import { execFileSync } from 'node:child_process'

import { expect, request, type APIRequestContext } from '@playwright/test'

/* The demo office the docs tour photographs: a team of seven sharing lunch and
 * coffee, with Tina as the "bank". Seeded through the app's own web forms (it
 * has no login and no JSON API for writes), in the UI language of the run -
 * scripts/docs-screenshots.sh gives every language a fresh stack.
 *
 * IDEMPOTENT: users, transactions and backups are looked up before they are
 * created; settings are simply posted again. Every transaction carries a fixed
 * local date, so the screenshots do not depend on when the tour runs. */

export type Lang = 'en' | 'de'

export const PEOPLE = {
  tina: { name: 'Tina Berger', since: '2025-09-01' },
  lukas: { name: 'Lukas Huber', since: '2025-09-01' },
  sophie: { name: 'Sophie Wagner', since: '2025-10-13' },
  jonas: { name: 'Jonas Gruber', since: '2025-11-03' },
  anna: { name: 'Anna Pichler', since: '2026-01-12' },
  felix: { name: 'Felix Moser', since: '2026-02-02' },
  lena: { name: 'Lena Bauer', since: '2025-09-01' },
} as const
type Who = keyof typeof PEOPLE

const email = (who: Who) => `${PEOPLE[who].name.toLowerCase().replace(' ', '.')}@tina-office.example`

/** Per-language demo text; proper nouns and dishes stay the same. */
const T = {
  en: {
    topUp: 'Cash top-up', payout: 'Cash payout', settle: 'Settled before leaving',
    teamLunch: 'Team lunch', farewell: 'Farewell lunch for Lena', groceries: 'Office groceries',
    groceriesNote: 'Milk, coffee beans and fruit for the kitchen',
    beans: 'Coffee beans 1 kg', milk: 'Milk (6 cartons)', fruit: 'Fruit basket', misc: 'Miscellaneous',
  },
  de: {
    topUp: 'Bareinzahlung', payout: 'Barauszahlung', settle: 'Vor dem Abschied ausgeglichen',
    teamLunch: 'Teamessen', farewell: 'Abschiedsessen für Lena', groceries: 'Büroeinkauf',
    groceriesNote: 'Milch, Kaffeebohnen und Obst für die Küche',
    beans: 'Kaffeebohnen 1 kg', milk: 'Milch (6 Packungen)', fruit: 'Obstkorb', misc: 'Sonstiges',
  },
} satisfies Record<Lang, Record<string, string>>

type Item = [name: string, price: string, debtor: Who]
type Tx =
  | { kind: 'expense'; at: string; buyer: Who; description: string; items: Item[]; notes?: string; receipt?: true }
  | { kind: 'deposit' | 'withdrawal'; at: string; who: Who; amount: string; description: string }

function transactions(t: (typeof T)[Lang]): Tx[] {
  return [
    { kind: 'expense', at: '2026-04-03T12:30', buyer: 'tina', description: 'Pizzeria Da Mario', items: [
      ['Pizza Margherita', '9.50', 'lukas'], ['Pizza Diavola', '11.00', 'sophie'],
      ['Pizza Funghi', '10.50', 'jonas'], ['Tiramisu', '5.50', 'lukas']] },
    { kind: 'deposit', at: '2026-04-10T09:15', who: 'lukas', amount: '50.00', description: t.topUp },
    { kind: 'expense', at: '2026-04-17T12:45', buyer: 'sophie', description: 'Sushi Kaito', items: [
      ['Sushi Bento', '14.90', 'anna'], ['Maki Set', '12.40', 'felix'], ['Miso Soup', '3.80', 'anna']] },
    { kind: 'expense', at: '2026-04-24T08:50', buyer: 'jonas', description: 'Café Sperl', items: [
      ['Cappuccino', '3.90', 'tina'], ['Melange', '4.20', 'lena'], ['Croissant', '2.80', 'tina']] },
    { kind: 'deposit', at: '2026-04-28T10:00', who: 'anna', amount: '40.00', description: t.topUp },
    { kind: 'expense', at: '2026-05-06T12:20', buyer: 'tina', description: 'Naschmarkt', items: [
      ['Falafel Wrap', '8.50', 'felix'], ['Hummus Bowl', '9.90', 'anna'],
      ['Falafel Wrap', '8.50', 'jonas'], ['Lemonade', '3.50', 'felix']] },
    { kind: 'withdrawal', at: '2026-05-12T15:00', who: 'sophie', amount: '20.00', description: t.payout },
    { kind: 'expense', at: '2026-05-15T08:40', buyer: 'lukas', description: 'Café Sperl', items: [
      ['Cappuccino', '3.90', 'sophie'], ['Croissant', '2.80', 'sophie'], ['Cappuccino', '3.90', 'felix']] },
    { kind: 'deposit', at: '2026-05-20T09:30', who: 'jonas', amount: '30.00', description: t.topUp },
    { kind: 'expense', at: '2026-05-22T12:30', buyer: 'tina', description: t.teamLunch, notes: t.farewell, items: [
      ['Wiener Schnitzel', '16.90', 'lena'], ['Tafelspitz', '18.50', 'lukas'],
      ['Käsespätzle', '13.90', 'sophie'], ['Apfelstrudel', '5.90', 'jonas']] },
    { kind: 'deposit', at: '2026-05-27T17:10', who: 'lena', amount: '21.10', description: t.settle },
    { kind: 'deposit', at: '2026-05-29T08:45', who: 'felix', amount: '25.00', description: t.topUp },
    { kind: 'expense', at: '2026-06-02T12:15', buyer: 'anna', description: 'Pizzeria Da Mario', items: [
      ['Pizza Margherita', '9.50', 'lukas'], ['Pizza Quattro Formaggi', '11.50', 'tina']] },
    { kind: 'deposit', at: '2026-05-29T10:00', who: 'sophie', amount: '40.00', description: t.topUp },
    { kind: 'expense', at: '2026-06-09T12:35', buyer: 'tina', description: 'Sushi Kaito', receipt: true, items: [
      ['Sushi Bento', '14.90', 'jonas'], ['Ramen', '13.50', 'lukas'], ['Edamame', '4.50', 'lukas']] },
    { kind: 'withdrawal', at: '2026-06-10T16:00', who: 'anna', amount: '15.00', description: t.payout },
    { kind: 'expense', at: '2026-06-11T08:40', buyer: 'felix', description: 'Café Sperl', items: [
      ['Cappuccino', '3.90', 'anna'], ['Croissant', '2.80', 'anna']] },
    { kind: 'expense', at: '2026-06-12T12:30', buyer: 'lukas', description: t.groceries, notes: t.groceriesNote, items: [
      [t.beans, '18.90', 'tina'], [t.milk, '7.14', 'tina'], [t.fruit, '12.00', 'tina']] },
    { kind: 'deposit', at: '2026-06-12T17:00', who: 'lukas', amount: '20.00', description: t.topUp },
  ]
}

/** The backups the Backup tab lists, renamed to fixed "scheduled" times. */
export const BACKUPS = ['bot_backup_2026_06_13_03-00-00.tar.gz', 'bot_backup_2026_06_14_03-00-00.tar.gz']

// A 1x1 PNG: the receipt is only ever linked, never shown inline.
const RECEIPT_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
)

export interface Demo {
  ids: Record<Who, number>
}

class Forms {
  private token = ''
  constructor(private api: APIRequestContext) {}

  async html(path: string): Promise<string> {
    const res = await this.api.get(path)
    expect(res.status(), `GET ${path}`).toBe(200)
    const body = await res.text()
    this.token = /<meta name="csrf-token" content="([^"]+)"/.exec(body)?.[1] ?? this.token
    return body
  }

  /** POST a form like the browser does; the redirect target must show no error toast. */
  async post(path: string, fields: Record<string, string>, file?: { name: string; buffer: Buffer }): Promise<string> {
    if (!this.token) await this.html('/settings')
    const data = { ...fields, csrf_token: this.token }
    const res = file
      ? await this.api.post(path, { multipart: { ...data, receipt: { name: file.name, mimeType: 'image/png', buffer: file.buffer } } })
      : await this.api.post(path, { form: data })
    const body = await res.text()
    expect(res.status(), `POST ${path}`).toBe(200)
    const error = /text-bg-danger[\s\S]*?<div class="toast-body">([^<]*)</.exec(body)
    expect(error?.[1], `POST ${path}`).toBeUndefined()
    return body
  }
}

/** name -> id of every user on the Users tab (active and deactivated). */
function userIds(settingsHtml: string): Map<string, number> {
  const ids = new Map<string, number>()
  for (const m of settingsHtml.matchAll(/href="\/user\/(\d+)"[^>]*>\s*<strong>([^<]+)<\/strong>/g)) {
    ids.set(m[2].trim(), Number(m[1]))
  }
  return ids
}

export async function seedDemo(baseURL: string, lang: Lang): Promise<Demo> {
  const api = await request.newContext({ baseURL })
  try {
    const f = new Forms(api)
    const t = T[lang]

    let ids = userIds(await f.html('/settings'))
    for (const who of Object.keys(PEOPLE) as Who[]) {
      if (ids.has(PEOPLE[who].name)) continue
      await f.post('/user/add', {
        name: PEOPLE[who].name, email: email(who), email_opt_in: '1',
        email_transactions: who === 'jonas' ? 'this_month' : 'last3',
      })
    }
    ids = userIds(await f.html('/settings'))
    const id = Object.fromEntries((Object.keys(PEOPLE) as Who[]).map((w) => [w, ids.get(PEOPLE[w].name)!])) as Record<Who, number>
    for (const who of Object.keys(PEOPLE) as Who[]) {
      await f.post(`/user/${id[who]}/edit`, {
        name: PEOPLE[who].name, email: email(who), created_at: PEOPLE[who].since, email_opt_in: who === 'felix' ? '' : '1',
        email_transactions: who === 'jonas' ? 'this_month' : 'last3',
      })
    }

    // Before any transaction: their dates are read in this timezone.
    await f.post('/settings/general', {
      default_item_rows: '3', recent_transactions_count: '5', language: lang, timezone: 'Europe/Vienna',
      site_admin_id: String(id.tina), decimal_separator: lang === 'de' ? ',' : '.', currency_symbol: '€',
    })
    await f.post('/settings/email', {
      smtp_server: 'mail.tina-office.example', smtp_port: '587', smtp_security: 'starttls',
      smtp_username: 'bank@tina-office.example', from_email: 'bank@tina-office.example', from_name: 'Bank of Tina',
      email_enabled: '1', admin_summary_email: '1',
    })
    await f.post('/settings/schedule', { schedule_enabled: '1', schedule_day: 'mon', schedule_hour: '9', schedule_minute: '0' })
    for (const name of ['Cappuccino', 'Croissant', 'Pizza Margherita', 'Sushi Bento']) {
      await f.post('/settings/common-items/add', { name })
    }
    for (const value of ['Café Sperl', 'Pizzeria Da Mario', 'Sushi Kaito']) {
      await f.post('/settings/common-descriptions/add', { value })
    }
    for (const value of ['3.90', '9.50', '14.90']) await f.post('/settings/common-prices/add', { value })
    await f.post('/settings/common-blacklist/add', { type: 'description', value: t.misc })
    await f.post('/settings/common-auto', {
      common_auto_enabled: '1', common_auto_day: '*', common_auto_hour: '2', common_auto_minute: '0',
      common_items_auto: '1', common_items_threshold: '3', common_descriptions_auto: '1',
      common_descriptions_threshold: '3', common_prices_auto: '', common_prices_threshold: '5',
    })
    await f.post('/settings/backup', {
      backup_enabled: '1', backup_admin_email: '1', backup_day: '*', backup_hour: '3', backup_minute: '0', backup_keep: '7',
    })

    if (!/\/transaction\/\d+\/edit/.test(await f.html('/transactions?year=2026&month=4'))) {
      for (const tx of transactions(t)) {
        if (tx.kind === 'expense') {
          const items = tx.items.map(([name, price, who]) => ({ name, price, debtor_id: String(id[who]) }))
          await f.post('/transaction/add', {
            transaction_type: 'expense', buyer_id: String(id[tx.buyer]), description: tx.description,
            items_json: JSON.stringify(items), date: tx.at, notes: tx.notes ?? '',
          }, tx.receipt ? { name: 'receipt.png', buffer: RECEIPT_PNG } : undefined)
        } else {
          await f.post('/transaction/add', {
            transaction_type: tx.kind, user_id: String(id[tx.who]), amount: tx.amount,
            description: tx.description, date: tx.at, notes: '',
          })
        }
      }
    }

    // Lena left after her farewell lunch.
    if (!/bg-secondary/.test(await f.html(`/user/${id.lena}`))) await f.post(`/user/${id.lena}/toggle-active`, {})

    await backups(f)
    return { ids: id }
  } finally {
    await api.dispose()
  }
}

/** Two backups made through the UI, then renamed to fixed nightly times so the
 * list does not show the time of the run. Needs DOCS_WEB_CONTAINER (the script
 * sets it); without it the Backup tab keeps whatever the run produced. */
async function backups(f: Forms): Promise<void> {
  const web = process.env.DOCS_WEB_CONTAINER
  if (!web || (await f.html('/settings')).includes(BACKUPS[1])) return
  for (let i = 0; i < BACKUPS.length; i++) await f.post('/settings/backup/create', {})
  // Container time is UTC: 01:00 UTC is 03:00 in Vienna (CEST).
  const rename = BACKUPS.map((name, i) => `mv "$${i + 1}" ${name} && touch -d '${name.slice(11, 21).replaceAll('_', '-')} 01:00:00' ${name}`)
  execFileSync('docker', ['exec', web, 'sh', '-c', `cd /backups && set -- $(ls bot_backup_*.tar.gz | sort) && ${rename.join(' && ')}`])
}
