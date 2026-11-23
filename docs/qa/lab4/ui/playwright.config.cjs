const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 40000,
  expect: { timeout: 7000 },
  workers: 1,
  retries: 0,
  outputDir: process.env.QA_PW_RESULTS || './test-results',
  reporter: [
    ['list'],
    ['json', { outputFile: process.env.QA_PW_JSON || './playwright-results.json' }],
    ['html', { outputFolder: process.env.QA_PW_HTML || './playwright-report', open: 'never' }],
  ],
  use: {
    baseURL: process.env.QA_BASE_URL || 'http://127.0.0.1:8765',
    actionTimeout: 9000,
    navigationTimeout: 12000,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'Chrome-UI', testMatch: 'flows.spec.cjs', use: { ...devices['Desktop Chrome'], channel: 'chrome' } },
    { name: 'Chrome', testMatch: 'compat.spec.cjs', use: { ...devices['Desktop Chrome'], channel: 'chrome' } },
    { name: 'Firefox', testMatch: 'compat.spec.cjs', use: { ...devices['Desktop Firefox'] } },
    { name: 'WebKit', testMatch: 'compat.spec.cjs', use: { ...devices['Desktop Safari'] } },
    { name: 'Chrome-mobile', testMatch: 'compat.spec.cjs', use: { ...devices['Pixel 7'], channel: 'chrome' } },
  ],
});
