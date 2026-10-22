import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { login } from './helpers'
import { ROUTES, THEMES } from './routes'

// Gate for Phase 10: zero serious or critical axe violations on every route, in both themes.
for (const theme of THEMES) {
  test(`axe: every route, ${theme} theme`, async ({ page }) => {
    test.setTimeout(180_000)
    // Toasts fade in; with motion reduced axe measures their settled colours instead of a mid-fade frame.
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.addInitScript((t) => localStorage.setItem('vs.theme', JSON.stringify(t)), theme)
    await login(page)
    const report: string[] = []
    for (const [path, title] of ROUTES) {
      await page.goto(path)
      await expect(page.getByRole('heading', { name: title, level: 1 })).toBeVisible()
      await page.waitForTimeout(1200)
      const res = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
      for (const v of res.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical'))
        report.push(`${path} [${v.impact}] ${v.id}: ${v.help} → ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`)
    }
    expect(report, report.join('\n')).toEqual([])
  })
}

test('reduced motion: overlays do not animate', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await login(page)
  const dur = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--dur-panel').trim())
  expect(dur).toBe('0ms')
})
