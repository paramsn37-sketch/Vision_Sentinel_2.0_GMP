# Decision records

Short ADRs. Format: context → decision → consequences. Newest at the bottom.

## ADR-0001 — Monorepo and stack
- **Context:** the blueprint asks for a lightweight but production-quality system that one person can run.
- **Decision:** one repo with `backend/` (FastAPI, SQLite, Ultralytics), `frontend/` (React + Vite), `training/`.
  Python 3.12 via `uv` (3.13 works but some wheels lag), Node 22.
- **Consequences:** one `Makefile` drives everything; no broker, no external database.

## ADR-0002 — Licence: AGPL-3.0
- **Context:** Ultralytics (detector, trainer) is AGPL-3.0; the Construction-PPE dataset is AGPL-3.0.
- **Decision:** license the project AGPL-3.0.
- **Consequences:** fine for academic/open use; a commercial closed deployment needs an Ultralytics licence.

## ADR-0003 — oxlint instead of ESLint
- **Context:** Vite 8's template ships oxlint; ESLint adds ~150 packages.
- **Decision:** keep oxlint + `tsc --noEmit` + Prettier.
- **Consequences:** fewer lint rules than ESLint's React plugins, much faster and lighter.

## ADR-0004 — Training environment and data sources
- **Context:** the build container has 4 CPU cores, 15 GB RAM, no GPU. Its network policy allows GitHub release
  assets (Ultralytics weights and datasets, boxmot's MOT17 subset), Open Images (Google Storage + S3) and PyPI/npm,
  but blocks Kaggle, Roboflow, Hugging Face and motchallenge.net. No Kaggle/Roboflow credentials are set.
- **Decision:** training mode `cpu-budget` (blueprint §4.4). Data: Ultralytics Construction-PPE + a capped Open
  Images V7 subset. Counting evaluation on the MOT17 half-length subset published as a boxmot release asset.
- **Consequences:** a smaller model trained for fewer epochs than the GPU plan; the Colab notebook reproduces the full
  plan with SH17/Roboflow data. All numbers in reports are from this setup and say so.

## ADR-0005 — Design skills
- **Context:** the UI must be built with impeccable, Emil Kowalski's design-engineering skills, Taste and Playwright.
- **Decision:** vendored into `.claude/skills/` (MIT / Apache-2.0 licences kept beside them):
  `impeccable` (direction, critique, audit, polish), `emil-design-eng`, `review-animations`, `improve-animations`,
  `ask-sonner`, `animation-performance` (motion and interaction craft), `taste-skill` (anti-generic constraints).
  Playwright via `@playwright/test` with the preinstalled Chromium.
- **How they are applied:** impeccable sets the direction and runs critique/audit passes on Playwright screenshots;
  Taste supplies the typography/spacing/colour checklist used in every review round; Emil's skills define motion
  tokens (durations, easings), toasts (Sonner) and review recorded interactions; Playwright captures screenshots at
  four widths and two themes, runs axe and holds visual baselines.
