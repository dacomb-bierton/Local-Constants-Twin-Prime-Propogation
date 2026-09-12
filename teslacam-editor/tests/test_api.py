import time

import pytest
from fastapi.testclient import TestClient

from teslacam_editor.app import app


@pytest.fixture(scope="module")
def client(teslacam_root):
    with TestClient(app) as c:
        r = c.post("/api/library/scan", json={"root": str(teslacam_root)})
        assert r.status_code == 200
        yield c


def _saved(client):
    events = client.get("/api/library").json()["events"]
    return next(e for e in events if e["kind"] == "SavedClips")


def test_config_and_library(client):
    cfg = client.get("/api/config").json()
    assert "9:16" in cfg["aspects"] and "pip" in cfg["layouts"]
    lib = client.get("/api/library").json()
    assert len(lib["events"]) == 4
    assert "segments" not in lib["events"][0]


def test_event_detail_and_thumb(client):
    ev = _saved(client)
    detail = client.get(f"/api/events/{ev['id']}").json()
    assert len(detail["segments"]) == 3
    assert 8 < detail["duration"] < 10  # probed, not the 60 s placeholder
    thumb = client.get(f"/api/events/{ev['id']}/thumb?t=1.5&camera=back")
    assert thumb.status_code == 200 and thumb.headers["content-type"].startswith("image/")
    assert client.get("/api/events/nope").status_code == 404


def test_media_range_requests(client):
    ev = _saved(client)
    full = client.get(f"/api/media/{ev['id']}/0/front")
    assert full.status_code == 200 and full.headers["accept-ranges"] == "bytes"
    size = int(full.headers["content-length"])
    part = client.get(f"/api/media/{ev['id']}/0/front", headers={"Range": "bytes=100-199"})
    assert part.status_code == 206
    assert part.headers["content-range"] == f"bytes 100-199/{size}"
    assert len(part.content) == 100
    assert client.get(f"/api/media/{ev['id']}/0/front", headers={"Range": f"bytes={size + 10}-"}).status_code == 416
    assert client.get(f"/api/media/{ev['id']}/9/front").status_code == 404


def test_layout_endpoint(client):
    data = client.get("/api/layout", params={"layout": "grid", "cameras": "front,back,left_repeater", "main": "back", "aspect": "1:1"}).json()
    assert data["canvas"]["w"] == data["canvas"]["h"]
    assert {t["camera"] for t in data["tiles"]} == {"front", "back", "left_repeater"}


def test_export_job_roundtrip(client, tmp_path):
    ev = _saved(client)
    project = {
        "name": "api",
        "items": [{"id": "x", "event_id": ev["id"], "in_point": 0, "out_point": 2, "cameras": ["front", "back"], "layout": "side",
                   "main_camera": "front", "cycle_enabled": True, "cycle_interval": 1}],
        "export": {"aspect": "9:16", "resolution": 240, "fps": 12, "quality": "draft", "output_dir": str(tmp_path)},
    }
    job_id = client.post("/api/export", json={"project": project}).json()["job_id"]
    for _ in range(600):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["state"] in ("done", "error", "cancelled"):
            break
        time.sleep(0.1)
    assert job["state"] == "done", job
    assert job["output"].endswith(".mp4")
    out = client.get("/api/output", params={"path": job["output"]})
    assert out.status_code == 200
    assert client.post("/api/export", json={"project": {"items": []}}).status_code == 400


def test_still_and_projects(client, tmp_path):
    ev = _saved(client)
    r = client.post("/api/still", json={"event_id": ev["id"], "time": 1.0, "cameras": ["front"], "aspect": "1:1", "resolution": 200, "output_dir": str(tmp_path)})
    assert r.status_code == 200 and r.json()["output"].endswith(".jpg")
    proj = {"name": "p", "items": [], "export": {"aspect": "4:3"}}
    assert client.put("/api/projects/My%20Project", json=proj).status_code == 200
    names = [p["name"] for p in client.get("/api/projects").json()]
    assert "My Project" in names
    loaded = client.get("/api/projects/My%20Project").json()
    assert loaded["export"]["aspect"] == "4:3" and loaded["name"] == "My Project"
    assert client.delete("/api/projects/My%20Project").status_code == 200


def test_browse_and_raw_export(client, teslacam_root, tmp_path):
    listing = client.get("/api/browse", params={"path": str(teslacam_root)}).json()
    assert listing["is_teslacam"]
    ev = _saved(client)
    r = client.post("/api/export_raw", json={"event_id": ev["id"], "cameras": ["front"], "output_dir": str(tmp_path)})
    assert r.status_code == 200 and len(r.json()["outputs"]) == 1
