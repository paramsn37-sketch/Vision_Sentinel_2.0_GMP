import { expect, test } from '@playwright/test'
import { login } from './helpers'
import { ROUTES, THEMES, WIDTHS } from './routes'

// Phase 10 review set: every route at four widths in both themes, with live data. The images are reviewed by eye
// (docs/ui-review/); the assertions here are the objective parts: the page renders and never scrolls sideways.
for (const theme of THEMES)
  for (const width of WIDTHS)
    test(`screens ${theme} ${width}px`, async ({ page }) => {
      test.setTimeout(180_000)
      await page.setViewportSize({ width, height: width < 600 ? 844 : 900 })
      await page.addInitScript((t) => localStorage.setItem('vs.theme', JSON.stringify(t)), theme)
      await login(page)
      for (const [path, title] of ROUTES) {
        await page.goto(path)
        await expect(page.getByRole('heading', { name: title, level: 1 })).toBeVisible()
        await page.waitForTimeout(path === '/live' ? 3000 : 1200)
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
        expect.soft(overflow, `${path} scrolls sideways at ${width}px`).toBeLessThanOrEqual(0)
        await page.screenshot({ path: `e2e/__screenshots__/visual/${path.slice(1)}-${width}-${theme}.png` })
      }
    })

// Key states for the review and the README: incident drawer with the explanation, and the zone editor mid-draw.
for (const theme of THEMES)
  test(`key states ${theme}`, async ({ page }) => {
    test.setTimeout(240_000)
    await page.addInitScript((t) => localStorage.setItem('vs.theme', JSON.stringify(t)), theme)
    await login(page)

    await page.goto('/incidents?rule=intrusion')
    const row = page.getByRole('row').filter({ hasText: 'Entered no-entry zone' }).first()
    await expect(row).toBeVisible({ timeout: 90_000 })
    const drawer = page.getByRole('dialog')
    await expect(async () => {
      if (!(await drawer.isVisible())) await row.click()
      await expect(drawer.getByRole('heading', { name: 'Entered no-entry zone' })).toBeVisible({ timeout: 5_000 })
    }).toPass({ timeout: 30_000 })
    await expect(drawer.getByAltText(/Evidence frame/)).toBeVisible({ timeout: 20_000 })
    await page.screenshot({ path: `e2e/__screenshots__/visual/state-drawer-${theme}.png` })
    await drawer.getByRole('tab', { name: 'Explanation' }).click()
    await expect(drawer.getByText(/% of the evidence lies inside the box/)).toBeVisible({ timeout: 120_000 })
    await page.screenshot({ path: `e2e/__screenshots__/visual/state-xai-${theme}.png` })
    await page.keyboard.press('Escape')

    await page.goto('/zones')
    await expect.poll(async () => page.getByAltText('Frozen camera frame').evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0)
    await page.getByRole('button', { name: 'New zone' }).click()
    const box = (await page.getByAltText('Frozen camera frame').boundingBox())!
    for (const [x, y] of [
      [0.35, 0.45],
      [0.62, 0.42],
      [0.7, 0.9],
    ])
      await page.mouse.click(box.x + box.width * x, box.y + box.height * y)
    await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.88)
    await page.screenshot({ path: `e2e/__screenshots__/visual/state-editor-drawing-${theme}.png` })
    await page.keyboard.press('Escape')
  })
