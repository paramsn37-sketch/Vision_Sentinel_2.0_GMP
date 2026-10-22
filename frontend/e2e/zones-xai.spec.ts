import { expect, test, type Page } from '@playwright/test'
import { login } from './helpers'

// Phase 9 flagship flows against the running stack (seeded cameras playing sample clips).
const PREFIX = 'E2E '

async function api(page: Page, method: 'GET' | 'DELETE', path: string) {
  const csrf = (await page.context().cookies()).find((c) => c.name === 'vs_csrf')?.value ?? ''
  return page.request.fetch(`/api/v1${path}`, { method, headers: { 'x-csrf-token': csrf } })
}

/** Remove zones created by these tests so they stop raising incidents on the demo cameras. */
async function cleanupZones(page: Page) {
  const res = await api(page, 'GET', '/zones')
  if (!res.ok()) return
  for (const z of (await res.json()) as { id: string; name: string }[]) if (z.name.startsWith(PREFIX)) await api(page, 'DELETE', `/zones/${z.id}`)
}

/** Click at normalised frame coordinates on the zone editor's image. */
async function clickFrame(page: Page, x: number, y: number) {
  const box = (await page.getByAltText('Frozen camera frame').boundingBox())!
  await page.mouse.click(box.x + box.width * x, box.y + box.height * y)
}

async function openNewZone(page: Page) {
  await page.goto('/zones')
  await expect(page.getByAltText('Frozen camera frame')).toBeVisible()
  await expect.poll(async () => (await page.getByAltText('Frozen camera frame').evaluate((i: HTMLImageElement) => i.naturalWidth)) > 0).toBe(true)
  await page.getByRole('button', { name: 'New zone' }).click()
  await expect(page.getByText(/^Drawing: 0 points/)).toBeVisible()
}

test.beforeEach(async ({ page }) => {
  await login(page)
  await cleanupZones(page)
})
test.afterEach(async ({ page }) => cleanupZones(page))

test('draw a no-entry zone, get an intrusion incident, explain it, acknowledge and resolve', async ({ page }) => {
  test.setTimeout(240_000)
  const name = `${PREFIX}walkway ${Date.now().toString(36)}`
  await openNewZone(page)

  // Cover the lower part of the frame, where people walk in every seeded clip.
  for (const [x, y] of [
    [0.03, 0.35],
    [0.97, 0.35],
    [0.97, 0.97],
    [0.03, 0.97],
  ])
    await clickFrame(page, x, y)
  await page.keyboard.press('Enter')
  await expect(page.getByText(/^4 points/)).toBeVisible()
  await page.getByLabel('Name').fill(name)
  await page.getByRole('button', { name: 'Save zone' }).click()
  await expect(page.getByText(`Zone “${name}” created`)).toBeVisible()

  // The running pipeline picks the zone up without a restart and opens an intrusion incident.
  await page.goto(`/incidents?q=${encodeURIComponent(name)}`)
  const row = page.getByRole('row').filter({ hasText: 'Entered no-entry zone' }).filter({ hasText: name }).first()
  await expect(row).toBeVisible({ timeout: 90_000 })

  // Live rows keep arriving for this zone, so retry the click if the table re-rendered under the pointer.
  const drawer = page.getByRole('dialog')
  await expect(async () => {
    if (!(await drawer.isVisible())) await row.click()
    await expect(drawer.getByRole('heading', { name: 'Entered no-entry zone' })).toBeVisible({ timeout: 5_000 })
    await expect(drawer.getByText(name)).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 30_000 })
  await expect(drawer.getByAltText(/Evidence frame/)).toBeVisible({ timeout: 20_000 })
  await drawer.getByRole('tab', { name: 'Explanation' }).click()
  await expect(drawer.getByRole('img', { name: 'Frame with the explanation heatmap blended over it' })).toBeVisible({ timeout: 120_000 })
  await expect(drawer.getByText(/% of the evidence lies inside the box/)).toBeVisible()

  await drawer.getByRole('button', { name: 'Acknowledge' }).click()
  await expect(drawer.getByText('Acknowledged', { exact: true })).toBeVisible()
  await drawer.getByRole('button', { name: 'Resolve' }).click()
  await expect(drawer.getByText('Resolved', { exact: true })).toBeVisible()
  await expect(drawer.getByRole('button', { name: 'Reopen' })).toBeVisible()
})

test('drag a vertex and undo it', async ({ page }) => {
  const name = `${PREFIX}drag ${Date.now().toString(36)}`
  await openNewZone(page)
  for (const [x, y] of [
    [0.2, 0.2],
    [0.5, 0.2],
    [0.5, 0.5],
  ])
    await clickFrame(page, x, y)
  await page.keyboard.press('Enter')
  await page.getByLabel('Name').fill(name)
  await page.getByRole('button', { name: 'Save zone' }).click()
  await expect(page.getByText(`Zone “${name}” created`)).toBeVisible()

  const vertex = page.locator('[data-vertex="1"]')
  const before = await vertex.getAttribute('cx')
  const img = (await page.getByAltText('Frozen camera frame').boundingBox())!
  await page.mouse.move(img.x + img.width * 0.5, img.y + img.height * 0.2)
  await page.mouse.down()
  await page.mouse.move(img.x + img.width * 0.65, img.y + img.height * 0.25, { steps: 8 })
  await page.mouse.up()
  const moved = await vertex.getAttribute('cx')
  expect(Number(moved)).toBeGreaterThan(Number(before))
  await expect(page.getByRole('button', { name: 'Save zone' })).toBeEnabled()

  await page.getByRole('button', { name: 'Undo' }).click()
  await expect(vertex).toHaveAttribute('cx', before!)
  await expect(page.getByRole('button', { name: 'Redo' })).toBeEnabled()
})

test('keyboard only: create and save a zone', async ({ page }) => {
  const name = `${PREFIX}keyboard ${Date.now().toString(36)}`
  await page.goto('/zones')
  await expect(page.getByAltText('Frozen camera frame')).toBeVisible()
  await page.getByRole('button', { name: 'New zone' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByText(/^Drawing: 0 points/)).toBeVisible()

  await page.getByTestId('zone-canvas').focus()
  const step = async (key: string, n: number) => {
    for (let i = 0; i < n; i++) await page.keyboard.press(`Shift+${key}`)
  }
  // Cursor starts at the centre; place a 20 % square around it with Space.
  await step('ArrowLeft', 10)
  await step('ArrowUp', 10)
  await page.keyboard.press('Space')
  await step('ArrowRight', 20)
  await page.keyboard.press('Space')
  await step('ArrowDown', 20)
  await page.keyboard.press('Space')
  await step('ArrowLeft', 20)
  await page.keyboard.press('Space')
  await expect(page.getByText(/^Drawing: 4 points/)).toBeVisible()
  await page.keyboard.press('Enter')
  await expect(page.getByText(/^4 points/)).toBeVisible()

  await page.getByLabel('Name').focus()
  await page.keyboard.type(name)
  await page.keyboard.press('Enter')
  await expect(page.getByText(`Zone “${name}” created`)).toBeVisible()
  await expect(page.getByRole('button', { name: new RegExp(name) })).toBeVisible()
})
