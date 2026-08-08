import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: '../build/e2e-report', open: 'never' }]],
  outputDir: '../build/e2e-results',
  use: {
    baseURL: 'http://127.0.0.1:18766',
    channel: 'msedge',
    viewport: { width: 1600, height: 1000 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command: 'python ../tools/testing/e2e_server.py',
    url: 'http://127.0.0.1:18766/api/health',
    timeout: 30_000,
    reuseExistingServer: false,
  },
});
