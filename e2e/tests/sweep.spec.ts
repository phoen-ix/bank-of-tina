import { App, expect, PNG, test, uid, type User } from './fixtures'

/* Breadth: every GET route of `flask routes` (COVERAGE.md) as the one role the
 * app has - a visitor, there is no login. Pages must render their own title and
 * main heading without a page error, console error or 5xx (the guard fixture);
 * the JSON/asset routes must answer with the right type. */

let user: User
let txId: number
let receipt: string

test.beforeAll(async ({ playwright }, info) => {
  // One user with an expense (and a receipt) so the id routes have something to show.
  const ctx = await playwright.request.newContext({ baseURL: info.project.use.baseURL, extraHTTPHeaders: { 'X-Forwarded-For': `10.0.0.${info.workerIndex + 1}` } })
  const app = new App(ctx)
  user = await app.addUser()
  const buyer = await app.addUser()
  const desc = `Sweep lunch ${uid()}`
  await app.expense(buyer, desc, [['Soup', '4.20', user]], { receipt: { name: 'scan.png', mimeType: 'image/png', buffer: PNG } })
  ;[txId] = await app.transactionIds(desc)
  receipt = /href="\/receipt\/([^"]+)"/.exec(await app.html(`/user/${user.id}`))![1]
  await ctx.dispose()
})

const PAGES: Array<[name: string, path: () => string, title: () => string | RegExp, heading: string]> = [
  ['dashboard', () => '/', () => /^Dashboard - Bank of Tina$/, 'User Balances'],
  ['add transaction', () => '/transaction/add', () => /^Add Transaction - Bank of Tina$/, 'Who paid?'],
  ['all transactions', () => '/transactions', () => /^Transactions - Bank of Tina$/, 'Transactions'],
  ['search', () => '/search', () => /^Search Transactions – Bank of Tina$/, 'Search Transactions'],
  ['search results', () => '/search?q=Sweep', () => /^Search Transactions – Bank of Tina$/, 'transaction(s) found'],
  ['charts', () => '/analytics', () => /^Charts & Statistics - Bank of Tina$/, 'Charts & Statistics'],
  ['settings', () => '/settings', () => /^Settings - Bank of Tina$/, 'Settings'],
  ['user detail', () => `/user/${user.id}`, () => `${user.name} - Bank of Tina`, 'Transaction History'],
  ['edit transaction', () => `/transaction/${txId}/edit`, () => /^Edit Transaction - Bank of Tina$/, 'Edit Transaction #'],
  ['offline page', () => '/offline', () => /^Offline — Bank of Tina$/, "You're offline"],
]

test.describe('visitor (no login)', () => {
  for (const [name, path, title, heading] of PAGES) {
    test(`page: ${name}`, async ({ page }) => {
      const res = await page.goto(path())
      expect(res!.status()).toBe(200)
      await expect(page).toHaveTitle(title())
      // The offline page is standalone (no navbar, no <main>).
      const content = name === 'offline page' ? page.locator('body') : page.getByRole('main')
      await expect(content.getByText(heading).first()).toBeVisible()
    })
  }

  for (const tab of ['general', 'email', 'common-items', 'backup', 'templates', 'users']) {
    test(`page: settings tab ${tab}`, async ({ page }) => {
      await page.goto(`/settings?tab=${tab}`)
      await expect(page.locator(`#tab-${tab}`)).toHaveClass(/active/)
      await expect(page.locator(`#tab-btn-${tab}`)).toHaveAttribute('aria-selected', 'true')
    })
  }

  for (const [path, heading] of [
    ['/settings/templates/preview/email', 'Weekly Balance Update'],
    ['/settings/templates/preview/admin-summary', 'All Active Users'],
    ['/settings/templates/preview/backup', 'bot_backup_'],
  ] as const) {
    test(`email preview ${path}`, async ({ page }) => {
      const res = await page.goto(path)
      expect(res!.headers()['content-type']).toContain('text/html')
      await expect(page.getByText(heading).first()).toBeVisible()
    })
  }

  test('JSON and asset routes', async ({ request }) => {
    const json = async (path: string) => {
      const res = await request.get(path)
      expect(res.status(), path).toBe(200)
      expect(res.headers()['content-type'], path).toMatch(/json/)
      return res.json()
    }
    expect(await json('/health')).toMatchObject({ status: 'ok', checks: { database: 'ok', scheduler: 'ok' } })
    expect(await json('/manifest.json')).toMatchObject({ name: 'Bank of Tina', start_url: '/', display: 'standalone' })
    expect(Array.isArray(await json('/api/common-items'))).toBe(true)
    expect(Array.isArray(await json('/api/common-descriptions'))).toBe(true)
    expect(Array.isArray(await json('/api/common-prices'))).toBe(true)
    expect(await json(`/analytics/data?users=${user.id}`)).toHaveProperty('balances')

    const sw = await request.get('/sw.js')
    expect(sw.headers()['content-type']).toContain('javascript')
    expect(await sw.text()).toContain("const CACHE = 'bot-v3'")
    const icon = await request.get('/favicon.ico')
    expect(icon.headers()['content-type']).toBe('image/png')
    const rec = await request.get(`/receipt/${receipt}`)
    expect(rec.headers()['content-type']).toBe('image/png')
    expect(Buffer.compare(await rec.body(), PNG)).toBe(0)
    expect((await request.get('/static/js/money.js')).status()).toBe(200)
  })

  test('error states: 404 for unknown ids, files and routes', async ({ page, request, guard }) => {
    guard.allow(/404/)
    for (const path of ['/user/999999', '/transaction/999999/edit', '/receipt/2000/01/01/none.png', '/backups/download/evil.txt',
      '/backups/download/bot_backup_2000_01_01_00-00-00.tar.gz', '/no-such-page']) {
      expect((await request.get(path)).status(), path).toBe(404)
    }
    const res = await page.goto('/user/999999')
    expect(res!.status()).toBe(404)
    await expect(page.getByRole('heading', { name: 'Not Found' })).toBeVisible()
  })
})
