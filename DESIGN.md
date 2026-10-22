# DESIGN.md — Vision Sentinel 2.0

The visual and interaction system for the operator console. Product truth lives in `PRODUCT.md`; tokens live in
`frontend/src/styles/tokens.css` (checked against this file by `frontend/scripts/check-tokens.mjs`).

## 1. Direction

**A monitoring terminal for a safety control room.** Operators read it for hours, often in a dim room, sometimes
from two metres. The surface is an *Operate* surface (impeccable): standard web controls, dense, calm. Its world
lends four things only — type, palette, density and one signature move — and never the layout or the controls.

- **Style:** Taste app style `data-terminal` (dark, long sessions, monitoring; seed 1131022410). Cards sit *darker*
  than the ground; numbers stack in tabular figures; colour carries state, never decoration.
- **Signature move — the selection line.** Every selection (nav item, tab, segmented option, selected table row,
  selected track on the video) is marked by the same **1 px accent line** on the nearest existing edge, exactly as
  wide as its label. Nothing else is blue unless it is information or a link.
- **Signature element — the shift strip.** A minute-by-minute strip of people on site across the shift with each
  incident marked at its onset (Live right panel, Analytics header). It answers "what happened during this shift"
  at a glance and is built from `counts_minutely` and incidents, never sampled or smoothed for show.
- **Face:** every figure, ID and timestamp in IBM Plex Mono (digits that stack and are read across a room); all
  prose and labels in Public Sans. Mono is used for measurement, not as a "technical" costume: it never sets a
  heading, a button or a sentence.
- **Deviation from the dealt sheet (recorded):** controls use 4 px corners instead of 999 px pills, because the
  owner asked for a *standard industrial* UI and HMI controls are rectangular. Dealt Public Sans is kept.

## 2. Principles

1. **Grey by default, colour means state** (ISA-101 high-performance HMI). Red, amber, green and blue appear only
   when something is in that state. Colour share of a screen stays under about 5 % outside the video.
2. **Every number is measured and has a unit.** "Not measured" is written out, never a dash that hides a gap.
   Zero is printed as `0`; a missing value is a grey `—` with a tooltip that says why.
3. **One decision per alert.** An incident shows its evidence, its explanation and the two actions (acknowledge,
   resolve) in one place.
4. **Calm motion.** Motion confirms a state change and then stops. Red never blinks forever.
5. **Keyboard first-class.** Every action reachable without a mouse; shortcuts are shown with `Kbd`.

## 3. Colour

Tokens (both themes define every one; dark is the default because of the use scene):

| role | token | dark | light | use |
|---|---|---|---|---|
| ground | `--bg` | #171719 | #f3f3f4 | page, rail, status strip |
| panel | `--bg-sunken` | #121215 | #ffffff | cards, tables, video tiles |
| float | `--bg-raised` | #1f1f23 | #ffffff | menus, dialogs, drawers, tooltips |
| hover | `--bg-hover` | #26262b | #e9e9eb | row and control hover |
| rule | `--line` | #26262b | #e1e1e4 | 1 px separators, table rules |
| boundary | `--line-strong` | #6a6b72 | #85878f | input, switch, checkbox outlines (≥ 3:1) |
| text | `--fg` | #f2f2f3 | #17171a | primary text and figures |
| secondary | `--fg-muted` | #9a9ca3 | #5c5e66 | labels, captions |
| tertiary | `--fg-subtle` | #85878e | #6e7078 | placeholders, timestamps |
| on accent | `--fg-on-accent` | #0c1420 | #ffffff | primary button label |
| information / selection | `--accent`, `--accent-bg` | #5b9be6 | #1d64c2 | selection line, links, info |
| danger (ISO red) | `--danger`, `--danger-bg` | #f2626f | #c3283d | open high incidents, no-entry |
| warning (ISO amber) | `--warning`, `--warning-bg` | #e0a84a | #8a5c00 | medium incidents, occupancy |
| safe (ISO green) | `--ok`, `--ok-bg` | #4fb58f | #1b7656 | compliant, running |
| neutral pill | `--neutral-bg` | #26262b | #e9e9eb | resolved, stopped |

Zones: `--zone-restricted` (red), `--zone-hazard` (amber), `--zone-ppe` (blue) — outline at full strength, fill
at 20 % on video. Video overlays use theme-independent colours because they sit on camera pixels:
`--ov-person`, `--ov-ok`, `--ov-danger`, `--ov-label-bg`. Floating layers use `--shadow-float` over `--scrim`.

Alert level → colour: green `--ok`, amber `--warning`, red `--danger`. State pills always pair the colour with a
word ("Open", "Missing helmet"), never colour alone.

### Contrast (measured by `node frontend/scripts/check-tokens.mjs`)

| theme | pair | ratio | target | result | used for |
|---|---|---|---|---|---|
| dark | `--fg` on `--bg` | 16.00 | 7 | pass | body text, live-wall numbers (AAA) |
| dark | `--fg` on `--bg-sunken` | 16.71 | 7 | pass | text in panels and tables (AAA) |
| dark | `--fg` on `--bg-raised` | 14.68 | 7 | pass | menus, dialogs |
| dark | `--fg-muted` on `--bg` | 6.53 | 4.5 | pass | secondary text |
| dark | `--fg-muted` on `--bg-sunken` | 6.82 | 4.5 | pass | secondary text in panels |
| dark | `--fg-muted` on `--bg-hover` | 5.49 | 4.5 | pass | secondary text on hovered row |
| dark | `--fg-subtle` on `--bg-sunken` | 5.21 | 4.5 | pass | placeholders, timestamps |
| dark | `--accent` on `--bg-sunken` | 6.48 | 4.5 | pass | links, selected tab label |
| dark | `--accent` on `--accent-bg` | 5.49 | 4.5 | pass | info pill |
| dark | `--danger` on `--bg-sunken` | 6.01 | 4.5 | pass | danger text |
| dark | `--danger` on `--danger-bg` | 5.16 | 4.5 | pass | danger pill |
| dark | `--warning` on `--bg-sunken` | 8.79 | 4.5 | pass | warning text |
| dark | `--warning` on `--warning-bg` | 7.15 | 4.5 | pass | warning pill |
| dark | `--ok` on `--bg-sunken` | 7.42 | 4.5 | pass | ok text |
| dark | `--ok` on `--ok-bg` | 6.08 | 4.5 | pass | ok pill |
| dark | `--fg-muted` on `--neutral-bg` | 5.49 | 4.5 | pass | neutral pill |
| dark | `--fg-on-accent` on `--accent` | 6.40 | 4.5 | pass | primary button label |
| dark | `--line-strong` on `--bg-sunken` | 3.53 | 3 | pass | input and switch boundaries |
| dark | `--line-strong` on `--bg` | 3.37 | 3 | pass | input boundaries on ground |
| dark | `--accent` on `--bg` | 6.20 | 3 | pass | focus ring, selection line |
| light | `--fg` on `--bg` | 16.13 | 7 | pass | body text, live-wall numbers (AAA) |
| light | `--fg` on `--bg-sunken` | 17.89 | 7 | pass | text in panels and tables (AAA) |
| light | `--fg` on `--bg-raised` | 17.89 | 7 | pass | menus, dialogs |
| light | `--fg-muted` on `--bg` | 5.83 | 4.5 | pass | secondary text |
| light | `--fg-muted` on `--bg-sunken` | 6.47 | 4.5 | pass | secondary text in panels |
| light | `--fg-muted` on `--bg-hover` | 5.33 | 4.5 | pass | secondary text on hovered row |
| light | `--fg-subtle` on `--bg-sunken` | 4.94 | 4.5 | pass | placeholders, timestamps |
| light | `--accent` on `--bg-sunken` | 5.75 | 4.5 | pass | links, selected tab label |
| light | `--accent` on `--accent-bg` | 4.86 | 4.5 | pass | info pill |
| light | `--danger` on `--bg-sunken` | 5.69 | 4.5 | pass | danger text |
| light | `--danger` on `--danger-bg` | 4.76 | 4.5 | pass | danger pill |
| light | `--warning` on `--bg-sunken` | 5.81 | 4.5 | pass | warning text |
| light | `--warning` on `--warning-bg` | 5.05 | 4.5 | pass | warning pill |
| light | `--ok` on `--bg-sunken` | 5.57 | 4.5 | pass | ok text |
| light | `--ok` on `--ok-bg` | 4.76 | 4.5 | pass | ok pill |
| light | `--fg-muted` on `--neutral-bg` | 5.33 | 4.5 | pass | neutral pill |
| light | `--fg-on-accent` on `--accent` | 5.75 | 4.5 | pass | primary button label |
| light | `--line-strong` on `--bg-sunken` | 3.58 | 3 | pass | input and switch boundaries |
| light | `--line-strong` on `--bg` | 3.23 | 3 | pass | input boundaries on ground |
| light | `--accent` on `--bg` | 5.18 | 3 | pass | focus ring, selection line |

## 4. Type

- Families: `--font-sans` Public Sans (variable, self-hosted), `--font-mono` IBM Plex Mono 400/500 (self-hosted,
  figures only). No third face.
- Scale (fixed, product UI): `--text-xs` 12 · `--text-sm` 13 (body) · `--text-md` 14 (controls, table body on
  large screens) · `--text-lg` 16 (panel titles) · `--text-xl` 20 (section titles, live counts) · `--text-2xl` 26
  (page title). Leading `--leading-tight` 1.25 for headings, `--leading-normal` 1.45 for text.
- Weights: 400 text, 500 labels and table headers, 600 titles. No 700 outside the wordmark.
- `font-variant-numeric: tabular-nums` on the body; the `num` utility switches to mono for figures, IDs and times.
- Sentence case everywhere. No uppercase micro-labels, no letter-spaced captions, no eyebrows above headings.

## 5. Space, shape, density

- 8 px grid with 4 px half-steps: `--space-1` 4 · `--space-2` 8 · `--space-3` 12 · `--space-4` 16 · `--space-5` 24 ·
  `--space-6` 32 · `--space-7` 48. One gap value (16 px) between panels, 24 px page gutter.
- Corners: `--radius-sm` 4 px (controls, pills), `--radius-md` 6 px (panels, tiles, dialogs). `--radius-full` only
  for the status dot and switch thumb.
- Density: table rows `--row-height` 36 px; controls `--control-height` 32 px; rail `--rail-width` 56 px collapsed,
  `--rail-width-open` 208 px open; status strip `--strip-height` 40 px.
- Elevation: borders and tone steps. Only menus, dialogs, drawers, toasts and tooltips cast `--shadow-float`.

## 6. Iconography

Lucide only, 16 px in controls and tables, 20 px in the rail, stroke 1.75. Icons appear where they speed recognition
(rail, toolbar, status), always with a text label or tooltip and an accessible name. No icons in tinted squares, no
emoji, no unicode glyphs as icons.

## 7. Motion (Emil Kowalski)

| token | value | use |
|---|---|---|
| `--dur-press` | 100 ms | press feedback (`press` utility, scale `--press-scale` 0.97) |
| `--dur-fast` | 140 ms | hover, colour changes, tooltip |
| `--dur-ui` | 180 ms | menus, popovers, new incident row, toast |
| `--dur-panel` | 260 ms | drawers and dialogs |
| `--ease-out` | cubic-bezier(0.23, 1, 0.32, 1) | every enter |
| `--ease-in` | cubic-bezier(0.55, 0.06, 0.68, 0.19) | exits (shorter than enters) |
| `--ease-in-out` | cubic-bezier(0.77, 0, 0.175, 1) | elements moving on screen (zone editor zoom) |

Rules: animate only `transform` and `opacity`; never animate from `scale(0)` (start at 0.96 + opacity 0); popovers
grow from their trigger (`transform-origin` from Radix); tooltips skip the delay once one is open; use CSS
transitions (interruptible) rather than keyframes for UI state; exits are faster than enters. A new incident row
slides in 8 px and fades in `--dur-ui`; the status strip's alert segment pulses once. The live video and its
overlays are never animated. `prefers-reduced-motion: reduce` sets every duration to 0 and the press scale to 1.

## 8. Data display

- Tables: rules not stripes; 36 px rows; header 12 px/500 in `--fg-muted`; numbers right-aligned in mono; the
  identity column in `--fg`, everything else may be muted. Selected row: the selection line on its left edge plus
  `--bg-hover`.
- Timestamps: relative ("4 min ago") with the absolute ISO time in a tooltip and `title`; durations as `1m 12s` (compact, aligns in mono).
- Charts (uPlot): one hue per series, the main series in `--fg`, comparison in `--fg-muted`, incidents in their
  state colour; y-scale and dates always shown; 3–5 faint gridlines in `--line`; direct labels instead of a legend
  for one or two series; units in the axis title.
- KPIs are type, not tiles: a label above a 20 px mono figure with its unit; no icons, no sparklines, no trend arrow
  unless the comparison is named ("+3 vs previous hour").
- Empty states say what is missing and what to do next, in one line with one action.

## 9. Components

Primitives in `frontend/src/components/ui/` (Radix where it gives accessibility for free): Button (primary,
secondary, ghost, danger; sizes sm/md), IconButton (always with `aria-label` and tooltip), Input, Textarea, Select,
Switch, Checkbox, Tabs (selection line), SegmentedControl (selection line), Table, StatusPill, Drawer, Dialog,
Tooltip, Toast (Sonner), Kbd, EmptyState, Skeleton, Field (label + hint + error), Slider.

Every interactive primitive has default, hover, focus-visible, active (press), disabled and, where it applies,
loading and error states.

## 10. Do and don't

| Do | Don't |
|---|---|
| Grey interface, colour only for state | Gradients, glows, glass, purple, neon |
| One 1 px selection line | Filled coloured pills for the active tab or nav item |
| Mono for figures, IDs, times | Mono for headings, buttons or "technical" flavour |
| Units on every number, sign on every change | Giant stat cards with invented trends |
| Plain-language empty and error states with the next step | "No data", lorem, placeholder charts |
| Relative time with absolute on hover | Bare unexplained timestamps |
| Confirm or undo every destructive action | Silent deletes |
| Shadow only on floating layers | Shadows or borders on everything |
| Sentence case labels | Uppercase tracked micro-labels, eyebrows, 01/02/03 section numbers |
| Toast once per event, grouped when many | Looping red blink, sound without opt-in |
| Lucide icons with labels or tooltips | Emoji, "AI-powered" badges, icons in tinted circles |
