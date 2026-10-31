import { expect, test } from './fixtures'

/* The PWA bits: manifest and icons, the service worker and its offline page,
 * plus the navbar on desktop and on a phone. */

test.describe('service worker', () => {
  test.use({ serviceWorkers: 'allow' })

  test('installs, and shows the offline page when the network is gone', async ({ page, context, guard }) => {
    // Chromium logs the failed navigation request while offline.
    guard.allow(/ERR_INTERNET_DISCONNECTED|Failed to load resource/)
    await page.goto('/')
    await page.evaluate(() => navigator.serviceWorker.ready)
    await expect.poll(() => page.evaluate(() => caches.has('bot-v3'))).toBe(true)
    await context.setOffline(true)
    await page.goto('/transactions').catch(() => {})
    await expect(page.getByRole('heading', { name: "You're offline" })).toBeVisible()
    await context.setOffline(false)
    await page.getByRole('link', { name: 'Retry' }).click()
    await expect(page).toHaveURL('/')
    await expect(page.getByText('User Balances')).toBeVisible()
  })
})

test('manifest, theme colour and icons are linked', async ({ page, request }) => {
  await page.goto('/')
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute('href', '/manifest.json')
  const manifest = await (await request.get('/manifest.json')).json()
  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute('content', manifest.theme_color)
  for (const icon of manifest.icons) {
    const res = await request.get(icon.src)
    expect(res.status(), icon.src).toBe(200)
    expect(res.headers()['content-type']).toBe('image/png')
  }
  expect((await request.get((await page.locator('link[rel="apple-touch-icon"]').getAttribute('href'))!)).status()).toBe(200)
})

test('navbar links and brand', async ({ page }) => {
  await page.goto('/settings')
  const nav = page.getByRole('navigation')
  for (const [name, url, title] of [
    ['Add Transaction', '/transaction/add', 'Add Transaction'],
    ['All Transactions', '/transactions', 'Transactions'],
    ['Charts', '/analytics', 'Charts & Statistics'],
    ['Settings', '/settings', 'Settings'],
    ['Dashboard', '/', 'Dashboard'],
  ]) {
    await nav.getByRole('link', { name, exact: true }).click()
    await expect(page).toHaveURL(url)
    await expect(page).toHaveTitle(new RegExp(`^${title} [-–] Bank of Tina$`))
  }
  await page.goto('/search')
  await nav.getByRole('link', { name: 'Bank of Tina' }).click()
  await expect(page).toHaveURL('/')
})

test('phone: the menu collapses behind the toggler', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  const link = page.getByRole('navigation').getByRole('link', { name: 'Charts' })
  await expect(link).toBeHidden()
  await page.getByRole('button', { name: 'Toggle navigation' }).click()
  await expect(link).toBeVisible()
  await link.click()
  await expect(page).toHaveURL('/analytics')
})
