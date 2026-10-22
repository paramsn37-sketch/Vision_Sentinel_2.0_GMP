"""API test app: real services (real model, real pipelines) on a temporary data directory."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.state import AppServices
from app.settings import Settings

REPO = Path(__file__).resolve().parents[3]
SAMPLES = REPO / "data" / "samples"
PASSWORD = "test-password-123"


@pytest.fixture(scope="session")
def services(tmp_path_factory) -> AppServices:
    tmp = tmp_path_factory.mktemp("vs")
    settings = Settings(
        admin_password=PASSWORD, secret_key="test-secret", storage={"data_dir": tmp}, demo={"seed": False}
    )
    return AppServices.create(settings)


@pytest.fixture(scope="session")
def client(services) -> TestClient:
    app = create_app(services, start_cameras=False)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"x-csrf-token": r.json()["csrf_token"]}
