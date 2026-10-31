import { defineConfig, devices } from '@playwright/test'

/* The e2e suite (./tests), inventory in COVERAGE.md. Run it through
 * scripts/e2e.sh, which starts a throwaway stack (app, MariaDB, Mailpit):
 *
 *   scripts/e2e.sh                         # everything
 *   scripts/e2e.sh tests/search.spec.ts    # extra args go to `playwright test`
 *
 * The app has no login, but some settings are global (language, timezone,
 * decimal separator, site admin, SMTP, templates, backups/restore). So:
 *   setup  - puts those settings into the state every other test expects
 *   app    - everything that only touches its own users/transactions, in parallel
 *   global - the specs that change global settings, one at a time, after `app`
 * Every request carries a per-test X-Forwarded-For (tests/fixtures.ts), so the
 * app's per-client rate limits never couple two tests. */

const CI = !!process.env.CI

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  workers: 2,
  retries: CI ? 1 : 0,
  forbidOnly: CI,
  reporter: CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5000',
    locale: 'en-GB',
    timezoneId: 'Europe/Vienna',
    // Bootstrap drops its fade transitions: a dialog closed while it was still
    // fading in would ignore the click.
    contextOptions: { reducedMotion: 'reduce' },
    // Only tests/pwa.spec.ts lets the service worker in.
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'setup', testMatch: /setup\.ts$/ },
    { name: 'app', testIgnore: [/global\//, /setup\.ts$/], dependencies: ['setup'] },
    { name: 'global', testMatch: /global\/.*\.spec\.ts$/, dependencies: ['app'], fullyParallel: false, workers: 1 },
  ],
})
