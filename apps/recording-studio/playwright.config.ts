import { defineConfig } from '@playwright/test';
export default defineConfig({
  // Playwright clears this directory before a run; preserve the native smoke evidence beside it.
  outputDir: './test-results/browser',
  testDir: './e2e', fullyParallel: true, retries: 0,
  use: { baseURL: 'http://127.0.0.1:1420', viewport: { width: 1280, height: 900 },
    channel: process.env.STUDIO_TEST_BROWSER || 'chrome', screenshot: 'only-on-failure' },
  webServer: { command: 'npm run web:dev', url: 'http://127.0.0.1:1420', reuseExistingServer: !process.env.CI },
});
