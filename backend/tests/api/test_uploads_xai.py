import time
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "images"


def wait_upload(client, uid: str, timeout: float = 300) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        u = client.get(f"/api/v1/uploads/{uid}").json()
        if u["status"] in ("done", "failed"):
            return u
        time.sleep(0.5)
    raise AssertionError("upload did not finish")


def test_image_upload_runs_real_model_and_explains(client, auth) -> None:
    img = next(p for p in sorted(FIXTURES.glob("construction_ppe*.jpg")))
    r = client.post(
        "/api/v1/uploads", files={"file": (img.name, img.read_bytes(), "image/jpeg")}, headers=auth
    )
    assert r.status_code == 202, r.text
    u = wait_upload(client, r.json()["id"])
    assert u["status"] == "done", u
    res = u["result"]
    assert res["frames"] == 1 and res["model"]
    assert client.get(f"/api/v1/uploads/{u['id']}/annotated").status_code == 200
    kf = res["keyframes"][0]
    if not kf["persons"]:
        pytest.skip("no person detected in this fixture by the current model")
    p = kf["persons"][0]
    job = client.post("/api/v1/xai", json={"source": "upload", "upload_id": u["id"], "frame_idx": 0, "box": p["box"], "cls": "person"},
                      headers=auth).json()  # fmt: skip
    deadline = time.time() + 120
    while job["status"] not in ("done", "failed") and time.time() < deadline:
        time.sleep(0.5)
        job = client.get(f"/api/v1/xai/{job['id']}").json()
    assert job["status"] == "done", job
    assert job["meta"]["method"] in ("hirescam", "gradcam") and 0 <= job["meta"]["energy_in_box"] <= 1
    assert client.get(job["overlay_url"]).headers["content-type"] == "image/jpeg"


def test_rejects_unsupported_file(client, auth) -> None:
    r = client.post("/api/v1/uploads", files={"file": ("notes.txt", b"hello", "text/plain")}, headers=auth)
    assert r.status_code == 415


def test_xai_needs_target(client, auth) -> None:
    r = client.post("/api/v1/xai", json={"source": "live", "camera_id": "nope", "frame_idx": 1}, headers=auth)
    assert r.status_code == 410


@pytest.mark.slow
def test_video_upload_counts_people(client, auth) -> None:
    """street_corner.mp4 has 22 ground-truth pedestrians (MOT17-09). The count must be in the right range, not
    the hundreds a per-frame count would give."""
    from .conftest import SAMPLES

    clip = SAMPLES / "street_corner.mp4"
    r = client.post(
        "/api/v1/uploads", files={"file": (clip.name, clip.read_bytes(), "video/mp4")}, headers=auth
    )
    u = wait_upload(client, r.json()["id"], timeout=1800)
    assert u["status"] == "done"
    assert 15 <= u["result"]["unique_people"] <= 30
