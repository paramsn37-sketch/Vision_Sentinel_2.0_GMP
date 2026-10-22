"""Failure handling that must not take the service down (Phase 11)."""

from pathlib import Path

from app.services.runtime import disk_has_room


def test_disk_guard(tmp_path: Path) -> None:
    assert disk_has_room(tmp_path, need=1)
    assert not disk_has_room(tmp_path, need=1 << 62)  # more than any disk
    assert not disk_has_room(tmp_path / "missing" / "dir")


def test_corrupt_upload_is_rejected_cleanly(client, auth) -> None:
    r = client.post(
        "/api/v1/uploads", files={"file": ("broken.mp4", b"not a video at all", "video/mp4")}, headers=auth
    )
    if r.status_code in (200, 201, 202):
        from .test_uploads_xai import wait_upload

        u = wait_upload(client, r.json()["id"], timeout=60)
        assert u["status"] == "failed" and u["error"]
    else:
        assert r.status_code in (400, 415, 422) and r.json()["error"]["message"]
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_retention_removes_only_old_files(tmp_path: Path) -> None:
    import os
    import time

    from app.services.runtime import retention_cleanup
    from app.services.storage import Paths

    paths = Paths(tmp_path).ensure()
    old, new = paths.snapshots / "old.jpg", paths.xai / "new.png"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    past = time.time() - 40 * 86400
    os.utime(old, (past, past))
    assert retention_cleanup(paths, days=30) == 1
    assert not old.exists() and new.exists()
