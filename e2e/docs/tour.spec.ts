import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test, type Page } from '@playwright/test'

import { BACKUPS, PEOPLE, seedDemo, type Demo, type Lang } from './seed'

/* The docs tour: one screenshot per screen and key state, in the language of
 * the Playwright project (en, de), against the demo office in ./seed.ts.
 * docs/screenshots/README.md is the gallery. Run it through
 * scripts/docs-screenshots.sh, which gives every language a fresh stack.
 *
 * It is ALSO a render check: every test asserts something page-specific
 * before it shoots, and an uncaught page error fails the test. */

const OUT = path.resolve(
  process.env.DOCS_SCREENSHOT_DIR ?? fileURLToPath(new URL('../../docs/screenshots', import.meta.url)),
)
mkdirSync(OUT, { recursive: true })

// The day the screenshots "are taken": after the last seeded transaction.
const NOW = new Date('2026-06-15T10:00:00+02:00')

let lang: Lang
let demo: Demo
let pageErrors: Error[] = []

/** English UI text, or its German translation in the de run. */
const tr = (en: string, de: string) => (lang === 'de' ? de : en)

test.beforeAll(async ({}, info) => {
  test.setTimeout(180_000)
  lang = info.project.name as Lang
  demo = await seedDemo(info.project.use.baseURL!, lang)
})

test.beforeEach(async ({ page }) => {
  pageErrors = []
  page.on('pageerror', (e) => pageErrors.push(e))
  await page.clock.setFixedTime(NOW)
  // Chart.js animates on its own clock; draw every chart in its final state.
  await page.addInitScript(() => {
    let chart: { defaults: { animation: boolean } } | undefined
    Object.defineProperty(window, 'Chart', {
      configurable: true,
      get: () => chart,
      set: (c) => {
        c.defaults.animation = false
        chart = c
      },
    })
  })
})

test.afterEach(async () => {
  expect(pageErrors.map((e) => e.message)).toEqual([])
})

/** `clipAbove`: the page from the top down to the top edge of that element.
 * `fullPage`: down to the footer, at most 2400 CSS px. Names get `.de` at the
 * end in the German run (`dashboard.mobile.de`). */
async function shoot(page: Page, name: string, opts: { fullPage?: boolean; clipAbove?: string } = {}): Promise<void> {
  // The icon font loads on first use; wait for it and for the relayout after it.
  await page.evaluate(async () => {
    await document.fonts.load('1em bootstrap-icons')
    await document.fonts.ready
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
  })
  await expect(page.locator('.toast')).toHaveCount(0)
  await expect(page.locator('.skeleton-placeholder:visible')).toHaveCount(0)
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.mouse.move(0, 0)
  const width = page.viewportSize()!.width
  let clip: { x: number; y: number; width: number; height: number } | undefined
  if (opts.clipAbove) {
    const box = await page.locator(opts.clipAbove).boundingBox()
    if (!box) throw new Error(`[docs] ${opts.clipAbove} is not on the page`)
    clip = { x: 0, y: 0, width, height: Math.min(2400, Math.floor(box.y)) }
  } else if (opts.fullPage) {
    const footer = page.locator('footer')
    const height = (await footer.count())
      ? (await footer.boundingBox())!.y
      : await page.evaluate(() => document.documentElement.scrollHeight)
    clip = { x: 0, y: 0, width, height: Math.min(2400, Math.floor(height)) }
  }
  await page.screenshot({
    path: path.join(OUT, `${name}${lang === 'de' ? '.de' : ''}.png`),
    animations: 'disabled',
    caret: 'hide',
    fullPage: Boolean(clip),
    clip,
  })
}

const name = (who: keyof typeof PEOPLE) => PEOPLE[who].name

/* --- dashboard ------------------------------------------------------------ */

test('dashboard', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.card-header', { hasText: tr('User Balances', 'Benutzersalden') })).toBeVisible()
  await expect(page.getByRole('link', { name: name('lukas') })).toBeVisible()
  // The admin is the bank and not listed; Lena is deactivated.
  await expect(page.getByRole('link', { name: name('tina') })).toHaveCount(0)
  await shoot(page, 'dashboard', { fullPage: true })
})

test('dashboard: mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByRole('link', { name: name('lukas') })).toBeVisible()
  await expect(page.locator('.navbar-toggler')).toBeVisible()
  // Balances and the three newest transactions, not a row cut in half.
  await shoot(page, 'dashboard.mobile', { clipAbove: '.list-group-item:nth-child(4)' })
})

/* --- transactions ------------------------------------------------------------ */

test('add transaction: expense', async ({ page }) => {
  await page.goto('/transaction/add')
  const form = page.locator('#expenseForm')
  await form.locator('#buyer_id').selectOption({ label: name('tina') })
  await form.locator('#description').fill('Pizzeria Da Mario')
  const rows = form.locator('.expense-item')
  await expect(rows).toHaveCount(3)
  const items: Array<[string, string, keyof typeof PEOPLE]> = [
    ['Pizza Margherita', '9.50', 'lukas'],
    ['Pizza Diavola', '11.00', 'sophie'],
    ['Tiramisu', '5.50', 'tina'],
  ]
  for (const [i, [item, price, who]] of items.entries()) {
    await rows.nth(i).locator('.item-name').fill(item)
    await rows.nth(i).locator('.item-price').fill(lang === 'de' ? price.replace('.', ',') : price)
    await rows.nth(i).locator('.item-debtor').selectOption({ label: name(who) })
  }
  await form.locator('#expense_date').fill('2026-06-15T12:30')
  await page.locator('h1, .card-header').first().click()
  await expect(page.locator('#totalAmount')).toHaveText(tr('26.00', '26,00'))
  await expect(page.locator('#owedNote')).toBeVisible()
  await shoot(page, 'transaction-add', { fullPage: true })
})

test('transactions: month', async ({ page }) => {
  await page.goto('/transactions?year=2026&month=6')
  await expect(page.locator('#jump-month')).toHaveValue('6')
  await expect(page.getByText('Sushi Kaito').first()).toBeVisible()
  await shoot(page, 'transactions', { fullPage: true })
})

test('transactions: empty month', async ({ page }) => {
  await page.goto('/transactions?year=2026&month=3')
  await expect(page.locator('#jump-month')).toHaveValue('3')
  await expect(page.locator('.card-body p.text-muted')).toContainText('2026')
  await shoot(page, 'transactions-empty', { fullPage: true })
})

test('edit transaction', async ({ page }) => {
  await page.goto('/transactions?year=2026&month=6')
  const row = page.locator('tr', { hasText: 'Sushi Kaito' }).filter({ hasText: name('lukas') })
  await row.locator('a[href*="/edit"]').click()
  await expect(page.locator('input[name="description"]')).toHaveValue('Sushi Kaito')
  await expect(page.getByText(tr('View current receipt', 'Aktuellen Beleg anzeigen'))).toBeVisible()
  await shoot(page, 'transaction-edit', { fullPage: true })
})

test('search: advanced filters', async ({ page }) => {
  await page.goto(`/search?q=Pizza&type=expense&user=${demo.ids.lukas}`)
  await expect(page.locator('#advancedFilters')).toBeVisible()
  await expect(page.getByText('Pizzeria Da Mario').first()).toBeVisible()
  await shoot(page, 'search', { fullPage: true })
})

test('search: no results', async ({ page }) => {
  await page.goto('/search?q=Kebab')
  await expect(page.getByText(tr('No transactions found for your search.', 'Keine Transaktionen für deine Suche gefunden.'))).toBeVisible()
  await shoot(page, 'search-empty', { fullPage: true })
})

/* --- users ------------------------------------------------------------------- */

test('user detail', async ({ page }) => {
  await page.goto(`/user/${demo.ids.lukas}`)
  await expect(page.locator('.card-header', { hasText: name('lukas') })).toBeVisible()
  await expect(page.getByText('2025-09-01')).toBeVisible()
  // The newest three transactions; the rest of the page is more of the same.
  await shoot(page, 'user-detail', { clipAbove: '.list-group-item:nth-child(4)' })
})

test('user detail: edit dialog', async ({ page }) => {
  await page.goto(`/user/${demo.ids.lukas}`)
  await page.getByRole('button', { name: tr('Edit User', 'Benutzer bearbeiten') }).click()
  await expect(page.locator('#editUserModal')).toBeVisible()
  await expect(page.locator('#editName')).toHaveValue(name('lukas'))
  await shoot(page, 'user-edit')
})

/* --- charts ---------------------------------------------------------------- */

// One tab of four (the PNG size budget): History. The page builds all four
// charts on every load, so a broken one still fails the render check.
for (const [tab, file] of [['history', 'charts-history']] as const) {
  test(`charts: ${tab}`, async ({ page }) => {
    await page.goto('/analytics')
    // The page loads the server's last 90 days first; then the tour's fixed range.
    await expect(page.locator('#wrap-balances')).toBeVisible()
    await page.locator('#filter-from').fill('2026-03-17')
    await page.locator('#filter-to').fill('2026-06-15')
    const data = page.waitForResponse((r) => r.url().includes('/analytics/data?date_from=2026-03-17'))
    await page.locator('#btn-apply').click()
    await data
    await expect(page.locator('#wrap-balances')).toBeVisible()
    await page.locator(`button[data-bs-target="#tab-${tab}"]`).click()
    await expect(page.locator(`#tab-${tab}`)).toHaveClass(/show/)
    const canvas = page.locator(`#chart-${tab}`)
    await expect(canvas).toBeVisible()
    // Chart.js redraws a chart that was hidden on its next resize frame.
    await expect.poll(() => canvas.evaluate((c: HTMLCanvasElement) => c.width)).toBeGreaterThan(600)
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))))
    await shoot(page, file, { fullPage: true })
  })
}

/* --- settings -------------------------------------------------------------- */

// Long tabs stop above a section (the PNG size budget): General above the
// dashboard switch, Email above the sending switches, Common after the
// descriptions, Backup above the schedule, Templates after the weekly email.
for (const [tab, file, check, clipAbove] of [
  ['general', 'settings-general', '#tab-general select[name="timezone"]', '#tab-general .mb-4:has(#show_email_on_dashboard)'],
  ['email', 'settings-email', '#smtp_server', '#tab-email hr'],
  ['common-items', 'settings-common', '#tab-common-items form', '#tab-common-items .card:has(> .card-header .bi-currency-euro)'],
  ['backup', 'settings-backup', `#tab-backup a[href$="${BACKUPS[1]}"]`, '#tab-backup .card:has(> .card-header .bi-clock)'],
  ['templates', 'settings-templates', '#tab-templates input[name="color_navbar"]', '#tab-templates .card:has(> .card-header .bi-person-badge)'],
  ['users', 'settings-users', '#new_user_name', ''],
] as const) {
  test(`settings: ${tab}`, async ({ page }) => {
    await page.goto(`/settings?tab=${tab}`)
    await expect(page.locator(`#tab-${tab}`)).toHaveClass(/active/)
    await expect(page.locator(check).first()).toBeVisible()
    await shoot(page, file, clipAbove ? { clipAbove } : { fullPage: true })
  })
}

test('email preview', async ({ page }) => {
  await page.goto('/settings/templates/preview/email')
  // The first active user by name gets the preview: Anna, with her last 3 transactions.
  await expect(page.getByText('Anna', { exact: false }).first()).toBeVisible()
  await expect(page.getByText('Café Sperl')).toBeVisible()
  await shoot(page, 'email-preview', { fullPage: true })
})

test('offline page', async ({ page }) => {
  await page.goto('/offline')
  await expect(page.locator('h1')).toBeVisible()
  await expect(page.locator('a.retry')).toBeVisible()
  await shoot(page, 'offline')
})
