from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from app.db.models import IncidentRow
from app.db.session import engine


def seed_incidents(n: int = 7) -> list[str]:
    now = datetime.now(UTC)
    ids = []
    with Session(engine()) as s:
        for i in range(n):
            row = IncidentRow(id=f"inc_t{i:03d}", camera_id="cam-x", track_id=i, rule="ppe_missing:helmet" if i % 2 else "intrusion",
                              zone_id="z1", zone_name="Pit", severity="high" if i % 3 == 0 else "medium",
                              started_at=now - timedelta(minutes=i), last_seen_at=now, duration_s=12.0)  # fmt: skip
            s.merge(row)
            ids.append(row.id)
        s.commit()
    return ids


def test_list_filter_paginate_patch(client, auth) -> None:
    ids = seed_incidents()
    page = client.get("/api/v1/incidents?camera_id=cam-x&limit=3").json()
    assert page["total"] == 7 and len(page["items"]) == 3 and page["next_cursor"]
    page2 = client.get(f"/api/v1/incidents?camera_id=cam-x&limit=3&cursor={page['next_cursor']}").json()
    assert {i["id"] for i in page["items"]}.isdisjoint({i["id"] for i in page2["items"]})
    helm = client.get("/api/v1/incidents?camera_id=cam-x&rule=ppe_missing").json()
    assert helm["total"] == 3
    r = client.patch(
        f"/api/v1/incidents/{ids[0]}",
        json={"status": "acknowledged", "note": "Called supervisor"},
        headers=auth,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "acknowledged" and body["notes"][-1]["text"] == "Called supervisor"
    assert (
        client.patch(f"/api/v1/incidents/{ids[0]}", json={"status": "gone"}, headers=auth).status_code == 422
    )
    assert client.get("/api/v1/incidents/nope").status_code == 404
    assert client.get(f"/api/v1/incidents/{ids[0]}/evidence").status_code == 404


def test_reports(client, auth) -> None:
    seed_incidents()
    r = client.get("/api/v1/reports/shift?format=csv")
    assert r.status_code == 200 and r.text.startswith("id,started_at")
    r = client.get("/api/v1/reports/shift?format=pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


def test_analytics_and_model(client) -> None:
    s = client.get("/api/v1/analytics/summary").json()
    assert {"people_now", "unique_people", "incidents", "alert_level"} <= s.keys()
    ts = client.get("/api/v1/analytics/timeseries?bucket=hour").json()
    assert len(ts["points"]) in (24, 25)
    assert "rows" in client.get("/api/v1/analytics/incidents-by-hour").json()
    assert isinstance(client.get("/api/v1/analytics/zones").json(), list)
    m = client.get("/api/v1/model/active").json()
    assert m["loaded"] and "person" in m["classes"]
    assert "runs" in client.get("/api/v1/model/runs").json()
    figs = client.get("/api/v1/model/figures").json()
    assert "class_distribution.png" in figs["dataset"]
    assert client.get("/api/v1/model/figures/dataset/class_distribution.png").status_code == 200
    assert client.get("/api/v1/model/figures/dataset/..%2F..%2FREADME.md").status_code == 404


def test_thresholds(client, auth) -> None:
    t = client.get("/api/v1/settings/thresholds").json()
    t["tracking"]["min_hits"] = 7
    r = client.put("/api/v1/settings/thresholds", json=t, headers=auth)
    assert r.status_code == 200 and r.json()["tracking"]["min_hits"] == 7
    t["ppe"]["absent_below"] = 0.9
    assert client.put("/api/v1/settings/thresholds", json=t, headers=auth).status_code == 422
    assert any(a["action"] == "settings.thresholds" for a in client.get("/api/v1/audit").json())
