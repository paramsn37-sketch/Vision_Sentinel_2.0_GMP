import { defineConfig, devices } from '@playwright/test'

// E2E runs against `make dev` (backend on :8000, Vite on :5173) unless VS_E2E_URL points elsewhere.
export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  snapshotPathTemplate: '{testDir}/__screenshots__/{arg}{ext}',
  use: {
    baseURL: process.env.VS_E2E_URL ?? 'http://127.0.0.1:5173',
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
    launchOptions: { executablePath: process.env.VS_CHROMIUM ?? undefined },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
})
