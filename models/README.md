# models/

The active detector. `model.json` names the weights file, its classes, per-class thresholds, input size and the
test metrics it was promoted with; it is written by `training/scripts/export.py`. Without `model.json` the backend
runs the stock COCO nano model in person-only mode. The Docker image copies this folder at build time.
