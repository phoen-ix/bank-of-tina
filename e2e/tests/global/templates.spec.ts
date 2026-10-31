import { expect, expectToast, GENERAL, PNG, test, uid } from '../fixtures'

/* Settings → Templates: theme presets and colour pickers, the email texts and
 * their previews, reset to defaults, and the app icon. Global settings: the
 * serial project; every test resets templates and the icon when done. */

test.afterEach(async ({ app }) => {
  await app.post('/settings/templates/reset', {})
  await app.post('/settings/icon', { action: 'reset' })
  await app.post('/settings/general', GENERAL)
})

const rgb = (hex: string) => `rgb(${[1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(', ')})`

test('preset theme fills the pickers and recolours the app', async ({ page }) => {
  await page.goto('/settings?tab=templates')
  await expect(page.getByLabel('Preset theme')).toHaveValue('default')
  await page.getByLabel('Preset theme').selectOption('forest')
  const navbar = await page.getByLabel('Navbar color').inputValue()
  await expect(page.locator('#color_navbar_hex')).toHaveValue(navbar)
  await page.getByRole('button', { name: 'Save Templates' }).click()
  await expectToast(page, 'Templates saved.')
  await expect(page.getByLabel('Preset theme')).toHaveValue('forest')
  await expect(page.locator('nav.navbar')).toHaveCSS('background-color', rgb(navbar))
  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute('content', navbar)
  expect((await (await page.request.get('/manifest.json')).json()).theme_color).toBe(navbar)
})

test('custom colours: hex box and picker stay in sync, the preset turns Custom', async ({ page, app }) => {
  await page.goto('/settings?tab=templates')
  await page.locator('#color_navbar_hex').fill('#123456')
  await expect(page.getByLabel('Navbar color')).toHaveValue('#123456')
  await expect(page.getByLabel('Preset theme')).toHaveValue('custom')
  await page.getByLabel('Negative balance color').fill('#aa0011')
  await expect(page.locator('#color_balance_negative_hex')).toHaveValue('#aa0011')
  await page.getByRole('button', { name: 'Save Templates' }).click()
  await expectToast(page, 'Templates saved.')
  await expect(page.locator('nav.navbar')).toHaveCSS('background-color', 'rgb(18, 52, 86)')
  // A negative balance uses the new colour.
  const u = await app.addUser()
  await app.withdrawal(u, '1', `Red ${uid()}`)
  await page.goto(`/user/${u.id}`)
  await expect(page.locator('h4.balance-negative')).toHaveCSS('color', 'rgb(170, 0, 17)')
})

test('weekly email text: placeholders, blank lines, preview, reset with confirm', async ({ page, context, app }) => {
  await app.addUser() // the preview needs an active user
  await page.goto('/settings?tab=templates')
  await page.getByLabel('Greeting').fill('Servus [Name]!')
  await page.getByLabel('Intro line').first().fill('')
  await page.getByLabel('Footer line 2').fill('Your balance: [Balance] ([BalanceStatus]) on [Date]')
  await page.getByRole('button', { name: 'Save Templates' }).click()
  await expectToast(page, 'Templates saved.')
  await expect(page.getByLabel('Greeting')).toHaveValue('Servus [Name]!')

  const preview = context.waitForEvent('page')
  await page.locator('.card').filter({ hasText: 'Weekly Balance Email' }).getByRole('link', { name: 'Preview' }).click()
  const tab = await preview
  // The preview shows the first active user by name; check the template, not the person.
  await expect(tab.getByText(/^Servus .+!$/)).toBeVisible()
  await expect(tab.getByText(/Your balance: €-?[\d.]+ \(.+\) on \d{4}-\d{2}-\d{2}/)).toBeVisible()
  await expect(tab.getByText("Here's your weekly update from the Bank of Tina:")).toHaveCount(0)
  await tab.close()

  let message = ''
  page.once('dialog', (d) => {
    message = d.message()
    void d.accept()
  })
  await page.getByRole('button', { name: /Reset to Defaults$/ }).click()
  await expectToast(page, 'Templates reset to defaults.')
  expect(message).toBe('Reset all templates and colors to defaults?')
  await expect(page.getByLabel('Greeting')).toHaveValue('Hi [Name],')
})

test('templates are kept per language', async ({ page, app }) => {
  await app.post('/settings/templates', { tpl_email_subject: 'English subject', color_navbar: '#0d6efd' })
  await app.post('/settings/general', { ...GENERAL, language: 'de' })
  await page.goto('/settings?tab=templates')
  await expect(page.getByLabel('Betreff').first()).toHaveValue('Bank of Tina - Wöchentliches Saldo-Update ([Date])')
  await app.post('/settings/general', GENERAL)
  await page.goto('/settings?tab=templates')
  await expect(page.getByLabel('Subject').first()).toHaveValue('English subject')
})

test('admin summary and backup previews; email addresses in the summary', async ({ page, app }) => {
  const u = await app.addUser()
  await page.goto('/settings/templates/preview/admin-summary')
  await expect(page.getByText(u.name)).toBeVisible()
  await expect(page.getByText(u.email)).toHaveCount(0)
  await page.goto('/settings?tab=templates')
  await page.getByLabel('Include email addresses in summary table').check()
  await page.getByRole('button', { name: 'Save Templates' }).click()
  await expectToast(page, 'Templates saved.')
  await page.goto('/settings/templates/preview/admin-summary')
  await expect(page.getByText(u.email)).toBeVisible()
  await app.post('/settings/templates', { color_navbar: '#0d6efd' }) // switch off again
  await page.goto('/settings/templates/preview/backup')
  await expect(page.getByText(/bot_backup_\d{4}_\d{2}_\d{2}_03-00-00\.tar\.gz/)).toBeVisible()
})

test('app icon: regenerate, upload, refuse bad files, reset', async ({ page }) => {
  await page.goto('/settings?tab=templates')
  const icon = page.getByRole('img', { name: 'Current app icon' })
  const before = await icon.getAttribute('src')
  await page.getByRole('button', { name: 'Regenerate with Navbar Color' }).click()
  await expectToast(page, 'Icon regenerated with current navbar color.')
  await expect(icon).not.toHaveAttribute('src', before!)
  await expect.poll(() => icon.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBe(192)

  const upload = page.locator('form').filter({ has: page.locator('input[name="icon_file"]') })
  await upload.getByRole('button', { name: 'Upload' }).click()
  await expectToast(page, 'No file selected.')
  await upload.locator('input[name="icon_file"]').setInputFiles({ name: 'logo.gif', mimeType: 'image/gif', buffer: Buffer.from('GIF89a') })
  await upload.getByRole('button', { name: 'Upload' }).click()
  await expectToast(page, 'Only PNG or JPG files are accepted.')
  await upload.locator('input[name="icon_file"]').setInputFiles({ name: 'logo.png', mimeType: 'image/png', buffer: Buffer.from('not a png') })
  await upload.getByRole('button', { name: 'Upload' }).click()
  await expectToast(page, /^Failed to process image: /)
  await upload.locator('input[name="icon_file"]').setInputFiles({ name: 'logo.png', mimeType: 'image/png', buffer: PNG })
  await upload.getByRole('button', { name: 'Upload' }).click()
  await expectToast(page, 'Custom icon uploaded.')
  const res = await page.request.get('/static/icons/icon-512.png')
  expect(res.headers()['content-type']).toBe('image/png')

  await page.getByRole('button', { name: /Reset to Default$/ }).click()
  await expectToast(page, 'Icon reset to default.')
})
