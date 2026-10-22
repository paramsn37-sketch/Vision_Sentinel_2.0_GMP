import { expect, test } from '@playwright/test'
import { login } from './helpers'
import { ROUTES } from './routes'


test('live shows frames with person boxes within 10 s', async ({ page }) => {
  await login(page)
  await expect(page.getByRole('figure').first()).toBeVisible()
  // The tile header shows counts once the first frame with metadata has been drawn.
  await expect(page.getByText(/unique$/).first()).toBeVisible({ timeout: 10_000 })
  await page.screenshot({ path: 'e2e/__screenshots__/screens/live-dark.png' })
})

test('every route renders without errors', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await login(page)
  for (const [path, title] of ROUTES) {
    await page.goto(path)
    await expect(page.getByRole('heading', { name: title, level: 1 })).toBeVisible()
    await page.waitForTimeout(1500)
    await page.screenshot({ path: `e2e/__screenshots__/screens${path}-dark.png` })
  }
  expect(errors).toEqual([])
})
