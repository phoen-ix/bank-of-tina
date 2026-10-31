import { expect, expectToast, GENERAL, test, uid } from '../fixtures'
import type { Page } from '@playwright/test'

/* Settings → General. These settings are global, so this file runs in the
 * serial `global` project and puts the baseline back after every test. */

test.afterEach(async ({ app }) => {
  await app.post('/settings/general', GENERAL)
})

async function saveGeneral(page: Page, change: () => Promise<void>, saved = 'General settings saved.') {
  await page.goto('/settings?tab=general')
  await change()
  await page.locator('#tab-general').getByRole('button', { name: /Save|Speichern/ }).click()
  await expectToast(page, saved)
}

test('language: the whole UI switches to German and back', async ({ page, app }) => {
  const u = await app.addUser()
  await saveGeneral(page, () => page.getByLabel('Language').selectOption('de').then(), 'Allgemeine Einstellungen gespeichert.')
  await expect(page.locator('html')).toHaveAttribute('lang', 'de')
  await expect(page).toHaveTitle('Einstellungen - Bank of Tina')
  await page.goto('/')
  await expect(page.getByText('Benutzersalden')).toBeVisible()
  await expect(page.getByRole('navigation').getByRole('link', { name: 'Transaktion hinzufügen' })).toBeVisible()
  await app.deposit(u, '3', `Einzahlung ${uid()}`, { date: '2036-06-12T12:00' })
  await page.goto('/transactions?year=2036&month=6')
  await expect(page.getByRole('heading', { name: 'Donnerstag, 12. Juni' })).toBeVisible()
  await expect(page.getByText('Einzahlung', { exact: true }).first()).toBeVisible() // the type badge
  await page.goto('/offline')
  await expect(page.getByRole('heading', { name: 'Du bist offline' })).toBeVisible()
  // Form errors are German too.
  await page.goto('/transaction/add?type=deposit')
  await page.locator('#deposit').getByLabel('Benutzer').selectOption({ label: u.name })
  await page.locator('#deposit').getByLabel('Betrag (€)').fill('0')
  await page.locator('#deposit').getByRole('button', { name: 'Geld einzahlen' }).click()
  await expectToast(page, 'Beträge müssen größer als null sein.')

  await saveGeneral(page, () => page.getByLabel('Sprache').selectOption('en').then())
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
})

test('German blacklist messages name the list in German', async ({ page, app }) => {
  await app.post('/settings/general', { ...GENERAL, language: 'de' })
  const id = uid()
  await page.goto('/settings?tab=common-items')
  for (const [placeholder, value, list] of [
    ['Artikelname für Blacklist', `Servietten ${id}`, 'Artikel'],
    ['Beschreibung für Blacklist', `Diverses ${id}`, 'Beschreibungs'],
  ]) {
    await page.getByPlaceholder(placeholder).fill(value)
    await page.getByPlaceholder(placeholder).locator('xpath=..').getByRole('button').click()
    await expectToast(page, `"${value}" zur ${list}-Blacklist hinzugefügt.`)
  }
})

test('timezone: stored times are shown in the chosen zone', async ({ page, app }) => {
  const u = await app.addUser()
  const desc = `Noon ${uid()}`
  await app.deposit(u, '1', desc, { date: '2036-01-15T12:00' }) // Vienna, UTC+1
  await page.goto(`/search?q=${desc.replace(' ', '+')}`)
  await expect(page.getByText('2036-01-15 12:00')).toBeVisible()
  await saveGeneral(page, () => page.getByLabel('Timezone').selectOption('America/New_York').then())
  await page.goto(`/search?q=${desc.replace(' ', '+')}`)
  await expect(page.getByText('2036-01-15 06:00')).toBeVisible()
  await page.goto('/settings?tab=email')
  await page.getByLabel('Enable automatic schedule').check()
  await page.getByRole('button', { name: 'Save Schedule' }).click()
  await expect(page.getByText('(America/New_York)')).toBeVisible()
  await app.post('/settings/schedule', { schedule_enabled: '', schedule_day: 'mon', schedule_hour: '9', schedule_minute: '0' })
})

test('decimal comma and currency symbol everywhere amounts appear', async ({ page, app }) => {
  const u = await app.addUser()
  await app.deposit(u, '1234.5', `Comma ${uid()}`)
  await saveGeneral(page, async () => {
    await page.getByLabel('Comma').check()
    await page.getByLabel('Currency symbol').selectOption('$')
  })
  await page.goto(`/user/${u.id}`)
  await expect(page.locator('h4')).toHaveText('$1234,50')
  await page.goto('/transaction/add?type=deposit')
  await expect(page.locator('#deposit').getByLabel('Amount ($)')).toHaveAttribute('placeholder', '0,00')
  await expect(page.locator('#totalAmount')).toHaveText('0,00')
  await page.locator('#deposit').getByLabel('User').selectOption({ label: u.name })
  await page.locator('#deposit').getByLabel('Amount ($)').fill('0,75')
  await page.locator('#deposit').getByRole('button', { name: 'Add Money' }).click()
  await expectToast(page, 'Deposit of $0,75 added successfully!')
  expect(await app.balance(u)).toBe('$1235,25')
})

test('dashboard options: email column and recent transactions', async ({ page, app }) => {
  const u = await app.addUser()
  await app.deposit(u, '2', `Recent ${uid()}`, { date: '2100-12-31T23:00' }) // newest of all
  await saveGeneral(page, async () => {
    await page.getByLabel('Show email address in user balances table').check()
    await page.getByLabel('Recent transactions on dashboard').fill('2')
  })
  await page.goto('/')
  await expect(page.getByRole('columnheader', { name: 'Email' })).toBeVisible()
  await expect(page.getByRole('row').filter({ hasText: u.name })).toContainText(u.email)
  const recent = page.locator('.card').filter({ hasText: 'Recent Transactions' }).locator('.list-group-item')
  await expect(recent).toHaveCount(2)
  await expect(recent.first()).toContainText('2100-12-31 23:00')
  await expect(recent.first()).toContainText(u.name)
  await page.getByRole('link', { name: 'View All Transactions' }).click()
  await expect(page).toHaveURL('/transactions')

  await saveGeneral(page, async () => {
    await page.getByLabel('Show email address in user balances table').uncheck()
    await page.getByLabel('Recent transactions on dashboard').fill('0')
  })
  await page.goto('/')
  await expect(page.getByText('Recent Transactions')).toHaveCount(0)
  await expect(page.getByRole('columnheader', { name: 'Email' })).toHaveCount(0)
})

test('default empty item rows on the expense form', async ({ page }) => {
  await saveGeneral(page, () => page.getByLabel('Default empty item rows').fill('5'))
  await page.goto('/transaction/add')
  await expect(page.locator('.expense-item')).toHaveCount(5)
  await saveGeneral(page, () => page.getByLabel('Default empty item rows').fill('0'))
  await page.goto('/transaction/add')
  await expect(page.locator('.expense-item')).toHaveCount(0)
  await expect(page.getByText('Click "Add Item" to add items from the receipt.')).toBeVisible()
  // Out-of-range numbers are clamped by the server.
  await page.goto('/settings?tab=general')
  await expect(page.getByLabel('Default empty item rows')).toHaveValue('0')
})

test('site admin: hidden from the dashboard, enables the admin emails', async ({ page, app }) => {
  const admin = await app.addUser()
  await page.goto('/settings?tab=email')
  await expect(page.getByLabel('Send admin summary email')).toBeDisabled()
  await expect(page.getByText('No site admin is configured.').first()).toBeVisible()
  await saveGeneral(page, () => page.getByLabel('Site Admin', { exact: true }).selectOption({ label: `${admin.name} (${admin.email})` }).then())
  await page.goto('/')
  await expect(page.getByRole('link', { name: admin.name })).toHaveCount(0)
  await page.goto('/settings?tab=email')
  await expect(page.getByLabel('Send admin summary email')).toBeEnabled()
  await page.goto('/settings?tab=backup')
  await expect(page.getByLabel('Send backup status email to site admin')).toBeEnabled()
  // A deactivated admin stays selected, marked inactive.
  await app.post(`/user/${admin.id}/toggle-active`, {})
  await page.goto('/settings?tab=general')
  await expect(page.getByLabel('Site Admin', { exact: true }).locator('option:checked')).toHaveText(`${admin.name} (${admin.email}) — inactive`)
  await app.post(`/user/${admin.id}/toggle-active`, {})
})
