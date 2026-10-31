import { expect, expectToast, test, uid } from './fixtures'

/* Users: add (Settings → Users), validation, detail page, the edit dialog,
 * deactivate/reactivate from both places, history pagination. */

test('add a user from Settings → Users', async ({ page }) => {
  const id = uid()
  const name = `Ben Probe ${id}`
  await page.goto('/settings?tab=users')
  await page.locator('#tab-users').getByLabel('Name', { exact: true }).fill(name)
  await page.locator('#tab-users').getByLabel('Email', { exact: true }).fill(`ben.${id}@e2e.example`)
  await page.getByLabel('Send weekly balance email').uncheck()
  await page.getByLabel('Include in email').selectOption('this_week')
  await page.locator('#tab-users').getByRole('button', { name: 'Add' }).click()

  await expectToast(page, `User ${name} added successfully!`)
  await expect(page.locator('#tab-users')).toHaveClass(/active/)
  const row = page.locator('#tab-users tr').filter({ hasText: name })
  await expect(row).toContainText(`ben.${id}@e2e.example`)
  await expect(row).toContainText('€0.00')

  // On the dashboard, in the transaction forms, and the options were stored.
  await page.goto('/')
  await expect(page.getByRole('link', { name })).toBeVisible()
  await page.goto('/transaction/add')
  await expect(page.getByLabel('Who paid?').locator('option', { hasText: name })).toBeAttached()
  await page.goto('/settings?tab=users')
  await page.locator('#tab-users').getByRole('link', { name }).click()
  await page.getByRole('button', { name: 'Edit User' }).click()
  await expect(page.getByLabel('Send weekly balance email')).not.toBeChecked()
  await expect(page.getByLabel('Include in email')).toHaveValue('this_week')
})

test('add user: validation messages', async ({ page, app }) => {
  const taken = await app.addUser()
  const tryAdd = async (name: string, email: string, message: string) => {
    await page.goto('/settings?tab=users')
    await page.locator('#tab-users').getByLabel('Name', { exact: true }).fill(name)
    await page.locator('#tab-users').getByLabel('Email', { exact: true }).fill(email)
    await page.locator('#tab-users').getByRole('button', { name: 'Add' }).click()
    await expectToast(page, message)
  }
  const id = uid()
  await tryAdd(taken.name.toUpperCase(), `x.${id}@e2e.example`, 'Another user with that name already exists!')
  await tryAdd(`Cleo ${id}`, taken.email.toUpperCase(), 'Another user with that email already exists!')
  await tryAdd(`Cleo ${id}`, `cleo@localhost`, 'Please enter a valid email address.')
  await tryAdd(`C${'l'.repeat(100)} ${id}`, `cleo.${id}@e2e.example`, 'Name and email can be at most 100 characters.')
  // Required fields: the browser stops an empty form.
  await page.goto('/settings?tab=users')
  await page.locator('#tab-users').getByRole('button', { name: 'Add' }).click()
  await expect(page.locator('#new_user_name:invalid')).toHaveCount(1)
  // Whitespace only gets past the browser but not the server.
  expect(await app.post('/user/add', { name: '  ', email: ' ' }, { error: true })).toContain('Name and email are required!')
  await page.goto(`/search?q=Cleo+${id}`)
  await expect(page.getByLabel('User', { exact: true }).locator('option', { hasText: `Cleo ${id}` })).toHaveCount(0)
})

test('user detail: details, history with paid/received, items and notes', async ({ page, app }) => {
  const [buyer, a] = [await app.addUser(), await app.addUser()]
  const id = uid()
  // Explicit dates: MariaDB keeps whole seconds, so two "now"s can tie.
  await app.expense(buyer, `Curry ${id}`, [['Curry', '9.90', a]], { notes: 'Extra spicy', date: '2036-02-02T12:00' })
  await app.deposit(a, '15', `Top-up ${id}`, { date: '2036-02-03T09:00' })
  await page.goto('/')
  await page.getByRole('link', { name: a.name }).click()
  await expect(page).toHaveURL(`/user/${a.id}`)
  await expect(page).toHaveTitle(`${a.name} - Bank of Tina`)
  await expect(page.getByText(a.email)).toBeVisible()
  await expect(page.locator('h4')).toHaveText('€5.10')
  await expect(page.locator('h4')).toHaveClass(/balance-positive/)
  await expect(page.locator('dl')).toContainText(`Member since: ${new Date().toISOString().slice(0, 4)}-`)
  const items = page.locator('.list-group-item')
  await expect(items).toHaveCount(2)
  await expect(items.nth(0)).toContainText(`Top-up ${id}`)
  await expect(items.nth(0)).toContainText('Received €15.00')
  await expect(items.nth(1)).toContainText(`Paid €9.90 to ${buyer.name}`)
  await expect(items.nth(1)).toContainText('Items: Curry (€9.90)')
  await expect(items.nth(1)).toContainText('Extra spicy')
  await page.goto(`/user/${buyer.id}`)
  await expect(page.locator('.list-group-item')).toContainText(`Received €9.90 from ${a.name}`)
  await page.getByRole('link', { name: 'Back to Dashboard' }).click()
  await expect(page).toHaveURL('/')
})

test('edit and delete a transaction from the user page', async ({ page, app }) => {
  const u = await app.addUser()
  const desc = `Snack ${uid()}`
  await app.deposit(u, '4', desc)
  await page.goto(`/user/${u.id}`)
  await page.getByRole('link', { name: 'Edit' }).click()
  await expect(page.getByLabel('Description')).toHaveValue(desc)
  await page.goBack()
  const dialogs: string[] = []
  page.on('dialog', (d) => {
    dialogs.push(d.message())
    void d.accept()
  })
  await page.getByRole('button', { name: 'Delete' }).click()
  await expectToast(page, 'Transaction deleted.')
  expect(dialogs).toEqual(['Delete this transaction? Balances will be reversed.'])
  await page.goto(`/user/${u.id}`)
  await expect(page.getByText('No transactions yet for this user.')).toBeVisible()
  await expect(page.locator('h4')).toHaveText('€0.00')
})

test('user detail: empty history and pagination', async ({ page, app }) => {
  const u = await app.addUser()
  await page.goto(`/user/${u.id}`)
  await expect(page.getByText('No transactions yet for this user.')).toBeVisible()
  for (let i = 1; i <= 22; i++) await app.deposit(u, '1', `Coin ${i}`, { date: `2035-02-${String(i).padStart(2, '0')}T08:00` })
  await page.goto(`/user/${u.id}`)
  await expect(page.locator('.list-group-item')).toHaveCount(20)
  await page.getByRole('link', { name: 'Next' }).click()
  await expect(page).toHaveURL(`/user/${u.id}?page=2`)
  await expect(page.locator('.list-group-item')).toHaveCount(2)
  await expect(page.locator('.page-item.active')).toHaveText('2')
})

test('edit dialog: change everything, validation, cancel', async ({ page, app }) => {
  const [u, other] = [await app.addUser(), await app.addUser()]
  await page.goto(`/user/${u.id}`)
  const dialog = page.getByRole('dialog', { name: 'Edit User' })
  await page.getByRole('button', { name: 'Edit User' }).click()
  await expect(dialog).toBeVisible()
  await expect(dialog.getByLabel('Name', { exact: true })).toHaveValue(u.name)
  await dialog.getByLabel('Name', { exact: true }).fill('Changed')
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(dialog).toBeHidden()

  await page.getByRole('button', { name: 'Edit User' }).click()
  await dialog.getByLabel('Email', { exact: true }).fill(other.email)
  await dialog.getByRole('button', { name: 'Save Changes' }).click()
  await expectToast(page, 'Another user with that email already exists!')

  const id = uid()
  await page.getByRole('button', { name: 'Edit User' }).click()
  await dialog.getByLabel('Name', { exact: true }).fill(`Dora Probe ${id}`)
  await dialog.getByLabel('Email', { exact: true }).fill(`dora.${id}@e2e.example`)
  await dialog.getByLabel('Member since').fill('2024-02-29')
  await dialog.getByLabel('Send weekly balance email').uncheck()
  await dialog.getByLabel('Include in email').selectOption('none')
  await dialog.getByRole('button', { name: 'Save Changes' }).click()
  await expectToast(page, 'User updated successfully!')
  await expect(page.locator('.card-header').first()).toContainText(`Dora Probe ${id}`)
  await expect(page.getByText(`dora.${id}@e2e.example`)).toBeVisible()
  await expect(page.getByText('2024-02-29')).toBeVisible()
  await page.getByRole('button', { name: 'Edit User' }).click()
  await expect(dialog.getByLabel('Send weekly balance email')).not.toBeChecked()
  await expect(dialog.getByLabel('Include in email')).toHaveValue('none')
  await dialog.getByRole('button', { name: 'Close' }).click()
  await expect(dialog).toBeHidden()

  // Server-side checks the browser cannot catch.
  expect(await app.post(`/user/${u.id}/edit`, { name: 'X', email: 'x@e2e.example', created_at: '' }, { error: true })).toContain('All fields are required!')
  expect(await app.post(`/user/${u.id}/edit`, { name: 'X', email: 'x@e2e.example', created_at: '29.02.2024' }, { error: true })).toContain('Invalid date format!')
})

test('deactivate and reactivate on the detail page', async ({ page, app }) => {
  const u = await app.addUser()
  await page.goto(`/user/${u.id}`)
  await page.getByRole('button', { name: 'Deactivate User' }).click()
  await expectToast(page, `User ${u.name} has been deactivated.`)
  await expect(page).toHaveURL(`/user/${u.id}`)
  await expect(page.getByText('Inactive', { exact: true })).toBeVisible()
  // Gone from the dashboard, the forms, search and charts; still listed in Settings.
  for (const path of ['/', '/transaction/add', '/search', '/analytics']) {
    await page.goto(path)
    await expect(page.getByText(u.name)).toHaveCount(0)
  }
  await page.goto('/settings?tab=users')
  await expect(page.getByText('Deactivated Users')).toBeVisible()
  await page.goto(`/user/${u.id}`)
  await page.getByRole('button', { name: 'Reactivate User' }).click()
  await expectToast(page, `User ${u.name} has been activated.`)
  await expect(page.getByText('Inactive', { exact: true })).toHaveCount(0)
  await page.goto('/')
  await expect(page.getByRole('link', { name: u.name })).toBeVisible()
})

test('deactivate (with confirm) and reactivate on the Users tab', async ({ page, app }) => {
  const u = await app.addUser()
  await page.goto('/settings?tab=users')
  const active = page.locator('#tab-users .card').filter({ hasText: 'Active Users' }).locator('tr').filter({ hasText: u.name })
  page.once('dialog', (d) => void d.dismiss())
  await active.getByRole('button', { name: 'Deactivate' }).click()
  await expect(active).toBeVisible()
  let message = ''
  page.once('dialog', (d) => {
    message = d.message()
    void d.accept()
  })
  await active.getByRole('button', { name: 'Deactivate' }).click()
  await expectToast(page, `User ${u.name} has been deactivated.`)
  expect(message).toBe(`Deactivate ${u.name}?`)
  await expect(page).toHaveURL(/\/settings/)
  const deactivated = page.locator('#tab-users .card').filter({ hasText: 'Deactivated Users' }).locator('tr').filter({ hasText: u.name })
  await expect(deactivated).toBeVisible()
  await deactivated.getByRole('button', { name: 'Reactivate' }).click()
  await expectToast(page, `User ${u.name} has been activated.`)
  await expect(page.locator('#tab-users .card').filter({ hasText: 'Active Users' }).locator('tr').filter({ hasText: u.name })).toBeVisible()
})

test('unknown user ids answer 404 on every user action', async ({ app }) => {
  for (const path of ['/user/99999999/edit', '/user/99999999/toggle-active']) {
    const res = await app.api.post(path, { form: { name: 'x', email: 'x@e2e.example', created_at: '2024-01-01' } })
    expect(res.status(), path).toBe(400) // no CSRF token: refused before the lookup
  }
  // With a token: 404.
  const token = /<meta name="csrf-token" content="([^"]+)"/.exec(await app.html('/search'))![1]
  for (const path of ['/user/99999999/edit', '/user/99999999/toggle-active', '/transaction/99999999/delete', '/transaction/99999999/edit']) {
    const res = await app.api.post(path, { form: { csrf_token: token, name: 'x', email: 'x@e2e.example', created_at: '2024-01-01' } })
    expect(res.status(), path).toBe(404)
  }
})
