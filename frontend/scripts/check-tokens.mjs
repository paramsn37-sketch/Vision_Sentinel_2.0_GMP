// Gate for Phase 7: every `--token` named in DESIGN.md exists in tokens.css, and every text/background pair the
// primitives use meets its WCAG contrast target in both themes. Prints a table; exits 1 on any failure.
// Usage: node scripts/check-tokens.mjs [--markdown]
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const css = readFileSync(resolve(here, '../src/styles/tokens.css'), 'utf8')
const design = readFileSync(resolve(here, '../../DESIGN.md'), 'utf8')

function block(selector) {
  const i = css.indexOf(selector)
  if (i < 0) throw new Error(`selector not found: ${selector}`)
  const body = css.slice(css.indexOf('{', i) + 1, css.indexOf('}', i))
  return Object.fromEntries([...body.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]))
}

const themes = { dark: block("[data-theme='dark'] {"), light: block("[data-theme='light'] {") }
const defined = new Set([...css.matchAll(/(--[\w-]+):/g)].map((m) => m[1]))
const named = new Set([...design.matchAll(/`(--[\w-]+)`/g)].map((m) => m[1]))
const missing = [...named].filter((t) => !defined.has(t))

function lum(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  const [r, g, b] = c.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const ratio = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}

// [foreground, background, minimum, what uses it]
const pairs = [
  ['--fg', '--bg', 7, 'body text, live-wall numbers (AAA)'],
  ['--fg', '--bg-sunken', 7, 'text in panels and tables (AAA)'],
  ['--fg', '--bg-raised', 7, 'menus, dialogs'],
  ['--fg-muted', '--bg', 4.5, 'secondary text'],
  ['--fg-muted', '--bg-sunken', 4.5, 'secondary text in panels'],
  ['--fg-muted', '--bg-hover', 4.5, 'secondary text on hovered row'],
  ['--fg-subtle', '--bg-sunken', 4.5, 'placeholders, timestamps'],
  ['--accent', '--bg-sunken', 4.5, 'links, selected tab label'],
  ['--accent', '--accent-bg', 4.5, 'info pill'],
  ['--danger', '--bg-sunken', 4.5, 'danger text'],
  ['--danger', '--danger-bg', 4.5, 'danger pill'],
  ['--warning', '--bg-sunken', 4.5, 'warning text'],
  ['--warning', '--warning-bg', 4.5, 'warning pill'],
  ['--ok', '--bg-sunken', 4.5, 'ok text'],
  ['--ok', '--ok-bg', 4.5, 'ok pill'],
  ['--fg-muted', '--neutral-bg', 4.5, 'neutral pill'],
  ['--fg-on-accent', '--accent', 4.5, 'primary button label'],
  ['--line-strong', '--bg-sunken', 3, 'input and switch boundaries'],
  ['--line-strong', '--bg', 3, 'input boundaries on ground'],
  ['--accent', '--bg', 3, 'focus ring, selection line'],
]

let failed = missing.length > 0
const rows = []
for (const [theme, t] of Object.entries(themes)) {
  for (const [fg, bg, min, use] of pairs) {
    const r = ratio(t[fg], t[bg])
    const ok = r >= min
    failed ||= !ok
    rows.push(`| ${theme} | \`${fg}\` on \`${bg}\` | ${r.toFixed(2)} | ${min} | ${ok ? 'pass' : 'FAIL'} | ${use} |`)
  }
}

if (process.argv.includes('--markdown')) {
  console.log('| theme | pair | ratio | target | result | used for |\n|---|---|---|---|---|---|')
  console.log(rows.join('\n'))
} else {
  console.log(rows.join('\n'))
  console.log(`\n${named.size} tokens named in DESIGN.md, ${defined.size} defined in tokens.css`)
  if (missing.length) console.log('missing from tokens.css:', missing.join(', '))
}
process.exit(failed ? 1 : 0)
