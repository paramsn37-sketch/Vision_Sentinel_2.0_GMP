from fastapi.testclient import TestClient

from .conftest import PASSWORD


def anonymous(client: TestClient) -> TestClient:
    # Same app, fresh cookie jar. Not used as a context manager: that would run the lifespan
    # again and shut down the shared services (DB writer, camera threads) on exit.
    return TestClient(client.app)


def test_requires_login(client) -> None:
    r = anonymous(client).get("/api/v1/cameras")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


def test_wrong_password(client) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401 and r.json()["error"]["message"] == "Wrong username or password."


def test_me_and_csrf(client, auth) -> None:
    assert client.get("/api/v1/auth/me").json()["user"] == "admin"
    body = {"camera_id": "x", "name": "z", "polygon": [[0, 0], [1, 0], [1, 1]]}
    r = client.post("/api/v1/zones/validate", json=body)  # no CSRF header
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf"
    assert client.post("/api/v1/zones/validate", json=body, headers=auth).status_code == 200


def test_login_rate_limit(client, services) -> None:
    services.login_limiter._hits.clear()
    c = anonymous(client)
    codes = [
        c.post("/api/v1/auth/login", json={"username": "admin", "password": "x"}).status_code
        for _ in range(6)
    ]
    assert codes[-1] == 429
    services.login_limiter._hits.clear()
    assert PASSWORD


def test_health_is_public(client) -> None:
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert "vs_uptime_seconds" in client.get("/api/v1/metrics").text
