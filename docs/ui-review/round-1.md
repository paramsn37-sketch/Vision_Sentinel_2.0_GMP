# UI review, round 1

Set reviewed: `frontend/e2e/__screenshots__/visual/` (7 routes × 1440/1024/768/390 px × dark/light, plus key
states: incident drawer, explanation panel, zone editor mid-draw), captured from the running stack with live data.
Checks: impeccable critique and audit points (hierarchy, density, copy, states), Taste checklist (signature line,
tone steps, no decoration), Emil Kowalski motion rules (entry/exit asymmetry, reduced motion), axe on every route.

| # | Finding | Screen | Severity | Fix | Status |
|---|---|---|---|---|---|
| 1 | Every route scrolled sideways below 1280 px: the status strip did not shrink | all | high | strip hides items by priority (model, fps, unique, cameras, clock), clips overflow; "Go to" collapses to an icon | fixed |
| 2 | Live wall and side panel overlapped at phone width | Live 390/768 | high | below 1024 px the page stacks: tiles one column at fixed height, overview panel below | fixed |
| 3 | Three-pane zone editor unusable below 1024 px | Zones 390/768 | high | panes stack: list, canvas (fixed height), form | fixed |
| 4 | Incidents table needed sideways scrolling on phones | Incidents 390 | medium | columns drop by priority; zone and camera fold into a second line in the row | fixed |
| 5 | Light theme hint text and dark hover timestamps under 4.5:1 | Settings, Model | high | `--fg-subtle` darkened (light) / lightened (dark); contrast checker now also tests subtle on ground and hover | fixed |
| 6 | Rail incidents link: visible badge number not in its accessible name; badge overlapped the icon | all | medium | link named "Incidents, N open", badge moved to the icon's top-right corner | fixed |
| 7 | Incident list scroll area not reachable by keyboard | Incidents | medium | scroll region is focusable and named | fixed |
| 8 | Hours with no camera running drawn as zero (peak line fell to 0 for every empty hour) | Analytics | high (misleading data) | API marks buckets `observed`; charts draw gaps, tooltips say "no data"; isolated points get a dot | fixed |
| 9 | Chart unit label overlapped the top tick | Analytics | medium | top padding reserves a row for the unit | fixed |
| 10 | People's foot markers in the editor looked like vertex handles | Zones (drawing) | medium | foot markers are small solid dots; handles stay hollow | fixed |
| 11 | Required-PPE checkboxes mixed lower and sentence case | Zones form | low | sentence case labels | fixed |
| 12 | "Choose a zone on the left" is wrong when panes stack | Zones 390 | low | "from the list" | fixed |
| 13 | Compliance showed 0 % from stale rows written before the person-only fix | Live, Analytics | high (wrong number) | code already fixed in Phase 8; demo runtime database reset | fixed |
| 14 | Dropzone's aria-label did not include its visible text | Uploads | medium | name comes from the visible text | fixed |
| 15 | "Unique today" grows quickly on the demo because the sample clips loop and each loop is new people | Live, strip | low | expected with looping files; stated in README and user guide | open (documented) |

Motion: overlays use keyframes with shorter `ease-in` exits than `ease-out` entries; `prefers-reduced-motion` sets
every duration token to 0 ms (`e2e/a11y.spec.ts` checks this). No high or medium findings remain open.
