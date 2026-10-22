"""Update docs/build_state.json from the command line (used at the start and end of every build phase).

python scripts/phase_state.py start 3
python scripts/phase_state.py done 3 --status done --note "..." --gate "pytest=pass"
"""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

STATE = Path(__file__).resolve().parents[1] / "docs" / "build_state.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["start", "done"])
    ap.add_argument("phase", type=int)
    ap.add_argument("--status", default="done")
    ap.add_argument("--note", default="")
    ap.add_argument("--gate", action="append", default=[], help="name=result")
    ap.add_argument("--followup", action="append", default=[])
    args = ap.parse_args()

    state = json.loads(STATE.read_text())
    phase = state["phases"][args.phase]
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.action == "start":
        phase["status"], phase["started_at"] = "in_progress", phase["started_at"] or now
    else:
        phase["status"], phase["finished_at"] = args.status, now
        phase["commit"] = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip()
        phase["gate_results"].update(dict(g.split("=", 1) for g in args.gate))
    if args.note:
        phase["notes"] = args.note
    state["followups"] += args.followup
    STATE.write_text(json.dumps(state, indent=2) + "\n")


if __name__ == "__main__":
    main()
