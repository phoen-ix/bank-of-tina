import { acceptNextDialog, expect, expectToast, PDF, PNG, test, uid } from './fixtures'

/* Add Transaction: the expense form (items, totals, client-side checks,
 * receipts, autocomplete), deposits, withdrawals and the server-side checks. */

test.describe('expense', () => {
  test('split between two debtors, the buyer\'s own item is not recorded', async ({ page, app }) => {
    const [buyer, a, b] = [await app.addUser(), await app.addUser(), await app.addUser()]
    const desc = `Pizza run ${uid()}`
    await page.goto('/transaction/add')
    await expect(page.getByRole('tab', { name: 'Expense' })).toHaveAttribute('aria-selected', 'true')
    await page.getByLabel('Who paid?').selectOption({ label: buyer.name })
    await page.getByLabel('Description', { exact: true }).fill(desc)
    const rows = page.locator('.expense-item')
    await expect(rows).toHaveCount(3) // the default empty rows
    const fill = async (i: number, name: string, price: string, who: string) => {
      await rows.nth(i).getByLabel('Item name').fill(name)
      await rows.nth(i).getByLabel('Price').fill(price)
      await rows.nth(i).getByLabel('Who owes?').selectOption({ label: who })
    }
    await fill(0, 'Margherita', '9.50', a.name)
    await fill(1, 'Diavola', '11,25', b.name) // a comma works as decimal separator too
    await fill(2, 'Tiramisu', '5.5', buyer.name)
    await expect(page.locator('#totalAmount')).toHaveText('26.25')
    await expect(page.locator('#owedNote')).toBeVisible()
    await expect(page.locator('#owedAmount')).toHaveText('20.75')
    await page.getByLabel('Date & time').first().fill('2031-03-04T12:30')
    await page.getByLabel('Notes').first().fill('Friday team lunch')
    await page.getByRole('button', { name: 'Record Expense' }).click()

    await expect(page).toHaveURL('/')
    await expectToast(page, 'Expense recorded successfully!')
    expect(await app.balance(buyer)).toBe('€20.75')
    expect(await app.balance(a)).toBe('€-9.50')
    expect(await app.balance(b)).toBe('€-11.25')
    // One transaction per debtor, both with the notes and the date.
    await page.goto(`/search?q=${encodeURIComponent(desc)}`)
    await expect(page.getByRole('row').filter({ hasText: desc })).toHaveCount(2)
    await expect(page.getByText('Friday team lunch')).toHaveCount(2)
    await expect(page.getByText('2031-03-04 12:30')).toHaveCount(2)
  })

  test('Add Item and remove buttons change the rows and the total', async ({ page, app }) => {
    const [buyer, a] = [await app.addUser(), await app.addUser()]
    await page.goto('/transaction/add')
    await page.getByLabel('Who paid?').selectOption({ label: buyer.name })
    const rows = page.locator('.expense-item')
    await page.getByRole('button', { name: 'Add Item' }).click()
    await expect(rows).toHaveCount(4)
    await rows.nth(3).getByLabel('Item name').fill('Water')
    await rows.nth(3).getByLabel('Price').fill('1.20')
    await rows.nth(3).getByLabel('Who owes?').selectOption({ label: a.name })
    await expect(page.locator('#totalAmount')).toHaveText('1.20')
    await expect(page.locator('#owedNote')).toBeHidden() // everything is owed
    await rows.nth(3).getByRole('button', { name: 'Remove item' }).click()
    await expect(rows).toHaveCount(3)
    await expect(page.locator('#totalAmount')).toHaveText('0.00')
  })

  test('client-side checks: no items, incomplete row, bad price', async ({ page, app }) => {
    const [buyer, a] = [await app.addUser(), await app.addUser()]
    await page.goto('/transaction/add')
    await page.getByLabel('Who paid?').selectOption({ label: buyer.name })
    await page.getByLabel('Description', { exact: true }).fill(`Checks ${uid()}`)
    const submit = page.getByRole('button', { name: 'Record Expense' })

    let msg = acceptNextDialog(page)
    await submit.click()
    expect(await msg).toBe('Please add at least one item!')

    const row = page.locator('.expense-item').first()
    await row.getByLabel('Item name').fill('Bread')
    msg = acceptNextDialog(page)
    await submit.click()
    expect(await msg).toBe('Please fill in name, price and who owes for every item, or remove the row.')

    await row.getByLabel('Price').fill('1.2.3')
    await row.getByLabel('Who owes?').selectOption({ label: a.name })
    await expect(row.getByLabel('Price')).toHaveClass(/is-invalid/)
    msg = acceptNextDialog(page)
    await submit.click()
    expect(await msg).toBe('Please enter a valid price.')
    await expect(row.getByLabel('Price')).toBeFocused()
    await expect(page).toHaveURL(/\/transaction\/add$/)
    expect(await app.balance(a)).toBe('€0.00')
  })

  test('required fields block the submit', async ({ page }) => {
    await page.goto('/transaction/add')
    await page.getByRole('button', { name: 'Record Expense' }).click()
    await expect(page.locator('#buyer_id:invalid')).toHaveCount(1)
    await expect(page).toHaveURL(/\/transaction\/add$/)
  })

  test('server-side: an expense of only the buyer\'s own items is rejected', async ({ page, app }) => {
    const buyer = await app.addUser()
    await page.goto('/transaction/add')
    await page.getByLabel('Who paid?').selectOption({ label: buyer.name })
    await page.getByLabel('Description', { exact: true }).fill(`Own lunch ${uid()}`)
    const row = page.locator('.expense-item').first()
    await row.getByLabel('Item name').fill('Salad')
    await row.getByLabel('Price').fill('7')
    await row.getByLabel('Who owes?').selectOption({ label: buyer.name })
    await page.getByRole('button', { name: 'Record Expense' }).click()
    await expect(page).toHaveURL(/\/transaction\/add$/)
    await expectToast(page, 'Nobody owes anything: all items belong to the buyer.')
    expect(await app.balance(buyer)).toBe('€0.00')
  })

  test('receipt: a PDF is stored and linked, other file types are refused', async ({ page, app }) => {
    const [buyer, a] = [await app.addUser(), await app.addUser()]
    const desc = `Receipt lunch ${uid()}`
    const fillAndSubmit = async (file: { name: string; mimeType: string; buffer: Buffer }) => {
      await page.goto('/transaction/add')
      await page.getByLabel('Who paid?').selectOption({ label: buyer.name })
      await page.getByLabel('Description', { exact: true }).fill(desc)
      const row = page.locator('.expense-item').first()
      await row.getByLabel('Item name').fill('Bento')
      await row.getByLabel('Price').fill('12.90')
      await row.getByLabel('Who owes?').selectOption({ label: a.name })
      await page.getByLabel('Receipt (optional)').setInputFiles(file)
      await page.getByRole('button', { name: 'Record Expense' }).click()
    }
    await fillAndSubmit({ name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('hello') })
    await expectToast(page, 'Receipts must be JPG, PNG or PDF files.')
    expect(await app.balance(a)).toBe('€0.00')

    await fillAndSubmit({ name: 'Bill 07.pdf', mimeType: 'application/pdf', buffer: PDF })
    await expectToast(page, 'Expense recorded successfully!')
    // Dashboard: the newest transactions link the receipt.
    await page.goto(`/user/${a.id}`)
    const link = page.getByRole('link', { name: 'View Receipt' })
    await expect(link).toHaveAttribute('href', new RegExp(`/receipt/\\d{4}/\\d{2}/\\d{2}/${buyer.name.replaceAll(' ', '_')}_Bill_07_[0-9a-f]{6}\\.pdf$`))
    const res = await page.request.get((await link.getAttribute('href'))!)
    expect(res.headers()['content-type']).toBe('application/pdf')
    expect((await res.body()).equals(PDF)).toBe(true)
  })

  test('autocomplete suggestions come from the common lists', async ({ page, app }) => {
    const id = uid()
    await app.post('/settings/common-items/add', { name: `Croissant ${id}` })
    await app.post('/settings/common-descriptions/add', { value: `Bakery ${id}` })
    await app.post('/settings/common-prices/add', { value: '2.85' })
    await page.goto('/transaction/add')
    await expect(page.locator(`#commonItemsList option[value="Croissant ${id}"]`)).toBeAttached()
    await expect(page.locator(`#commonDescriptionsList option[value="Bakery ${id}"]`)).toBeAttached()
    await expect(page.locator('#commonPricesList option[value="2.85"]')).toBeAttached()
    await expect(page.getByLabel('Description', { exact: true })).toHaveAttribute('list', 'commonDescriptionsList')
    await expect(page.locator('.expense-item').first().getByLabel('Item name')).toHaveAttribute('list', 'commonItemsList')
  })
})

test.describe('deposit and withdrawal', () => {
  test('quick actions open the matching tab', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: 'Add Money' }).click()
    await expect(page).toHaveURL(/type=deposit/)
    await expect(page.getByRole('tab', { name: 'Deposit' })).toHaveAttribute('aria-selected', 'true')
    await page.goto('/')
    await page.getByRole('link', { name: 'Withdraw Money' }).click()
    await expect(page.getByRole('tab', { name: 'Withdrawal' })).toHaveAttribute('aria-selected', 'true')
    await page.goto('/')
    await page.getByRole('link', { name: 'Record Expense' }).click()
    await expect(page.getByRole('tab', { name: 'Expense' })).toHaveAttribute('aria-selected', 'true')
  })

  test('deposit then withdrawal move the balance', async ({ page, app }) => {
    const u = await app.addUser()
    const desc = `Top-up ${uid()}`
    await page.goto('/transaction/add?type=deposit')
    const dep = page.locator('#deposit')
    await dep.getByLabel('User').selectOption({ label: u.name })
    await dep.getByLabel('Amount (€)').fill('20,5')
    await dep.getByLabel('Description (optional)').fill(desc)
    await dep.getByLabel('Notes').fill('Cash in the tin')
    await dep.getByRole('button', { name: 'Add Money' }).click()
    await expectToast(page, 'Deposit of €20.50 added successfully!')
    expect(await app.balance(u)).toBe('€20.50')

    await page.goto('/transaction/add?type=withdrawal')
    const wd = page.locator('#withdrawal')
    await wd.getByLabel('User').selectOption({ label: u.name })
    await wd.getByLabel('Amount (€)').fill('25')
    await wd.getByRole('button', { name: 'Withdraw Money' }).click()
    await expectToast(page, 'Withdrawal of €25.00 processed successfully!')
    expect(await app.balance(u)).toBe('€-4.50') // overdrawing is allowed

    await page.goto(`/user/${u.id}`)
    await expect(page.getByText('Received €20.50')).toBeVisible()
    await expect(page.getByText('Paid €25.00')).toBeVisible()
    await expect(page.getByText('Cash in the tin')).toBeVisible()
  })

  test('invalid amounts are refused and change nothing', async ({ page, app }) => {
    const u = await app.addUser()
    for (const [amount, message] of [['abc', '"abc" is not a valid amount.'], ['0', 'Amounts must be greater than zero.'],
      ['-5', 'Amounts must be greater than zero.'], ['1e5', '"1e5" is not a valid amount.']]) {
      await page.goto('/transaction/add?type=deposit')
      await page.locator('#deposit').getByLabel('User').selectOption({ label: u.name })
      await page.locator('#deposit').getByLabel('Amount (€)').fill(amount)
      await page.locator('#deposit').getByRole('button', { name: 'Add Money' }).click()
      await expect(page).toHaveURL(/\/transaction\/add$/)
      await expectToast(page, message)
    }
    expect(await app.balance(u)).toBe('€0.00')
  })

  test('tampered forms: unknown user and unknown type', async ({ app }) => {
    let body = await app.post('/transaction/add', { transaction_type: 'deposit', user_id: '99999999', amount: '5' }, { error: true })
    expect(body).toContain('Unknown user.')
    body = await app.post('/transaction/add', { transaction_type: 'gift', amount: '5' }, { error: true })
    expect(body).toContain('Unknown transaction type.')
    body = await app.post('/transaction/add', { transaction_type: 'expense', buyer_id: '', items_json: '[]' }, { error: true })
    expect(body).toContain('Please select a user.')
  })
})
