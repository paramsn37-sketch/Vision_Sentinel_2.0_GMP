import { expect, test } from '@playwright/test'

for (const theme of ['dark', 'light'] as const) {
  test(`design route renders every primitive (${theme})`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto(`/_design?theme=${theme}`)
    await expect(page.getByRole('heading', { name: 'Design system' })).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: `e2e/__screenshots__/design/design-${theme}.png`, fullPage: true })
  })
}
