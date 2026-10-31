import { expect, expectToast, test, uid } from '../fixtures'
import type { Page } from '@playwright/test'

/* Settings → Common: the global autocomplete switch and auto-collect (schedule,
 * Run Now, blacklist, debug log). Global settings: the serial project. */

const OFF = {
  common_auto_enabled: '', common_auto_debug: '', common_auto_day: '*', common_auto_hour: '2', common_auto_minute: '0',
  common_items_auto: '', common_items_threshold: '5', common_descriptions_auto: '', common_descriptions_threshold: '5',
  common_prices_auto: '', common_prices_threshold: '5',
}

test.afterEach(async ({ app }) => {
  await app.post('/settings/common', { common_enabled: '1' })
  await app.post('/settings/common-auto', OFF)
  await app.post('/settings/common-auto/clear-log', {})
})

const commonTab = (page: Page) => page.locator('#tab-common-items')

test('switching autocomplete off empties every suggestion list', async ({ page, app }) => {
  const name = `Strudel ${uid()}`
  await app.post('/settings/common-items/add', { name })
  await page.goto('/settings?tab=common-items')
  await page.getByLabel('Enable Common autocomplete feature').uncheck()
  await commonTab(page).locator('form').first().getByRole('button', { name: 'Save' }).click()
  await expectToast(page, 'Common autocomplete settings saved.')
  await expect(page.getByLabel('Enable Common autocomplete feature')).not.toBeChecked()
  for (const api of ['/api/common-items', '/api/common-descriptions', '/api/common-prices']) {
    expect(await (await page.request.get(api)).json(), api).toEqual([])
  }
  await page.goto('/transaction/add')
  await expect(page.locator('#commonItemsList option')).toHaveCount(0)

  await page.goto('/settings?tab=common-items')
  await page.getByLabel('Enable Common autocomplete feature').check()
  await commonTab(page).locator('form').first().getByRole('button', { name: 'Save' }).click()
  await page.goto('/transaction/add')
  await expect(page.locator(`#commonItemsList option[value="${name}"]`)).toBeAttached()
})

test('auto-collect: schedule, Run Now promotes frequent values, blacklist wins, debug log', async ({ page, app }) => {
  const id = uid()
  const [buyer, a] = [await app.addUser(), await app.addUser()]
  for (let i = 0; i < 2; i++) {
    await app.expense(buyer, `Dim sum ${id}`, [[`Bao ${id}`, '3.10', a], [`Tea ${id}`, '2.00', a]])
  }
  await app.post('/settings/common-blacklist/add', { type: 'item', value: `tea ${id}` }) // case-insensitive

  await page.goto('/settings?tab=common-items')
  const fields = page.locator('#common_auto_fields')
  await expect(fields).toBeHidden()
  await page.getByLabel('Enable auto-collect').check()
  await expect(fields).toBeVisible()
  await page.getByLabel('Debug mode — log all decisions to database').check()
  const tab = commonTab(page)
  await tab.getByLabel('Item names').check()
  await tab.getByLabel('Descriptions', { exact: true }).check()
  for (const t of await tab.getByLabel('Min occurrences:').all()) await t.fill('2')
  await tab.getByLabel('Run', { exact: true }).selectOption('sat')
  await tab.getByLabel('Hour').selectOption('4')
  await tab.getByLabel('Minute').selectOption('15')
  await page.getByRole('button', { name: 'Save Auto-Collect' }).click()
  await expectToast(page, 'Auto-collect schedule saved and enabled.')
  await expect(page.getByText('Auto-collect runs every Saturday at 04:15 (Europe/Vienna).')).toBeVisible()

  await page.getByRole('button', { name: 'Run Now' }).click()
  await expectToast(page, 'Auto-collect job ran successfully.')
  const items = (await (await page.request.get('/api/common-items')).json()).map((i: { name: string }) => i.name)
  expect(items).toContain(`Bao ${id}`)
  expect(items).not.toContain(`Tea ${id}`)
  const descs = (await (await page.request.get('/api/common-descriptions')).json()).map((d: { value: string }) => d.value)
  expect(descs).toContain(`Dim sum ${id}`)
  const log = commonTab(page).locator('pre')
  await expect(log).toContainText(new RegExp(`\\[ADDED\\] item\\s+Added "Bao ${id}"`))
  await expect(log).toContainText(new RegExp(`\\[SKIP\\] item\\s+"Tea ${id}" \\(blacklist\\)`))
  await expect(log).toContainText('Run complete:')

  page.once('dialog', (d) => void d.accept())
  await commonTab(page).getByRole('button', { name: 'Clear Log' }).click()
  await expectToast(page, 'Debug log cleared.')
  await expect(page.getByText('No log entries yet. Run auto-collect to generate log entries.')).toBeVisible()

  await page.getByLabel('Enable auto-collect').uncheck()
  await page.getByRole('button', { name: 'Save Auto-Collect' }).click()
  await expectToast(page, 'Auto-collect schedule disabled.')
  await expect(page.getByText('Auto-collect runs')).toHaveCount(0)
})
