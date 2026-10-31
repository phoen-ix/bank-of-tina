import { expect, PNG, test, uid } from './fixtures'

/* Search: text over descriptions, notes and item names; the advanced filters;
 * pagination; the navbar search box; edit/delete from the results. */

test('before searching, and no results', async ({ page }) => {
  await page.goto('/search')
  await expect(page.getByText('Enter a search term or use advanced filters to find transactions across all months.')).toBeVisible()
  await expect(page.locator('#advancedFilters')).toBeHidden()
  await page.getByRole('main').getByPlaceholder('Search transactions…').fill(`nothing-${uid()}`)
  await page.getByRole('main').getByRole('button', { name: 'Search' }).first().click()
  await expect(page.getByText('No transactions found for your search.')).toBeVisible()
})

test('text matches description, notes and item names; % and _ are literal', async ({ page, app }) => {
  const [buyer, a] = [await app.addUser(), await app.addUser()]
  const id = uid()
  await app.expense(buyer, `Lunch ${id}`, [[`Ramen ${id}`, '9', a]])
  await app.deposit(a, '5', 'Top-up', { notes: `cash from jar ${id}` })
  await app.deposit(a, '6', `100% ${id}`)
  await app.deposit(a, '7', `100x ${id}`)

  const search = async (q: string) => {
    await page.goto('/')
    await page.getByRole('navigation').getByRole('searchbox', { name: 'Search transactions…' }).fill(q)
    await page.getByRole('navigation').getByRole('searchbox', { name: 'Search transactions…' }).press('Enter')
    await expect(page).toHaveURL(`/search?q=${encodeURIComponent(q).replaceAll('%20', '+')}`)
    // The navbar box keeps the query on the results page.
    await expect(page.getByRole('navigation').getByRole('searchbox', { name: 'Search transactions…' })).toHaveValue(q)
    return page.locator('tbody > tr:not(.table-light)')
  }
  await expect(await search(`Lunch ${id}`)).toHaveCount(1)
  await expect(await search(`Ramen ${id}`)).toHaveCount(1)
  await expect(await search(`jar ${id}`)).toHaveCount(1)
  await expect(await search(`100% ${id}`)).toHaveCount(1)
  await expect(page.locator('.card-footer')).toHaveText(/1 transaction\(s\) found\s*\(showing page 1 of 1\)/)
  await expect(await search(`10_ ${id}`)).toHaveCount(0)
})

test('advanced filters: type, user, dates, amounts, receipt', async ({ page, app }) => {
  const [buyer, a, b] = [await app.addUser(), await app.addUser(), await app.addUser()]
  const id = uid()
  await app.expense(buyer, `F ${id} pizza`, [['Pizza', '10', a]], { date: '2033-04-10T12:00', receipt: { name: 'p.png', mimeType: 'image/png', buffer: PNG } })
  await app.expense(buyer, `F ${id} sushi`, [['Sushi', '25', b]], { date: '2033-04-11T12:00' })
  await app.deposit(a, '50', `F ${id} deposit`, { date: '2033-04-12T09:00' })
  await app.withdrawal(b, '3', `F ${id} withdrawal`, { date: '2033-04-13T23:30' })

  await page.goto(`/search?q=F+${id}`)
  await expect(page.locator('tbody > tr:not(.table-light)')).toHaveCount(4)
  await page.getByRole('button', { name: 'Advanced filters' }).click()
  await expect(page.locator('#advancedFilters')).toBeVisible()

  const results = page.locator('tbody > tr:not(.table-light)')
  const apply = async (fill: () => Promise<void>, expected: string[]) => {
    await page.goto(`/search?q=F+${id}`)
    await page.getByRole('button', { name: 'Advanced filters' }).click()
    await fill()
    await page.locator('#advancedFilters').getByRole('button', { name: 'Search' }).click()
    // Filters in the URL open the panel by themselves.
    await expect(page.locator('#advancedFilters')).toBeVisible()
    await expect(results).toHaveCount(expected.length)
    for (const e of expected) await expect(results.filter({ hasText: `F ${id} ${e}` })).toHaveCount(1)
  }
  await apply(() => page.getByLabel('Type').selectOption('expense').then(), ['pizza', 'sushi'])
  await apply(() => page.getByLabel('User', { exact: true }).selectOption({ label: a.name }).then(), ['pizza', 'deposit'])
  await apply(async () => {
    await page.getByLabel('From date').fill('2033-04-11')
    await page.getByLabel('To date').fill('2033-04-12')
  }, ['sushi', 'deposit'])
  // Local days: 23:30 on the 13th is still the 13th.
  await apply(() => page.getByLabel('From date').fill('2033-04-13'), ['withdrawal'])
  await apply(async () => {
    await page.getByLabel('Min amount (€)').fill('10')
    await page.getByLabel('Max amount (€)').fill('25,00')
  }, ['pizza', 'sushi'])
  await apply(() => page.getByLabel('Has attachment / receipt').check(), ['pizza'])
  await expect(results.getByRole('link', { name: 'View' })).toHaveAttribute('href', /\/receipt\//)
  await expect(page.getByLabel('Has attachment / receipt')).toBeChecked()
})

test('pagination keeps the query and filters', async ({ page, app }) => {
  const a = await app.addUser()
  const id = uid()
  for (let i = 1; i <= 27; i++) await app.deposit(a, String(i), `Page ${id} #${i}`, { date: `2034-01-${String(i).padStart(2, '0')}T10:00` })
  await page.goto(`/search?q=Page+${id}&type=deposit`)
  await expect(page.locator('tbody > tr')).toHaveCount(25)
  await expect(page.locator('.card-footer')).toContainText('27 transaction(s) found (showing page 1 of 2)')
  await expect(page.getByText(`Page ${id} #27`)).toBeVisible() // newest first
  await page.getByRole('navigation', { name: 'Page navigation' }).getByRole('link', { name: 'Next' }).click()
  await expect(page).toHaveURL(new RegExp(`page=2`))
  await expect(page).toHaveURL(/type=deposit/)
  await expect(page.locator('tbody > tr')).toHaveCount(2)
  await expect(page.getByText(`Page ${id} #1`, { exact: true })).toBeVisible()
  await page.getByRole('link', { name: '1', exact: true }).click()
  await expect(page.locator('tbody > tr')).toHaveCount(25)
})

test('edit and delete from the results', async ({ page, app }) => {
  const a = await app.addUser()
  const desc = `Result ${uid()}`
  await app.deposit(a, '8', desc)
  await page.goto(`/search?q=${encodeURIComponent(desc)}`)
  await page.getByRole('link', { name: 'Edit' }).click()
  await expect(page.getByLabel('Description')).toHaveValue(desc)
  await page.goto(`/search?q=${encodeURIComponent(desc)}`)
  const dialogs: string[] = []
  page.on('dialog', (d) => {
    dialogs.push(d.message())
    void d.accept()
  })
  await page.getByRole('button', { name: 'Delete' }).click()
  await expect(page.locator('#toastContainer')).toContainText('Transaction deleted.')
  expect(dialogs).toHaveLength(1)
  expect(await app.balance(a)).toBe('€0.00')
})
