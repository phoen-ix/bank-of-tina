import { GENERAL, test } from './fixtures'

// The global settings every spec expects: English UI, Vienna time, "." and €,
// no site admin, autocomplete on. The global/ specs put these back when done.
test('baseline settings', async ({ app }) => {
  await app.post('/settings/general', GENERAL)
  await app.post('/settings/common', { common_enabled: '1' })
})
