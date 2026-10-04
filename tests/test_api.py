"""API smoke tests (FastAPI TestClient + FakeModels)."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from dam.app import create_app
from dam.models import FakeModels

from .test_pipeline import env  # noqa: F401  (fixture)


def _wait(client, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get("/api/index/status").json()
        if not s["running"]:
            return s
        time.sleep(0.1)
    raise AssertionError("indexing did not finish")


def test_api_flow(env):  # noqa: F811
    cfg, db, _models, media = env
    client = TestClient(create_app(cfg, FakeModels(cfg)))

    assert client.get("/").status_code == 200
    r = client.post("/api/index/start", json={"root": str(media)}).json()
    assert r["started"]
    s = _wait(client)
    assert s["job"]["state"] == "finished" and s["asset_status"]["done"] == 6

    res = client.get("/api/search", params={"q": "red picture"}).json()
    top = res["results"][0]
    assert top["filename"] in ("IMG_re01.jpg", "copy_of_photo.jpg")
    assert client.get(f"/thumbs/{top['thumb']}").status_code == 200
    assert client.get(f"/api/file/{top['file_id']}").status_code == 200
    d = client.get(f"/api/assets/{top['hash']}").json()
    assert len(d["files"]) == 2  # original + duplicate

    # type filter + video range request (needed for video seeking in the browser)
    vids = client.get("/api/search", params={"q": "green", "kinds": "video"}).json()["results"]
    assert vids and all(v["kind"] == "video" for v in vids)
    rr = client.get(f"/api/file/{vids[0]['file_id']}", headers={"Range": "bytes=0-99"})
    assert rr.status_code == 206

    f = client.get("/api/failures").json()
    assert len(f["failed"]) == 2 and any(x["file_status"] == "unsupported" for x in f["skipped"])
    st = client.get("/api/stats").json()
    assert st["duplicate_files"] == 1

    # second run is incremental
    client.post("/api/index/start", json={"root": str(media)})
    s = _wait(client)
    assert s["job"]["processed"] == 0 and s["job"]["skipped"] > 0

    # evaluation endpoints
    ev = client.get("/api/eval").json()
    assert ev["summary"]["queries"] >= 10
    q0 = ev["queries"][0]
    for r_ in q0["results"][:5]:
        client.post("/api/eval/judge", json={"query": q0["query"], "hash": r_["hash"], "relevant": True})
    ev = client.get("/api/eval").json()
    assert ev["queries"][0]["metrics"]["p_at_k"] == 1.0
