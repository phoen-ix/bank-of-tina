import { expect, expectToast, test, uid } from './fixtures'
import type { Page } from '@playwright/test'

/* Settings → Common: the item name / description / price lists that feed the
 * autocomplete, and their blacklists. Every value is unique to the test. The
 * global switch and auto-collect are in global/autocollect.spec.ts. */

const card = (page: Page, header: string) => page.locator('#tab-common-items .card').filter({ has: page.locator('.card-header', { hasText: header }) })

async function removeBadge(page: Page, cardHeader: string, text: string, confirmText: string) {
  const badge = card(page, cardHeader).locator('.badge').filter({ hasText: text })
  let message = ''
  page.once('dialog', (d) => {
    message = d.message()
    void d.accept()
  })
  await badge.getByRole('button', { name: 'Remove' }).click()
  await expect(badge).toHaveCount(0)
  expect(message).toBe(confirmText)
}

test('item names: add, no duplicates, autocomplete, remove', async ({ page, app }) => {
  const name = `Cappuccino ${uid()}`
  await page.goto('/settings?tab=common-items')
  const items = card(page, 'Item Names')
  await items.getByPlaceholder('New item name').fill(name)
  await items.getByRole('button', { name: /Add$/ }).click()
  await expectToast(page, `"${name}" added to common items.`)
  // The page comes back on the Common tab.
  await expect(page.locator('#tab-common-items')).toHaveClass(/active/)
  await expect(items.locator('.badge').filter({ hasText: name })).toHaveCount(1)
  await items.getByPlaceholder('New item name').fill(name)
  await items.getByRole('button', { name: /Add$/ }).click()
  await expectToast(page, `"${name}" added to common items.`)
  await expect(items.locator('.badge').filter({ hasText: name })).toHaveCount(1)
  expect((await (await app.api.get('/api/common-items')).json()).map((i: { name: string }) => i.name)).toContain(name)

  await removeBadge(page, 'Item Names', name, `Remove '${name}' from common items?`)
  await expectToast(page, `"${name}" removed from common items.`)
  expect((await (await app.api.get('/api/common-items')).json()).map((i: { name: string }) => i.name)).not.toContain(name)
})

test('descriptions: add and remove', async ({ page, app }) => {
  const value = `Café Central ${uid()}`
  await page.goto('/settings?tab=common-items')
  const descs = card(page, 'Descriptions')
  await descs.getByPlaceholder('New description').fill(value)
  await descs.getByRole('button', { name: /Add$/ }).click()
  await expectToast(page, `"${value}" added to common descriptions.`)
  expect((await (await app.api.get('/api/common-descriptions')).json()).map((i: { value: string }) => i.value)).toContain(value)
  await removeBadge(page, 'Descriptions', value, `Remove '${value}' from common descriptions?`)
  await expectToast(page, `"${value}" removed from common descriptions.`)
})

test('prices: comma input, display, invalid input, remove', async ({ page }) => {
  // Prices are shared by value; a cent value nobody else uses.
  const cents = 100000 + Math.floor(Math.random() * 800000)
  const shown = `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, '0')}`
  await page.goto('/settings?tab=common-items')
  const prices = card(page, 'Prices')
  await prices.getByPlaceholder('Price (e.g. 3.50)').fill(shown.replace('.', ','))
  await prices.getByRole('button', { name: /Add$/ }).click()
  await expectToast(page, `€${shown} added to common prices.`)
  await expect(prices.locator('.badge').filter({ hasText: `€${shown}` })).toHaveCount(1)
  await prices.getByPlaceholder('Price (e.g. 3.50)').fill('free')
  await prices.getByRole('button', { name: /Add$/ }).click()
  await expectToast(page, 'Valid price is required.')
  await removeBadge(page, 'Prices', `€${shown}`, `Remove €${shown} from common prices?`)
  await expectToast(page, `€${shown} removed from common prices.`)
})

test('blacklists: item, description and price (normalised)', async ({ page }) => {
  const id = uid()
  const n = 1000 + Math.floor(Math.random() * 90000)
  await page.goto('/settings?tab=common-items')
  for (const [header, placeholder, value, stored, kind] of [
    ['Item Names', 'Item name to blacklist', `Napkins ${id}`, `Napkins ${id}`, 'item'],
    ['Descriptions', 'Description to blacklist', `Misc ${id}`, `Misc ${id}`, 'description'],
    ['Prices', 'Price to blacklist (e.g. 3.50)', `${n},5`, `${n}.50`, 'price'],
  ] as const) {
    const c = card(page, header)
    await c.getByPlaceholder(placeholder).fill(value)
    await c.getByRole('button', { name: 'Add to blacklist' }).click()
    await expectToast(page, `"${stored}" added to ${kind} blacklist.`)
    const badge = card(page, header).locator('.badge.bg-warning').filter({ hasText: stored })
    await expect(badge).toHaveCount(1)
    page.once('dialog', (d) => void d.accept())
    await badge.getByRole('button', { name: 'Remove' }).click()
    await expectToast(page, `"${stored}" removed from ${kind} blacklist.`)
    await expect(badge).toHaveCount(0)
  }
  await card(page, 'Prices').getByPlaceholder('Price to blacklist (e.g. 3.50)').fill('-1')
  await card(page, 'Prices').getByRole('button', { name: 'Add to blacklist' }).click()
  await expectToast(page, 'Valid price is required.')
})

test('server-side checks: blank values and unknown ids', async ({ app }) => {
  expect(await app.post('/settings/common-items/add', { name: '  ' }, { error: true })).toContain('Item name is required.')
  expect(await app.post('/settings/common-descriptions/add', { value: ' ' }, { error: true })).toContain('Description is required.')
  expect(await app.post('/settings/common-blacklist/add', { type: 'colour', value: 'red' }, { error: true })).toContain('Invalid blacklist entry.')
  const token = /<meta name="csrf-token" content="([^"]+)"/.exec(await app.html('/search'))![1]
  for (const kind of ['common-items', 'common-descriptions', 'common-prices', 'common-blacklist']) {
    expect((await app.api.post(`/settings/${kind}/99999999/delete`, { form: { csrf_token: token } })).status(), kind).toBe(404)
  }
})
