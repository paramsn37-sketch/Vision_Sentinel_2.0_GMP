import { expect, type Page } from '@playwright/test'

export const PASSWORD = process.env.VS_ADMIN_PASSWORD ?? 'sentinel-demo-pass'

export async function login(page: Page) {
  await page.goto('/login')
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/live/)
}
