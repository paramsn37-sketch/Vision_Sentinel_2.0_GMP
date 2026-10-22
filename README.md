# Vision Sentinel 2.0

Real-time industrial safety monitoring: PPE compliance per tracked person, polygon-zone intrusion detection, and
explainable alerts (Grad-CAM). A rebuild from scratch of the v1 college prototype.

**Status:** blueprint and build plan ready; implementation not started.

| Document | Purpose |
|---|---|
| [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) | What we are building and why (architecture, model, tracking, zones, XAI, UI, quality bar) |
| [`BUILD_PROMPTS.md`](BUILD_PROMPTS.md) | 13 phases Claude Code runs unattended, each with tasks and acceptance gates |
| [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) | Summary appended after every phase |
| [`docs/build_state.json`](docs/build_state.json) | Machine-readable phase status, used to resume |

## Running the build

1. Open this repo in Claude Code. A GPU machine gives the best model; without one the build trains a
   smaller model on a time budget and ships a Colab notebook for the full run.
2. Optional, for more training data: set `KAGGLE_USERNAME`, `KAGGLE_KEY` and `ROBOFLOW_API_KEY` as environment
   variables (never commit them). Without them the build uses public sources only.
3. Allow the session to run commands without prompting (it is unattended), then paste the kickoff prompt from the top
   of `BUILD_PROMPTS.md`.
4. If the session ends early, start a new one with the same kickoff prompt: it resumes from `docs/build_state.json`.
