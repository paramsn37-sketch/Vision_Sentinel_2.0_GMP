import time

from .conftest import SAMPLES

SQUARE = [[0.2, 0.2], [0.6, 0.2], [0.6, 0.6], [0.2, 0.6]]


def make_camera(client, auth, name="Gate", file="street_corner.mp4", enabled=False) -> dict:
    r = client.post(
        "/api/v1/cameras",
        json={"name": name, "uri": str(SAMPLES / file), "enabled": enabled, "stride": 3},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_camera_crud_and_snapshot(client, auth) -> None:
    cam = make_camera(client, auth)
    assert cam["status"] in ("disabled", "stopped")
    r = client.get(f"/api/v1/cameras/{cam['id']}/snapshot")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and len(r.content) > 1000
    r = client.patch(f"/api/v1/cameras/{cam['id']}", json={"name": "Gate 2"}, headers=auth)
    assert r.json()["name"] == "Gate 2"
    assert (
        client.post("/api/v1/cameras/test", json={"name": "t", "uri": "/nope.mp4"}, headers=auth).json()["ok"]
        is False
    )
    assert client.delete(f"/api/v1/cameras/{cam['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/cameras/{cam['id']}/snapshot").status_code == 404


def test_zone_crud_validation_and_yaml(client, auth) -> None:
    cam = make_camera(client, auth, "Yard")
    body = {
        "camera_id": cam["id"],
        "name": "Pit",
        "kind": "restricted",
        "polygon": SQUARE,
        "rules": {"no_entry": True},
        "severity": "high",
    }
    r = client.post("/api/v1/zones", json=body, headers=auth)
    assert r.status_code == 201, r.text
    zid = r.json()["id"]
    bad = {**body, "polygon": [[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]]}
    r = client.post("/api/v1/zones", json=bad, headers=auth)
    assert r.status_code == 422 and "crosses itself" in r.json()["error"]["message"]
    v = client.post("/api/v1/zones/validate", json=bad, headers=auth).json()
    assert v["valid"] is False
    r = client.put(f"/api/v1/zones/{zid}", json={**body, "name": "Pit edge"}, headers=auth)
    assert r.json()["name"] == "Pit edge"
    exported = client.get(f"/api/v1/zones/export?camera_id={cam['id']}").text
    assert "Pit edge" in exported
    r = client.post(
        f"/api/v1/zones/import?camera_id={cam['id']}",
        content=exported,
        headers={**auth, "content-type": "application/yaml"},
    )
    assert r.status_code == 200, r.text
    assert len(client.get(f"/api/v1/zones?camera_id={cam['id']}").json()) == 2
    assert client.delete(f"/api/v1/zones/{zid}", headers=auth).status_code == 204


def test_running_camera_streams_frames_and_raises_incident(client, auth, services) -> None:
    """End to end on real footage: a no-entry zone over the lower half of the town square must catch people."""
    cam = make_camera(client, auth, "Square", "town_square.mp4", enabled=False)
    zone = {"camera_id": cam["id"], "name": "Plaza", "kind": "restricted", "polygon": [[0, 0.5], [1, 0.5], [1, 1], [0, 1]],
            "rules": {"no_entry": True}, "severity": "high"}  # fmt: skip
    assert client.post("/api/v1/zones", json=zone, headers=auth).status_code == 201
    assert client.post(f"/api/v1/cameras/{cam['id']}/start", headers=auth).status_code == 200
    frames = 0
    with client.websocket_connect(f"/ws/live?camera_id={cam['id']}&fps=30") as ws:
        meta = None
        deadline = time.time() + 120
        while frames < 10 and time.time() < deadline:
            msg = ws.receive()
            if msg.get("text"):
                import json

                data = json.loads(msg["text"])
                if data["type"] == "frame":
                    meta = data
            elif msg.get("bytes"):
                assert msg["bytes"][:2] == b"\xff\xd8"  # JPEG
                frames += 1
    assert frames >= 10
    assert (
        meta is not None and meta["width"] > 0 and "persons" in meta and meta["zones"][0]["name"] == "Plaza"
    )
    deadline = time.time() + 120
    items = []
    while time.time() < deadline and not items:
        services.writer.drain()
        items = client.get(f"/api/v1/incidents?camera_id={cam['id']}").json()["items"]
        time.sleep(1)
    info = services.cameras.get(cam["id"]).info()
    in_memory = len(services.cameras.get(cam["id"]).incidents.all())
    client.post(f"/api/v1/cameras/{cam['id']}/stop", headers=auth)
    assert items, (
        f"a no-entry zone over a busy square should raise an intrusion incident ({info}, {in_memory} in memory)"
    )
    assert items[0]["rule"] == "intrusion" and items[0]["zone_name"] == "Plaza"
