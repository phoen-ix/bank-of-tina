import { closeSync, ftruncateSync, openSync } from 'node:fs'

import { expect, expectToast, test, uid } from '../fixtures'
import type { Page } from '@playwright/test'

/* Settings → Backup: create, download, delete, chunked upload, restore (with
 * the safety backup) and the schedule. Needs the real stack (mariadb-dump in
 * the image): scripts/e2e.sh sets E2E_STACK. Restore replaces the whole
 * database, so this runs in the serial `global` project. */

test.skip(!process.env.E2E_STACK, 'needs the Docker stack of scripts/e2e.sh (mariadb-dump)')

const OFF = { backup_enabled: '', backup_debug: '', backup_admin_email: '', backup_day: '*', backup_hour: '3', backup_minute: '0', backup_keep: '7' }

test.afterEach(async ({ app }) => {
  await app.post('/settings/backup', OFF)
})

async function createBackup(page: Page): Promise<string> {
  await page.goto('/settings?tab=backup')
  await page.getByRole('button', { name: 'Create Backup Now' }).click()
  const toast = page.locator('#toastContainer .toast-body').filter({ hasText: 'Backup created: ' })
  await expect(toast).toBeAttached()
  return (await toast.textContent())!.replace('Backup created: ', '').trim()
}

const row = (page: Page, file: string) => page.locator('#tab-backup tr').filter({ hasText: file })

test('create, download and delete a backup', async ({ page }) => {
  const file = await createBackup(page)
  expect(file).toMatch(/^bot_backup_\d{4}_\d{2}_\d{2}_\d{2}-\d{2}-\d{2}(-\d+)?\.tar\.gz$/)
  await expect(row(page, file)).toContainText(/\d+ KB/)

  const download = page.waitForEvent('download')
  await row(page, file).getByRole('link', { name: 'Download' }).click()
  expect((await download).suggestedFilename()).toBe(file)
  expect((await (await download).createReadStream()).readable).toBe(true)

  let message = ''
  page.once('dialog', (d) => {
    message = d.message()
    void d.accept()
  })
  await row(page, file).getByRole('button', { name: 'Delete' }).click()
  await expectToast(page, `${file} deleted.`)
  expect(message).toBe(`Delete ${file}?`)
  await expect(row(page, file)).toHaveCount(0)
})

test('delete: unknown and invalid file names', async ({ app }) => {
  expect(await app.post('/backups/delete/bot_backup_2000_01_01_00-00-00.tar.gz', {}, { error: true })).toContain('Backup file not found.')
  expect(await app.post('/backups/delete/notes.txt', {}, { error: true })).toContain('Invalid filename.')
  expect(await app.post('/backups/restore/bot_backup_2000_01_01_00-00-00.tar.gz', {}, { error: true })).toContain('Backup file not found.')
})

test('upload a downloaded backup and restore it: later changes are undone', async ({ page, app }) => {
  const u = await app.addUser()
  await app.deposit(u, '10', `Before ${uid()}`)
  const file = await createBackup(page)
  const archive = await (await page.request.get(`/backups/download/${file}`)).body()
  await app.deposit(u, '5', `After ${uid()}`)
  expect(await app.balance(u)).toBe('€15.00')

  // Upload it again: it comes back under a new name.
  await page.goto('/settings?tab=backup')
  const before = await page.locator('#tab-backup td.font-monospace').allTextContents()
  await page.locator('#backupFileInput').setInputFiles({ name: file, mimeType: 'application/gzip', buffer: archive })
  await page.locator('#uploadBtn').click()
  await expect(page.locator('#uploadStatus')).toContainText('Upload complete: bot_backup_')
  await expect(page.locator('#uploadProgressBar')).toHaveText('100%')
  const uploaded = (await page.locator('#uploadStatus').textContent())!.replace('Upload complete: ', '').trim()
  // The page reloads by itself and lists it.
  await expect(row(page, uploaded)).toBeVisible()
  expect(before).not.toContain(uploaded)

  page.once('dialog', (d) => void d.dismiss())
  await row(page, uploaded).getByRole('button', { name: 'Restore' }).click()
  expect(await app.balance(u)).toBe('€15.00')

  let message = ''
  page.once('dialog', (d) => {
    message = d.message()
    void d.accept()
  })
  await row(page, uploaded).getByRole('button', { name: 'Restore' }).click()
  await expectToast(page, new RegExp(`^Restore from ${uploaded.replaceAll('.', '\\.')} completed successfully\\. The previous state was saved as bot_backup_.+\\.tar\\.gz\\.$`))
  expect(message).toContain('Restore from this backup?')
  expect(message).toContain('A backup of the current state is created first.')
  expect(await app.balance(u)).toBe('€10.00')
})

test('upload: no file, an empty file, a too large file, not an archive', async ({ page, guard }) => {
  guard.allow(/400/)
  await page.goto('/settings?tab=backup')
  const upload = page.locator('#uploadBtn')
  let message: Promise<string> = new Promise((r) => page.once('dialog', (d) => void r(d.message()) || void d.accept()))
  await upload.click()
  expect(await message).toBe('Please select a file first.')
  await page.locator('#backupFileInput').setInputFiles({ name: 'empty.tar.gz', mimeType: 'application/gzip', buffer: Buffer.alloc(0) })
  message = new Promise((r) => page.once('dialog', (d) => void r(d.message()) || void d.accept()))
  await upload.click()
  expect(await message).toBe('The selected file is empty.')
  // Over 400 chunks of 5 MB (a sparse file: nothing is read before the check).
  const big = test.info().outputPath('big.tar.gz')
  const fd = openSync(big, 'w')
  ftruncateSync(fd, 2_100_000_000)
  closeSync(fd)
  await page.locator('#backupFileInput').setInputFiles(big)
  message = new Promise((r) => page.once('dialog', (d) => void r(d.message()) || void d.accept()))
  await upload.click()
  expect(await message).toBe('The file is too large (max 2 GB).')
  await page.locator('#backupFileInput').setInputFiles({ name: 'notes.tar.gz', mimeType: 'application/gzip', buffer: Buffer.from('not a tar file') })
  await upload.click()
  await expect(page.locator('#uploadStatus')).toHaveText('Upload error: The uploaded file is not a backup archive.')
  await expect(page.locator('#uploadProgressBar')).toHaveClass(/bg-danger/)
  await expect(upload).toBeEnabled()
})

test('schedule: enable with retention, summary line, debug log, disable', async ({ page }) => {
  await page.goto('/settings?tab=backup')
  const tab = page.locator('#tab-backup')
  await expect(tab.getByLabel('Send backup status email to site admin')).toBeDisabled()
  await tab.getByLabel('Enable automatic backups').check()
  await tab.getByLabel('Debug mode — log backup runs to database').check()
  await tab.getByLabel('Run', { exact: true }).selectOption('sun')
  await tab.getByLabel('Hour').selectOption('3')
  await tab.getByLabel('Minute').selectOption('30')
  await tab.getByLabel('Keep last').fill('14')
  await tab.getByRole('button', { name: 'Save Schedule' }).click()
  await expectToast(page, 'Backup schedule saved and enabled.')
  await expect(tab.getByText('Backups run every Sunday at 03:30 (Europe/Vienna).')).toBeVisible()
  await expect(tab.getByLabel('Keep last')).toHaveValue('14')

  const log = page.locator('.card').filter({ has: page.getByText('Backup Debug Log') })
  await expect(log).toBeVisible()
  page.once('dialog', (d) => void d.accept())
  await log.getByRole('button', { name: 'Clear Log' }).click()
  await expectToast(page, 'Backup debug log cleared.')

  await tab.getByLabel('Enable automatic backups').uncheck()
  await tab.getByRole('button', { name: 'Save Schedule' }).click()
  await expectToast(page, 'Backup schedule disabled.')
  await expect(tab.getByText('Backups run')).toHaveCount(0)
})
