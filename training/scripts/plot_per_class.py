"""Per-class test mAP50 bar chart of the promoted model -> training/reports/figures/per_class_map50.png.

uv run python ../training/scripts/plot_per_class.py ..
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

repo = Path(sys.argv[1])
m = json.loads((repo / "models/model.json").read_text())["metrics_test"]
items = sorted(((c, v["mAP50"]) for c, v in m.items()), key=lambda t: t[1])
fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
ink, muted, grid, bar = "#1f2328", "#5b616e", "#e3e5e8", "#2f6fdf"
ys = range(len(items))
ax.barh(ys, [v for _, v in items], height=0.55, color=bar)
for y, (_, v) in zip(ys, items, strict=True):
    ax.text(v + 0.01, y, f"{v:.2f}", va="center", fontsize=8, color=ink)
ax.set_yticks(list(ys), [c for c, _ in items], fontsize=9, color=ink)
ax.axvline(0.70, color=muted, lw=1, ls=(0, (3, 3)))
ax.text(0.705, len(items) - 0.4, "target 0.70 (helmet, head, vest)", fontsize=7, color=muted, va="bottom")
ax.set_xlim(0, 1)
ax.set_xlabel("mAP50 on the frozen test split (559 images)", fontsize=8, color=muted)
ax.set_title("vs2-y26n: test mAP50 per class", fontsize=10, color=ink, loc="left")
ax.tick_params(axis="x", labelsize=8, colors=muted)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(grid)
ax.xaxis.grid(True, color=grid, lw=0.6)
ax.set_axisbelow(True)
fig.tight_layout()
out = repo / "training/reports/figures/per_class_map50.png"
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out)
print(out)
