# Vision Sentinel 2.0 — developer entry points
BACKEND := backend
FRONTEND := frontend
UV := cd $(BACKEND) && uv run

.PHONY: setup dev backend frontend lint typecheck test test-backend test-frontend e2e eval train api-types docker clean

setup:
	cd $(BACKEND) && uv sync --all-groups
	cd $(FRONTEND) && npm ci

dev:
	$(MAKE) -j2 backend frontend

backend:
	$(UV) uvicorn app.main:app --host 0.0.0.0 --port 8000

frontend:
	cd $(FRONTEND) && npm run dev

lint:
	$(UV) ruff check . ../training ../scripts && uv run ruff format --check . ../training ../scripts
	cd $(FRONTEND) && npm run lint

typecheck:
	$(UV) mypy app/core
	cd $(FRONTEND) && npm run typecheck

test: test-backend test-frontend

test-backend:
	$(UV) pytest -m "not slow and not model"

test-model:
	$(UV) pytest -m model

test-frontend:
	cd $(FRONTEND) && npm run test

e2e:
	cd $(FRONTEND) && npx playwright test

eval:
	$(UV) python -m eval.counting_eval
	$(UV) python -m eval.xai_eval

train:
	$(UV) python ../training/scripts/train.py --hyp ../training/configs/hyp_cpu_budget.yaml --name vs2-y26n-cpu

api-types:
	$(UV) python -c "import json; from app.main import create_app; print(json.dumps(create_app(start_cameras=False).openapi()))" > $(CURDIR)/$(FRONTEND)/openapi.json
	cd $(FRONTEND) && npx --yes openapi-typescript@7 openapi.json -o src/lib/api/schema.ts && rm openapi.json

docker:
	docker compose build

clean:
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache $(BACKEND)/.mypy_cache $(FRONTEND)/dist
