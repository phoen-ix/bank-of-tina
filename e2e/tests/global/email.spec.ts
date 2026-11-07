import { App, expect, expectToast, GENERAL, test, uid } from '../fixtures'
import type { APIRequestContext, Page } from '@playwright/test'

/* Settings → Email: credentials, Send Now against the stack's Mailpit (its API
 * on MAILPIT_URL, set by scripts/e2e.sh), the debug log, the auto-schedule.
 * Global settings: serial project, baseline restored after each test. */

const MAILPIT = process.env.MAILPIT_URL ?? ''
const SMTP = {
  smtp_server: 'mailpit', smtp_port: '1025', smtp_security: 'none', smtp_username: 'e2e',
  smtp_password: 'e2e-smtp-not-a-secret', from_email: 'bank@e2e.example', from_name: 'Bank of Tina',
  // The weekly email's unsubscribe link points here.
  smtp_ehlo_name: '', app_url: process.env.E2E_BASE_URL ?? 'http://localhost:24100',
  email_enabled: '1', email_debug: '', admin_summary_email: '',
}

interface Mail { ID: string; Subject: string; To: Array<{ Address: string }> }

async function mails(api: APIRequestContext, to: string): Promise<Mail[]> {
  const res = await api.get(`${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:"${to}"`)}`)
  expect(res.ok()).toBe(true)
  return (await res.json()).messages
}

async function sendNow(page: Page) {
  await page.goto('/settings?tab=email')
  await page.getByRole('button', { name: 'Send Emails Now' }).click()
}

test.skip(!MAILPIT, 'needs the Mailpit of scripts/e2e.sh (MAILPIT_URL)')

test.afterEach(async ({ app }) => {
  await app.post('/settings/email', SMTP)
  await app.post('/settings/general', GENERAL)
  await app.post('/settings/email/clear-log', {})
})

test.beforeAll(async ({ playwright }, info) => {
  const api = await playwright.request.newContext({ baseURL: info.project.use.baseURL, extraHTTPHeaders: { 'X-Forwarded-For': '10.254.0.1' } })
  await new App(api).post('/settings/email', SMTP)
  await api.dispose()
})

test('credentials form: saved, password kept when left blank, port suggestion', async ({ page }) => {
  await page.goto('/settings?tab=email')
  await expect(page.getByLabel('SMTP Server')).toHaveValue('mailpit')
  await expect(page.getByLabel('SMTP Password')).toHaveValue('')
  await expect(page.getByLabel('SMTP Password')).toHaveAttribute('placeholder', '•••••••••')
  await expect(page.getByText('Leave blank to keep the existing password.')).toBeVisible()
  // Picking an encryption suggests its usual port while the port is still a default one.
  await page.getByLabel('SMTP Port').fill('587')
  await page.getByLabel('Encryption').selectOption('ssl')
  await expect(page.getByLabel('SMTP Port')).toHaveValue('465')
  await page.getByLabel('SMTP Port').fill('2525')
  await page.getByLabel('Encryption').selectOption('starttls')
  await expect(page.getByLabel('SMTP Port')).toHaveValue('2525')

  await page.getByLabel('Encryption').selectOption('none')
  await page.getByLabel('SMTP Port').fill('1025')
  await page.getByLabel('From Name').fill('Tina’s Bank')
  await expect(page.getByText('The name the app gives the SMTP server in EHLO. Empty: the domain of the From Email.')).toBeVisible()
  await page.getByLabel('EHLO Name').fill('mx.e2e.example')
  await expect(page.getByLabel('Site URL')).toHaveValue(SMTP.app_url)
  await expect(page.getByText(/^The public address of the app\. With it, the weekly email carries an unsubscribe link/)).toBeVisible()
  await page.getByRole('button', { name: 'Save Settings' }).click()
  await expectToast(page, 'Settings saved.')
  await expect(page.getByLabel('From Name')).toHaveValue('Tina’s Bank')
  await expect(page.getByLabel('EHLO Name')).toHaveValue('mx.e2e.example')
  await expect(page.getByLabel('Encryption')).toHaveValue('none')
  // The blank password field did not wipe the stored password: sending still logs in.
  await sendNow(page)
  await expectToast(page, /^\d+ email\(s\) sent, 0 failed\.$/)
})

test('invalid port, EHLO name and site URL are refused by the server', async ({ app }) => {
  expect(await app.post('/settings/email', { ...SMTP, smtp_port: '70000' }, { error: true })).toContain('SMTP port must be a number between 1 and 65535.')
  expect(await app.post('/settings/email', { ...SMTP, smtp_ehlo_name: 'mx e2e' }, { error: true })).toContain('The EHLO name may only contain letters, digits, dots and hyphens.')
  expect(await app.post('/settings/email', { ...SMTP, app_url: 'tina.e2e.example' }, { error: true })).toContain('The site URL must start with http:// or https://.')
})

test('Send Now: every opted-in user gets their balance, the admin a summary', async ({ page, app, request }) => {
  const [a, quiet, admin] = [await app.addUser(), await app.addUser({ optIn: false }), await app.addUser()]
  await app.deposit(a, '12.34', `Mail ${uid()}`)
  await app.post('/settings/general', { ...GENERAL, site_admin_id: String(admin.id) })
  await app.post('/settings/email', { ...SMTP, email_debug: '1', admin_summary_email: '1' })
  await sendNow(page)
  await expectToast(page, /^\d+ email\(s\) sent, 0 failed\.$/)

  const [mail] = await mails(request, a.email)
  expect(mail.Subject).toMatch(/Bank of Tina/)
  const html = await (await request.get(`${MAILPIT}/view/${mail.ID}.html`)).text()
  expect(html).toContain(a.name)
  expect(html).toContain('€12.34')
  expect(await mails(request, quiet.email)).toHaveLength(0)
  // The admin gets the summary, which lists everyone else.
  const summary = (await mails(request, admin.email)).find((m) => m.Subject.includes('Admin Summary'))!
  const table = await (await request.get(`${MAILPIT}/view/${summary.ID}.html`)).text()
  expect(table).toContain('All Active Users')
  expect(table).toContain(a.name)
  expect(table).not.toContain(a.email) // emails only when the template says so

  // Debug mode: the log card lists the run.
  await page.goto('/settings?tab=email')
  const log = page.locator('.card').filter({ has: page.getByText('Email Debug Log') })
  await expect(log.locator('pre')).toContainText(`[SUCCESS] ${a.name} <${a.email}>`)
  await expect(log.locator('pre')).toContainText(`Admin summary sent to ${admin.name}`)
  page.once('dialog', (d) => void d.accept())
  await log.getByRole('button', { name: 'Clear Log' }).click()
  await expectToast(page, 'Email debug log cleared.')
  await expect(page.getByText('No log entries yet. Send emails to generate log entries.')).toBeVisible()
})

test('unsubscribe: the link asks first, its button and the one-click POST stop the weekly email', async ({ page, app, request }) => {
  const [a, b] = [await app.addUser(), await app.addUser()]
  await sendNow(page)
  await expectToast(page, /^\d+ email\(s\) sent, 0 failed\.$/)
  const link = async (to: string) => {
    const [mail] = await mails(request, to)
    const headers = await (await request.get(`${MAILPIT}/api/v1/message/${mail.ID}/headers`)).json()
    expect(headers['List-Unsubscribe-Post']).toEqual(['List-Unsubscribe=One-Click'])
    expect(headers['Auto-Submitted']).toEqual(['auto-generated'])
    const text: string = (await (await request.get(`${MAILPIT}/api/v1/message/${mail.ID}`)).json()).Text
    const path = /\/unsubscribe\/[\w.-]+/.exec(text)?.[0]
    expect(path, 'the unsubscribe link in the text part').toBeTruthy()
    expect(headers['List-Unsubscribe'][0]).toContain(path!)
    return path!
  }

  await page.goto(await link(a.email))
  await expect(page.getByText(`Stop the weekly balance email to ${a.email}?`)).toBeVisible()
  await page.getByRole('button', { name: 'Unsubscribe' }).click()
  await expect(page.getByText(`${a.name} no longer gets the weekly balance email.`)).toBeVisible()
  const res = await app.api.post(await link(b.email), { form: { 'List-Unsubscribe': 'One-Click' } })
  expect(res.status()).toBe(200)

  await sendNow(page)
  await expectToast(page, /^\d+ email\(s\) sent, 0 failed\.$/)
  expect(await mails(request, a.email)).toHaveLength(1)
  expect(await mails(request, b.email)).toHaveLength(1)
})

test('a broken SMTP server: every send fails, and the failures are logged', async ({ page, app }) => {
  const a = await app.addUser()
  await app.post('/settings/email', { ...SMTP, smtp_port: '1026' })
  await sendNow(page)
  await expectToast(page, /^0 email\(s\) sent, \d+ failed\.$/)
  // Failures are logged even without debug mode; the log card shows with it.
  await app.post('/settings/email', { ...SMTP, smtp_port: '1026', email_debug: '1' })
  await page.goto('/settings?tab=email')
  await expect(page.locator('pre')).toContainText(`[FAIL] ${a.name} <${a.email}>`)
  await expect(page.locator('pre')).toContainText('Connection refused')
})

test('sending switched off: Send Now does nothing', async ({ page, app, request }) => {
  const a = await app.addUser()
  await app.post('/settings/email', { ...SMTP, email_enabled: '' })
  await page.goto('/settings?tab=email')
  await expect(page.getByLabel('Enable email sending')).not.toBeChecked()
  await sendNow(page)
  await expectToast(page, '0 email(s) sent, 0 failed.')
  expect(await mails(request, a.email)).toHaveLength(0)
})

test('auto-schedule: enable, the summary line, disable', async ({ page }) => {
  await page.goto('/settings?tab=email')
  const fields = page.locator('#schedule_fields')
  await expect(fields).toBeHidden()
  await page.getByLabel('Enable automatic schedule').check()
  await expect(fields).toBeVisible()
  const tab = page.locator('#tab-email')
  await tab.getByLabel('Day').selectOption('wed')
  await tab.getByLabel('Time (24-hour)').selectOption('7')
  await tab.getByLabel('Minute').selectOption('30')
  await page.getByRole('button', { name: 'Save Schedule' }).click()
  await expectToast(page, 'Schedule saved and enabled.')
  await expect(page.getByText('Emails will be sent every Wednesday at 07:30 (Europe/Vienna).')).toBeVisible()
  await page.getByLabel('Enable automatic schedule').uncheck()
  await expect(fields).toBeHidden()
  await page.getByRole('button', { name: 'Save Schedule' }).click()
  await expectToast(page, 'Schedule disabled.')
  await expect(page.getByText('Emails will be sent')).toHaveCount(0)
})

