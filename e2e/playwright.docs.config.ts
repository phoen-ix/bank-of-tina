import { defineConfig, devices } from '@playwright/test'

/* The docs tour (./docs): screenshots of every screen for the READMEs and
 * docs/screenshots/, and a render check of every page it visits. One project
 * per UI language; scripts/docs-screenshots.sh runs each against its own
 * freshly seeded stack:
 *
 *   npx playwright test -c playwright.docs.config.ts --project en
 *
 * Screenshots land in ../docs/screenshots (DOCS_SCREENSHOT_DIR overrides). */

// Native controls (date inputs) and Chart.js number formats follow the
// browser's own locale, which headless Chromium takes from --lang / LANG.
function language(locale: string, lang: string) {
  return {
    locale,
    launchOptions: {
      args: [`--lang=${locale}`],
      env: { ...process.env, LANG: `${lang}.UTF-8`, LANGUAGE: `${lang}:${locale.slice(0, 2)}`, LC_ALL: `${lang}.UTF-8` },
    },
  }
}

export default defineConfig({
  testDir: './docs',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  // The seed is idempotent, but a retried render check would hide a flaky page.
  retries: 0,
  reporter: 'list',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5000',
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 2,
    timezoneId: 'Europe/Vienna',
    contextOptions: { reducedMotion: 'reduce' },
    // Full Chromium, not the headless shell: only it ships the locale packs
    // that translate native controls ("Choose File" -> "Datei auswählen").
    channel: 'chromium',
    // The app registers a service worker; it only matters offline.
    serviceWorkers: 'block',
    screenshot: 'only-on-failure',
    trace: 'off',
  },
  projects: [
    { name: 'en', use: language('en-GB', 'en_GB') },
    { name: 'de', use: language('de-AT', 'de_AT') },
  ],
})
