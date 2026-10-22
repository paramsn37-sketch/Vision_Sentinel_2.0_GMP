# Product

<!-- impeccable:product-schema 1 -->

> Written during the unattended build (Phase 7). The owner asked for the build to run without stopping for
> questions, so every fact below comes from the owner's brief and `docs/BLUEPRINT.md`. Facts marked
> *(inferred)* were not stated by the owner and should be confirmed.

## Platform

web

## Users

- **Safety officer / control-room operator** on a shift: watches several camera feeds on a large screen or a
  laptop, acknowledges and resolves incidents, and explains them to supervisors. Sessions last hours, often in a
  dimmed room *(inferred from "control room")*.
- **Site safety lead** who draws zones, sets PPE rules and thresholds, and exports shift reports.
- **Reviewer / examiner** of the project who checks that counts, detections and explanations are real and measured.

## Product Purpose

Vision Sentinel watches site cameras and tells people, in real time, who is on site, whether they wear the required
PPE, and when someone enters a zone they must not. Every alert can be explained (Grad-CAM on the exact detection)
and audited. Success: counts that match reality (unique people, not people-per-frame), alerts that are rare enough
to be trusted, and an operator who can go from alert to evidence to decision in seconds.

## Positioning

A lightweight, self-hosted, single-machine safety monitor whose numbers are measured and published (dataset card,
training report, counting and XAI evaluations) instead of claimed. It explains each alert on the detection that
raised it.

## Operating Context

- Live camera wall, incident queue, zone editor on a frozen camera frame, shift analytics and PDF/CSV reports.
- Runs on one PC or a small server, CPU-only is supported; the browser connects over the LAN.
- Demo footage: MOT17 street scenes and Construction-PPE still images (real data, licences in
  `data/samples/LICENSES.md`).

## Capabilities and Constraints

- Detection classes: person, head, helmet, vest, gloves, hand, boots, goggles, no_goggles. No face-mask class.
- Unique people via tracking with confirmation; PPE state smoothed over time; zones are normalised polygons with
  rules (no entry, required PPE, max occupancy, max dwell, active hours).
- Single admin account; English only *(inferred)*.
- Must not show invented numbers: anything not measured is shown as "not measured".

## Brand Commitments

- Name: **Vision Sentinel 2.0**. No existing logo or palette; v1's look is an anti-reference.
- Owner's binding constraints: "standard industrial app and UI", lightweight, not generic "AI slop".
- Safety colours follow ISO 3864 meanings (red danger, amber warning, green safe, blue information).

## Evidence on Hand

- `data/DATASET_CARD.md`, `docs/eval/counting_report.md`, `docs/eval/xai_report.md`, `training/registry.json`,
  model card and training report (Phase 2). No customer logos, testimonials or deployments exist; never invent them.

## Product Principles

1. Every number is measured, has a unit, and says what it counts.
2. Colour means state. Grey carries the interface; red, amber, green and blue only when something is in that state.
3. An alert is one decision: see it, check the evidence, acknowledge or resolve.
4. Calm under load: nothing blinks forever, nothing moves unless state changed.

## Accessibility & Inclusion

WCAG 2.2 AA minimum; numbers on the live wall at AAA contrast. Full keyboard operation including the zone editor.
`prefers-reduced-motion` respected.
