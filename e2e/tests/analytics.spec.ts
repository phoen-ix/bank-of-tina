import { expect, test, uid, type App, type User } from './fixtures'
import type { Page } from '@playwright/test'

/* Charts & Statistics: filters (dates, users, quick ranges), the four chart
 * tabs, empty states, the error box and printing. The charts are canvases, so
 * the tests check the data the page asked for and the DOM around the charts.
 * The browser clock is fixed: the quick ranges count back from it. */

const NOW = new Date('2036-06-15T10:00:00+02:00')

async function people(app: App): Promise<[User, User]> {
  const [a, b] = [await app.addUser(), await app.addUser()]
  await app.expense(a, `Pho ${uid()}`, [['Pho', '12.50', b], ['Spring rolls', '4.00', b], ['Pho', '12.50', b]], { date: '2036-06-01T12:00' })
  await app.deposit(b, '20', 'Top-up', { date: '2036-06-10T09:00' })
  await app.expense(b, `Bubble tea ${uid()}`, [['Bubble tea', '4.80', a]], { date: '2036-03-02T16:00' })
  return [a, b]
}

/** Tick exactly these users in the Users dropdown. */
async function onlyUsers(page: Page, users: User[]): Promise<void> {
  await page.locator('#user-dropdown-btn').click()
  await page.getByRole('link', { name: 'Clear all' }).click()
  for (const u of users) await page.getByLabel(u.name).check()
  await page.locator('#user-dropdown-btn').click()
}

async function apply(page: Page, from: string, to: string) {
  await page.getByLabel('From', { exact: true }).fill(from)
  await page.getByLabel('To', { exact: true }).fill(to)
  const res = page.waitForResponse((r) => r.url().includes('/analytics/data?'))
  await page.getByRole('button', { name: 'Apply' }).click()
  return (await res).json()
}

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(NOW)
})

test('first load: the last 90 days of every active user', async ({ page, app }) => {
  await app.addUser()
  const res = page.waitForResponse((r) => r.url().includes('/analytics/data?'))
  await page.goto('/analytics')
  const url = new URL((await res).url())
  expect(url.searchParams.get('date_to')).toBe(await page.getByLabel('To', { exact: true }).inputValue())
  await expect(page.locator('#user-dropdown-btn')).toHaveText('All users')
  await expect(page.locator('#skel-balances')).toBeHidden()
  await expect(page.locator('#chart-balances')).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Balances' })).toHaveAttribute('aria-selected', 'true')
})

test('filters: users and dates drive every chart', async ({ page, app }) => {
  const [a, b] = await people(app)
  await app.addUser() // so that two are not all
  await page.goto('/analytics')
  await onlyUsers(page, [a, b])
  await expect(page.locator('#user-dropdown-btn')).toHaveText(/^2 of \d+ users$/)
  const data = await apply(page, '2036-05-17', '2036-06-15')

  expect(data.balances).toEqual([{ name: a.name, balance: 24.2 }, { name: b.name, balance: -4.2 }].sort((x, y) => x.name.localeCompare(y.name)))
  // Weekly samples within 90 days, the last one on the end date.
  expect(data.balance_history.labels[0]).toBe('2036-05-17')
  expect(data.balance_history.labels.at(-1)).toBe('2036-06-15')
  expect(data.balance_history.datasets[a.name][0]).toBe(-4.8)
  expect(data.balance_history.datasets[a.name].at(-1)).toBe(24.2)
  expect(data.transaction_volume.labels).toEqual(['26 May', '9 Jun']) // weeks start on Monday
  expect(data.transaction_volume.counts).toEqual([1, 1])
  expect(data.top_items).toEqual({ names: ['Pho', 'Spring rolls'], counts: [2, 1], totals: [25, 4] })
  expect(data.meta).toMatchObject({ transaction_count: 2, user_count: 2 })
  await expect(page.locator('#print-meta')).toHaveText('2036-05-17 → 2036-06-15  ·  2 Transactions  ·  2 users')

  for (const tab of ['History', 'Volume', 'Top Items'] as const) {
    await page.getByRole('tab', { name: tab }).click()
    const id = { History: 'history', Volume: 'volume', 'Top Items': 'items' }[tab]
    await expect(page.locator(`#chart-${id}`)).toBeVisible()
    await expect(page.locator(`#empty-${id}`)).toBeHidden()
  }
  await page.getByRole('button', { name: 'By Count' }).click()
  await expect(page.getByRole('button', { name: 'By Count' })).toHaveClass(/active/)
  await expect(page.getByRole('button', { name: 'By Amount' })).not.toHaveClass(/active/)
  await page.getByRole('button', { name: 'By Amount' }).click()
  await expect(page.getByRole('button', { name: 'By Amount' })).toHaveClass(/active/)

  // More than 90 days: monthly samples.
  const long = await apply(page, '2036-01-01', '2036-06-15')
  expect(long.balance_history.labels).toEqual(['2036-01-01', '2036-02-01', '2036-03-01', '2036-04-01', '2036-05-01', '2036-06-01', '2036-06-15'])
  expect(long.transaction_volume.labels).toEqual(['Mar 2036', 'Jun 2036'])
})

test('empty states: no users ticked, and a period without transactions', async ({ page, app }) => {
  const [a] = await people(app)
  await page.goto('/analytics')
  await page.locator('#user-dropdown-btn').click()
  await page.getByRole('link', { name: 'Clear all' }).click()
  await expect(page.locator('#user-dropdown-btn')).toHaveText('No users')
  let asked = false
  page.on('request', (r) => void (r.url().includes('/analytics/data') && (asked = true)))
  await page.getByRole('button', { name: 'Apply' }).click({ force: true })
  await expect(page.getByText('No users to display.')).toBeVisible()
  expect(asked).toBe(false)
  await page.locator('#user-dropdown-btn').click()
  await page.getByRole('link', { name: 'Select all' }).click()
  await expect(page.locator('#user-dropdown-btn')).toHaveText('All users')
  await page.locator('#user-dropdown-btn').click() // close it again

  await onlyUsers(page, [a])
  await apply(page, '2030-01-01', '2030-01-31')
  await page.getByRole('tab', { name: 'Volume' }).click()
  await expect(page.getByText('No transactions in this period.')).toBeVisible()
  await page.getByRole('tab', { name: 'Top Items' }).click()
  await expect(page.getByText('No expense items in this period.')).toBeVisible()
  // The balance history still has a (flat) line for the user.
  await page.getByRole('tab', { name: 'History' }).click()
  await expect(page.locator('#chart-history')).toBeVisible()
})

test('quick ranges count back from today', async ({ page, app }) => {
  const [a] = await people(app)
  await page.goto('/analytics')
  await onlyUsers(page, [a])
  // "1 year" is 365 days, and 2036 is a leap year.
  for (const [label, from] of [['30 days', '2036-05-16'], ['90 days', '2036-03-17'], ['1 year', '2035-06-16']] as const) {
    const res = page.waitForResponse((r) => r.url().includes(`date_from=${from}`))
    await page.getByRole('button', { name: label }).click()
    await res
    await expect(page.getByLabel('From', { exact: true })).toHaveValue(from)
    await expect(page.getByLabel('To', { exact: true })).toHaveValue('2036-06-15')
  }
  // All: from the first transaction anyone recorded.
  await page.getByRole('button', { name: 'All', exact: true }).click()
  await expect(page.getByLabel('From', { exact: true })).not.toHaveValue('2035-06-16')
  await expect(page.getByLabel('From', { exact: true })).toHaveValue(/^\d{4}-\d{2}-\d{2}$/)
})

test('a failing data request shows the error box', async ({ page, guard }) => {
  guard.allow(/500|Analytics fetch failed/)
  await page.route('**/analytics/data?*', (r) => r.fulfill({ status: 500, body: 'boom' }))
  await page.goto('/analytics')
  await expect(page.getByRole('alert')).toContainText('Could not load the chart data:')
  await expect(page.locator('#skel-balances')).toBeHidden()
  await page.unroute('**/analytics/data?*')
  await page.getByRole('button', { name: 'Apply' }).click()
  await expect(page.locator('#analytics-error')).toBeHidden()
})

test('print: the button prints, print media shows only the header and the active chart', async ({ page }) => {
  await page.addInitScript(() => {
    ;(window as unknown as { printed: number }).printed = 0
    window.print = () => void (window as unknown as { printed: number }).printed++
  })
  await page.goto('/analytics')
  await expect(page.locator('#chart-balances')).toBeVisible()
  await page.getByRole('button', { name: 'Print / PDF' }).click()
  expect(await page.evaluate(() => (window as unknown as { printed: number }).printed)).toBe(1)

  await page.getByRole('tab', { name: 'History' }).click()
  const meta = page.locator('#print-meta')
  const before = await meta.textContent()
  await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')))
  await expect(meta).toHaveText(`${before}  ·  History`)
  await page.emulateMedia({ media: 'print' })
  await expect(page.getByRole('heading', { name: 'Bank of Tina — Charts & Statistics' })).toBeVisible()
  await expect(page.locator('#filter-card')).toBeHidden()
  await expect(page.locator('nav.navbar')).toBeHidden()
  await page.emulateMedia({ media: 'screen' })
  await page.evaluate(() => window.dispatchEvent(new Event('afterprint')))
  await expect(meta).toHaveText(before!)
})
