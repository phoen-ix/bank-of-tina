import { App, expect, expectToast, test, uid } from './fixtures'

/* Error states that are not a validation message of one form: the per-client
 * rate limit and a form without its CSRF token. (404s: sweep.spec.ts.) */

test('rate limit: the 11th new user within a minute is refused with a message', async ({ page, app }) => {
  for (let i = 0; i < 10; i++) await app.addUser()
  const name = `Over Limit ${uid()}`
  await page.goto('/settings?tab=users')
  await page.locator('#tab-users').getByLabel('Name', { exact: true }).fill(name)
  await page.locator('#tab-users').getByLabel('Email', { exact: true }).fill(`over.${uid()}@e2e.example`)
  await page.locator('#tab-users').getByRole('button', { name: 'Add' }).click()
  await expectToast(page, 'Too many requests. Please wait and try again.')
  // Back where the form was, and nobody was added.
  await expect(page).toHaveURL('/settings?tab=users')
  await expect(page.getByText(name)).toHaveCount(0)
})

test('rate limit is per client: another client can still add users', async ({ app, playwright, baseURL }) => {
  for (let i = 0; i < 10; i++) await app.addUser()
  const other = await playwright.request.newContext({ baseURL, extraHTTPHeaders: { 'X-Forwarded-For': '10.255.0.1' } })
  await new App(other).addUser()
  await other.dispose()
})

test('a form posted without its CSRF token is refused with a message', async ({ page, app }) => {
  const u = await app.addUser()
  await page.goto(`/user/${u.id}`)
  await page.locator('input[name="csrf_token"]').evaluateAll((els) => els.forEach((e) => e.remove()))
  const res = page.waitForResponse((r) => r.url().endsWith('/toggle-active'))
  await page.getByRole('button', { name: 'Deactivate User' }).click()
  expect((await res).status()).toBe(302)
  await expectToast(page, 'The form has expired. Please submit it again.')
  await expect(page).toHaveURL(`/user/${u.id}`)
  expect(await app.balance(u)).toBe('€0.00')
  await page.goto(`/user/${u.id}`)
  await expect(page.getByText('Inactive', { exact: true })).toHaveCount(0)
})
