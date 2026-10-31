import { acceptNextDialog, expect, expectToast, PNG, test, uid } from './fixtures'

/* All Transactions (month view), editing and deleting. Each test writes into a
 * month nobody else uses (app.freeMonth()), so counts and totals are its own. */

const pad = (n: number) => String(n).padStart(2, '0')
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

test('month view: day groups, details, totals per type, user links', async ({ page, app }) => {
  const [y, m] = await app.freeMonth()
  const [buyer, a] = [await app.addUser(), await app.addUser()]
  const id = uid()
  await app.expense(buyer, `Sushi ${id}`, [['Maki', '12.40', a], ['Miso', '3.80', a]], { date: `${y}-${pad(m)}-03T12:15`, notes: 'Birthday', receipt: { name: 'r.png', mimeType: 'image/png', buffer: PNG } })
  await app.deposit(a, '30', `Top-up ${id}`, { date: `${y}-${pad(m)}-10T09:00` })
  await app.withdrawal(buyer, '5.25', `Payout ${id}`, { date: `${y}-${pad(m)}-10T17:45` })

  await page.goto(`/transactions?year=${y}&month=${m}`)
  await expect(page.getByText(`${MONTHS[m - 1]} ${y}`, { exact: true })).toBeVisible()
  const weekday = new Date(Date.UTC(y, m - 1, 10)).toLocaleDateString('en-GB', { weekday: 'long', timeZone: 'UTC' })
  await expect(page.getByRole('heading', { name: `${weekday}, 10 ${MONTHS[m - 1]}` })).toBeVisible() // "Friday, 10 June"
  const expense = page.getByRole('row').filter({ hasText: `Sushi ${id}` })
  await expect(expense).toContainText('12:15')
  await expect(expense).toContainText('expense')
  await expect(expense).toContainText('€16.20')
  await expect(expense.getByRole('link', { name: a.name })).toHaveAttribute('href', `/user/${a.id}`)
  await expect(expense.getByRole('link', { name: 'View' })).toHaveAttribute('href', /\/receipt\//)
  await expect(page.getByText('Maki (€12.40), Miso (€3.80)')).toBeVisible()
  await expect(page.getByText('Birthday')).toBeVisible()
  await expect(page.locator('.card-footer')).toHaveText(/3 transaction\(s\)\s*· Deposit: €30.00\s*· Expense: €16.20\s*· Withdrawal: €5.25/)
  await expense.getByRole('link', { name: buyer.name }).click()
  await expect(page).toHaveURL(`/user/${buyer.id}`)
})

test('month navigation: previous/next, jump selects, current month', async ({ page, app }) => {
  // A transaction in 2024 makes the year select start there.
  await app.deposit(await app.addUser(), '1', `Old ${uid()}`, { date: '2024-05-02T10:00' })
  await page.goto('/transactions')
  const now = new Date()
  await expect(page.getByRole('button', { name: 'Next month' })).toBeDisabled()
  await expect(page.getByLabel('Month', { exact: true })).toHaveValue(String(now.getMonth() + 1))
  await page.getByRole('link', { name: 'Previous month' }).click()
  const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1)
  await expect(page).toHaveURL(`/transactions?year=${prev.getFullYear()}&month=${prev.getMonth() + 1}`)
  await page.getByRole('link', { name: 'Next month' }).click()
  await expect(page.getByRole('button', { name: 'Next month' })).toBeDisabled()

  const other = now.getMonth() === 1 ? 3 : 2
  await page.getByLabel('Month', { exact: true }).selectOption(String(other))
  await expect(page).toHaveURL(`/transactions?year=${now.getFullYear()}&month=${other}`)
  await page.getByLabel('Year', { exact: true }).selectOption('2024')
  await expect(page).toHaveURL(`/transactions?year=2024&month=${other}`)

  await page.goto('/transactions?year=2045&month=12')
  await page.getByRole('link', { name: 'Next month' }).click()
  await expect(page).toHaveURL('/transactions?year=2046&month=1')
  await page.getByRole('link', { name: 'Previous month' }).click()
  await expect(page).toHaveURL('/transactions?year=2045&month=12')
})

test('empty month', async ({ page, app }) => {
  const [y, m] = await app.freeMonth()
  await page.goto(`/transactions?year=${y}&month=${m}`)
  await expect(page.getByText(`No transactions recorded in ${MONTHS[m - 1]} ${y}.`)).toBeVisible()
  await expect(page.locator('.card-footer')).toHaveCount(0)
})

test('delete: cancelled confirm keeps it, confirmed delete reverses balances', async ({ page, app }) => {
  const [y, m] = await app.freeMonth()
  const [buyer, a] = [await app.addUser(), await app.addUser()]
  const desc = `Kebab ${uid()}`
  await app.expense(buyer, desc, [['Kebab', '6.50', a]], { date: `${y}-${pad(m)}-20T12:00` })
  await page.goto(`/transactions?year=${y}&month=${m}`)
  const row = page.getByRole('row').filter({ hasText: desc })

  page.once('dialog', (d) => void d.dismiss())
  await row.getByRole('button', { name: 'Delete' }).click()
  await expect(row).toBeVisible()
  expect(await app.balance(a)).toBe('€-6.50')

  // Asked exactly once (the form's data-confirm used to be asked on click and again on submit).
  const dialogs: string[] = []
  page.on('dialog', (d) => {
    dialogs.push(d.message())
    void d.accept()
  })
  await row.getByRole('button', { name: 'Delete' }).click()
  await expectToast(page, 'Transaction deleted.')
  expect(dialogs).toEqual(['Delete this transaction? Balances will be reversed.'])
  await expect(page).toHaveURL(`/transactions?year=${y}&month=${m}`)
  await expect(row).toHaveCount(0)
  expect(await app.balance(a)).toBe('€0.00')
  expect(await app.balance(buyer)).toBe('€0.00')
})

test.describe('edit', () => {
  test('expense items: the amount follows the items, balances follow the amount', async ({ page, app }) => {
    const [y, m] = await app.freeMonth()
    const [buyer, a] = [await app.addUser(), await app.addUser()]
    const desc = `Thai ${uid()}`
    await app.expense(buyer, desc, [['Pad Thai', '11.00', a], ['Spring rolls', '4.50', a]], { date: `${y}-${pad(m)}-05T12:30` })
    const [id] = await app.transactionIds(desc)
    await page.goto(`/transactions?year=${y}&month=${m}`)
    await page.getByRole('row').filter({ hasText: desc }).getByRole('link', { name: 'Edit' }).click()
    await expect(page).toHaveURL(`/transaction/${id}/edit`)
    await expect(page.getByText(`Edit Transaction #${id}`)).toBeVisible()
    await expect(page.getByLabel('Type')).toHaveValue('expense')
    await expect(page.getByLabel('Type')).toBeDisabled()

    const amount = page.getByLabel('Amount (€)')
    await expect(amount).toHaveValue('15.50')
    await expect(amount).not.toBeEditable()
    await expect(page.getByText('Auto-calculated from items below.')).toBeVisible()
    const rows = page.locator('.item-row')
    await expect(rows).toHaveCount(2)
    await rows.nth(1).getByLabel('Price').fill('5')
    await page.getByRole('button', { name: 'Add Item' }).click()
    await rows.nth(2).getByLabel('Item name').fill('Mango sticky rice')
    await rows.nth(2).getByLabel('Price').fill('6,25')
    await expect(page.locator('#itemsTotal')).toHaveText('22.25')
    await expect(amount).toHaveValue('22.25')
    await rows.nth(0).getByRole('button', { name: 'Remove item' }).click()
    await expect(amount).toHaveValue('11.25')
    await page.getByLabel('Description').fill(`${desc} (corrected)`)
    await page.getByLabel('Notes').fill('Rice instead of noodles')
    await page.getByRole('button', { name: 'Save Changes' }).click()

    await expectToast(page, 'Transaction updated successfully!')
    await expect(page).toHaveURL(`/transactions?year=${y}&month=${m}`)
    await expect(page.getByText('Spring rolls (€5.00), Mango sticky rice (€6.25)')).toBeVisible()
    await expect(page.getByText('Rice instead of noodles')).toBeVisible()
    expect(await app.balance(a)).toBe('€-11.25')
    expect(await app.balance(buyer)).toBe('€11.25')
  })

  test('removing every item makes the amount editable again', async ({ page, app }) => {
    const [buyer, a] = [await app.addUser(), await app.addUser()]
    const desc = `Bakery ${uid()}`
    await app.expense(buyer, desc, [['Bread', '3.20', a]])
    const [id] = await app.transactionIds(desc)
    await page.goto(`/transaction/${id}/edit`)
    await page.locator('.item-row').getByRole('button', { name: 'Remove item' }).click()
    await expect(page.getByText('No items. Click "Add Item" to attach expense line items.')).toBeVisible()
    const amount = page.getByLabel('Amount (€)')
    await expect(amount).toBeEditable()
    await expect(amount).toHaveValue('3.20')
    await amount.fill('4')
    await page.getByRole('button', { name: 'Save Changes' }).click()
    await expectToast(page, 'Transaction updated successfully!')
    expect(await app.balance(a)).toBe('€-4.00')
    await page.goto(`/user/${a.id}`)
    await expect(page.getByText('Items:')).toHaveCount(0)
  })

  test('a bad item price is caught before saving', async ({ page, app }) => {
    const [buyer, a] = [await app.addUser(), await app.addUser()]
    const desc = `Deli ${uid()}`
    await app.expense(buyer, desc, [['Bagel', '3.50', a]])
    const [id] = await app.transactionIds(desc)
    await page.goto(`/transaction/${id}/edit`)
    await page.locator('.item-row').getByLabel('Price').fill('abc')
    await expect(page.locator('.item-row').getByLabel('Price')).toHaveClass(/is-invalid/)
    const msg = acceptNextDialog(page)
    await page.getByRole('button', { name: 'Save Changes' }).click()
    expect(await msg).toBe('Please enter a valid price.')
    await expect(page).toHaveURL(`/transaction/${id}/edit`)
    expect(await app.balance(a)).toBe('€-3.50')
  })

  test('deposit: amount, user, date and receipt', async ({ page, app }) => {
    const [y, m] = await app.freeMonth()
    const [a, b] = [await app.addUser(), await app.addUser()]
    const desc = `Top-up ${uid()}`
    await app.deposit(a, '10', desc)
    const [id] = await app.transactionIds(desc)
    await page.goto(`/transaction/${id}/edit`)
    await expect(page.locator('.item-row')).toHaveCount(0)
    await expect(page.getByText('Expense Items')).toHaveCount(0)

    await page.getByLabel('Amount (€)').fill('12.5')
    await page.getByLabel('To user').selectOption({ label: b.name })
    await page.getByLabel('Date & Time').fill(`${y}-${pad(m)}-14T08:05`)
    await page.getByLabel('Receipt / Attachment').setInputFiles({ name: 'slip.png', mimeType: 'image/png', buffer: PNG })
    await page.getByRole('button', { name: 'Save Changes' }).click()
    await expectToast(page, 'Transaction updated successfully!')
    // Saved into the new month, and the money moved from a to b.
    await expect(page).toHaveURL(`/transactions?year=${y}&month=${m}`)
    await expect(page.getByRole('row').filter({ hasText: desc })).toContainText('08:05')
    expect(await app.balance(a)).toBe('€0.00')
    expect(await app.balance(b)).toBe('€12.50')

    // The receipt is shown on the edit page, and "Remove receipt" drops it.
    await page.goto(`/transaction/${id}/edit`)
    await expect(page.getByRole('link', { name: 'View current receipt' })).toBeVisible()
    await expect(page.getByText('Uploading a new file replaces the current one.')).toBeVisible()
    await page.getByLabel('Remove receipt').check()
    await page.getByRole('button', { name: 'Save Changes' }).click()
    await expectToast(page, 'Transaction updated successfully!')
    await page.goto(`/transaction/${id}/edit`)
    await expect(page.getByRole('link', { name: 'View current receipt' })).toHaveCount(0)
    await expect(page.getByText('JPG, PNG or PDF.')).toBeVisible()
  })

  test('invalid amount and unknown user are refused, nothing changes', async ({ page, app }) => {
    const a = await app.addUser()
    const desc = `Top-up ${uid()}`
    await app.deposit(a, '10', desc)
    const [id] = await app.transactionIds(desc)
    await page.goto(`/transaction/${id}/edit`)
    await page.getByLabel('Amount (€)').fill('ten')
    await page.getByRole('button', { name: 'Save Changes' }).click()
    await expectToast(page, '"ten" is not a valid amount.')
    await expect(page).toHaveURL(`/transaction/${id}/edit`)
    const body = await app.post(`/transaction/${id}/edit`, { amount: '5', to_user_id: '99999999' }, { error: true })
    expect(body).toContain('Unknown user.')
    expect(await app.balance(a)).toBe('€10.00')
  })

  test('cancel goes back to the month without saving', async ({ page, app }) => {
    const [y, m] = await app.freeMonth()
    const a = await app.addUser()
    const desc = `Top-up ${uid()}`
    await app.deposit(a, '7', desc, { date: `${y}-${pad(m)}-01T10:00` })
    const [id] = await app.transactionIds(desc)
    await page.goto(`/transaction/${id}/edit`)
    await page.getByLabel('Amount (€)').fill('70')
    await page.getByRole('link', { name: 'Cancel' }).click()
    await expect(page).toHaveURL(`/transactions?year=${y}&month=${m}`)
    expect(await app.balance(a)).toBe('€7.00')
  })
})
