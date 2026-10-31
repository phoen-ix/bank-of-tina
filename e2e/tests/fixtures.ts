import { randomBytes } from 'node:crypto'

import { test as base, expect, type APIRequestContext, type Page } from '@playwright/test'

/* Shared fixtures for the e2e suite.
 *
 * - `ip`: every test is its own client. The stack runs with BEHIND_PROXY=1, so
 *   the per-client rate limits (10 users/min, 30 transactions/min, ...) key on
 *   this X-Forwarded-For value and two tests never share a budget.
 * - `guard` (automatic): an uncaught page error, a console error or any 5xx
 *   response fails the test; `guard.allow(/.../)` for the ones a test expects.
 * - `app`: seeds data through the app's own web forms (there is no JSON API for
 *   writes), with the CSRF token of its own session, as the same client.
 *
 * Tests own their data: users and descriptions carry a unique suffix (`uid()`),
 * and month views use a month nobody else writes to (`app.freeMonth()`). */

export const uid = (): string => randomBytes(4).toString('hex')

/** The baseline the `setup` project puts in place and the global specs restore. */
export const GENERAL = {
  default_item_rows: '3', recent_transactions_count: '5', language: 'en', timezone: 'Europe/Vienna',
  site_admin_id: '', decimal_separator: '.', currency_symbol: '€',
}

export interface User { id: number; name: string; email: string }
type Item = [name: string, price: string, debtor: User]

export class App {
  private token = ''
  constructor(readonly api: APIRequestContext) {}

  async html(path: string): Promise<string> {
    const res = await this.api.get(path)
    expect(res.status(), `GET ${path}`).toBe(200)
    const body = await res.text()
    this.token = /<meta name="csrf-token" content="([^"]+)"/.exec(body)?.[1] ?? this.token
    return body
  }

  /** POST a form like the browser does. Unless `error` is set, the page it
   * redirects to must not show an error toast. Returns that page. */
  async post(path: string, fields: Record<string, string>, opts: { file?: { field: string; name: string; mimeType: string; buffer: Buffer }; error?: boolean } = {}): Promise<string> {
    if (!this.token) await this.html('/search')
    const data = { ...fields, csrf_token: this.token }
    const res = opts.file
      ? await this.api.post(path, { multipart: { ...data, [opts.file.field]: opts.file } })
      : await this.api.post(path, { form: data })
    const body = await res.text()
    expect(res.status(), `POST ${path}`).toBe(200)
    if (!opts.error) expect(toast(body, 'danger'), `POST ${path}`).toBeUndefined()
    return body
  }

  async addUser(opts: { name?: string; email?: string; optIn?: boolean; emailTx?: string } = {}): Promise<User> {
    const id = uid()
    const name = opts.name ?? `Ada Probe ${id}`
    const email = opts.email ?? `ada.${id}@e2e.example`
    const body = await this.post('/user/add', {
      name, email, email_opt_in: opts.optIn === false ? '' : '1', email_transactions: opts.emailTx ?? 'last3',
    })
    const m = new RegExp(`href="/user/(\\d+)"[^>]*>\\s*<strong>${name}</strong>`).exec(body)
    expect(m, `user ${name} on the Users tab`).not.toBeNull()
    return { id: Number(m![1]), name, email }
  }

  async expense(buyer: User, description: string, items: Item[], opts: { date?: string; notes?: string; receipt?: { name: string; mimeType: string; buffer: Buffer } } = {}): Promise<void> {
    await this.post('/transaction/add', {
      transaction_type: 'expense', buyer_id: String(buyer.id), description, notes: opts.notes ?? '', date: opts.date ?? '',
      items_json: JSON.stringify(items.map(([name, price, debtor]) => ({ name, price, debtor_id: String(debtor.id) }))),
    }, opts.receipt ? { file: { field: 'receipt', ...opts.receipt } } : {})
  }

  async deposit(user: User, amount: string, description: string, opts: { date?: string; notes?: string } = {}): Promise<void> {
    await this.post('/transaction/add', { transaction_type: 'deposit', user_id: String(user.id), amount, description, date: opts.date ?? '', notes: opts.notes ?? '' })
  }

  async withdrawal(user: User, amount: string, description: string, opts: { date?: string } = {}): Promise<void> {
    await this.post('/transaction/add', { transaction_type: 'withdrawal', user_id: String(user.id), amount, description, date: opts.date ?? '', notes: '' })
  }

  /** The user's balance as the detail page shows it, e.g. "€-12.50". */
  async balance(user: User): Promise<string> {
    const body = await this.html(`/user/${user.id}`)
    return /<h4 class="mb-0 balance-[a-z]+">\s*([^<]+?)\s*<\/h4>/.exec(body)![1]
  }

  /** Ids of the transactions a search for `q` finds, newest first. */
  async transactionIds(q: string): Promise<number[]> {
    const body = await this.html(`/search?q=${encodeURIComponent(q)}`)
    return [...body.matchAll(/href="\/transaction\/(\d+)\/edit"/g)].map((m) => Number(m[1]))
  }

  /** A month (year 2040-2099) with no transactions yet, for tests that count
   * what a month view shows. Returns [year, month]. */
  async freeMonth(): Promise<[number, number]> {
    for (;;) {
      const year = 2040 + Math.floor(Math.random() * 60)
      const month = 1 + Math.floor(Math.random() * 12)
      if ((await this.html(`/transactions?year=${year}&month=${month}`)).includes('No transactions recorded')) return [year, month]
    }
  }
}

/** The text of the first success/danger toast in a page's HTML. */
export function toast(html: string, kind: 'success' | 'danger'): string | undefined {
  return new RegExp(`text-bg-${kind}[\\s\\S]*?<div class="toast-body">([^<]*)<`).exec(html)?.[1]
}

/** Expect a flash message (a toast that hides itself after 4 s). */
export async function expectToast(page: Page, text: string | RegExp): Promise<void> {
  await expect(page.locator('#toastContainer .toast-body').filter({ hasText: text }).first()).toBeAttached()
}

/** Accept the next native confirm() and return its message. */
export function acceptNextDialog(page: Page): Promise<string> {
  return new Promise((resolve) => {
    page.once('dialog', async (d) => {
      const message = d.message()
      await d.accept()
      resolve(message)
    })
  })
}

const byte = () => Math.floor(Math.random() * 250) + 1

export const test = base.extend<{ ip: string; app: App; guard: { allow(re: RegExp): void } }>({
  ip: async ({}, use) => {
    await use(`10.${byte()}.${byte()}.${byte()}`)
  },
  extraHTTPHeaders: async ({ ip }, use) => {
    await use({ 'X-Forwarded-For': ip })
  },
  app: async ({ request }, use) => {
    await use(new App(request))
  },
  guard: [
    async ({ page }, use) => {
      const problems: string[] = []
      const allowed: RegExp[] = []
      page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`))
      page.on('console', (m) => {
        if (m.type() === 'error') problems.push(`console: ${m.text()}`)
      })
      page.on('response', (r) => {
        if (r.status() >= 500) problems.push(`HTTP ${r.status()} ${r.url()}`)
      })
      // When a Docker network comes or goes on the host, Chromium aborts every
      // request in flight with ERR_NETWORK_CHANGED (seen on the fleet VM: the
      // charts script went missing). A page.goto that met it loads the page
      // again (at most 3 times) and forgets what the broken load reported.
      const goto = page.goto.bind(page)
      page.goto = async (url, options) => {
        for (let attempt = 1; ; attempt++) {
          const mark = problems.length
          let changed = false
          const onFail = (r: { failure(): { errorText: string } | null }) => {
            if (r.failure()?.errorText === 'net::ERR_NETWORK_CHANGED') changed = true
          }
          page.on('requestfailed', onFail)
          try {
            const res = await goto(url, options)
            if (!changed || attempt === 3) return res
          } catch (e) {
            if (!String(e).includes('ERR_NETWORK_CHANGED') || attempt === 3) throw e
          } finally {
            page.off('requestfailed', onFail)
          }
          problems.length = mark
        }
      }
      await use({ allow: (re) => void allowed.push(re) })
      expect(problems.filter((p) => !allowed.some((re) => re.test(p)))).toEqual([])
    },
    { auto: true },
  ],
})

export { expect }

// A 1x1 PNG and a minimal PDF for receipts and icons.
export const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
)
export const PDF = Buffer.from('%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n')
