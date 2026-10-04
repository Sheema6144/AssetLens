"""End-to-end tests of ingestion, incremental indexing, failure handling and search.

Uses FakeModels (no downloads) so the suite runs in seconds anywhere:
    pytest -q
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from dam.config import Settings
from dam.db import DB
from dam.indexer import Indexer
from dam.models import FakeModels
from dam.search import Searcher, parse_query

COLORS = {"red": (220, 30, 30), "green": (30, 180, 30), "blue": (30, 30, 220), "yellow": (230, 220, 30)}


def make_video(path: Path, colors: list[tuple[int, int, int]], seconds_each: int = 3, fps: int = 10):
    import cv2

    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (160, 120))
    for c in colors:
        frame = np.zeros((120, 160, 3), np.uint8)
        frame[:] = c[::-1]  # BGR
        for _ in range(seconds_each * fps):
            w.write(frame)
    w.release()


def make_pdf(path: Path, text: str, color=(1, 1, 1)):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_rect(page.rect, color=color, fill=color)
    page.insert_text((72, 100), text, fontsize=14)
    doc.save(str(path))


@pytest.fixture()
def env(tmp_path):
    media = tmp_path / "media"
    (media / "photos").mkdir(parents=True)
    (media / "videos").mkdir()
    (media / "docs").mkdir()
    (media / "backup").mkdir()
    for name, c in COLORS.items():
        Image.new("RGB", (64, 48), c).save(media / "photos" / f"IMG_{name[:2]}01.jpg")
    make_video(media / "videos" / "clip001.mp4", [COLORS["green"], COLORS["blue"]])
    make_pdf(media / "docs" / "doc1.pdf", "Luxury residential apartments brochure. Yellow sunny homes for families.")
    shutil.copy(media / "photos" / "IMG_re01.jpg", media / "backup" / "copy_of_photo.jpg")  # duplicate
    (media / "photos" / "broken.jpg").write_bytes(b"\xff\xd8\xff\xe0 this is not really a jpeg")  # corrupt
    (media / "docs" / "notes.txt").write_text("unsupported")
    (media / "videos" / "bad.mp4").write_bytes(os.urandom(2048))  # corrupt video

    cfg = Settings(media_dir=media, data_dir=tmp_path / "data")
    cfg.enable_captions = True
    cfg.ensure_dirs()
    db = DB(cfg.db_path)
    models = FakeModels(cfg)
    return cfg, db, models, media


def test_full_index_and_metadata(env):
    cfg, db, models, media = env
    res = Indexer(db, models, cfg).run()
    assert res["state"] == "finished"
    assert res["scan"]["duplicates"] == 1
    assert res["scan"]["unsupported"] == 1
    # 4 images + 1 video + 1 pdf processed, broken.jpg + bad.mp4 failed
    assert res["processed"] == 6
    assert res["failed"] == 2
    f = db.one("SELECT * FROM files WHERE filename='IMG_bl01.jpg'")
    assert f["kind"] == "image" and f["size"] > 0 and f["folder"].endswith("photos") and len(f["hash"]) == 64
    v = db.one("SELECT a.meta FROM assets a JOIN files f ON f.hash=a.hash WHERE f.filename='clip001.mp4'")
    import json

    meta = json.loads(v["meta"])
    assert meta["duration"] == pytest.approx(6, abs=0.5)
    assert 2 <= meta["frames_sampled"] <= cfg.video_max_frames


def test_failures_are_recorded_and_not_retried(env):
    cfg, db, models, media = env
    Indexer(db, models, cfg).run()
    failed = db.q("SELECT a.error FROM assets a WHERE status='failed'")
    errors = " ".join(r["error"] for r in failed)
    assert "corrupt" in errors
    unsupported = db.one("SELECT file_status, file_error FROM files WHERE filename='notes.txt'")
    assert unsupported["file_status"] == "unsupported" and ".txt" in unsupported["file_error"]
    # second run: corrupt files are not retried (they would fail again)
    res2 = Indexer(db, models, cfg).run()
    assert res2["processed"] == 0 and res2["failed"] == 0


def test_incremental_reindex_skips_unchanged(env):
    cfg, db, models, media = env
    Indexer(db, models, cfg).run()
    calls_before = models.calls["clip_image"]
    res = Indexer(db, models, cfg).run()
    assert res["processed"] == 0
    assert res["scan"]["unchanged"] == res["scan"]["seen"]
    assert models.calls["clip_image"] == calls_before  # no AI work at all

    # change one file -> only that file is processed
    time.sleep(0.01)
    Image.new("RGB", (64, 48), (10, 10, 10)).save(media / "photos" / "IMG_gr01.jpg")
    res = Indexer(db, models, cfg).run()
    assert res["processed"] == 1 and res["scan"]["changed"] == 1

    # add a new file -> only that one
    Image.new("RGB", (64, 48), COLORS["blue"]).rotate(1).save(media / "photos" / "new.png")
    res = Indexer(db, models, cfg).run()
    assert res["processed"] == 1 and res["scan"]["new"] == 1


def test_duplicates_processed_once_and_grouped(env):
    cfg, db, models, media = env
    Indexer(db, models, cfg).run()
    h = db.one("SELECT hash FROM files WHERE filename='copy_of_photo.jpg'")["hash"]
    assert db.one("SELECT COUNT(*) n FROM files WHERE hash=?", (h,))["n"] == 2
    assert db.one("SELECT COUNT(*) n FROM assets WHERE hash=?", (h,))["n"] == 1
    res = Searcher(db, models).search("red", top_k=5)
    top = res["results"][0]
    assert top["hash"] == h and len(top["duplicates"]) == 1


def test_crash_recovery(env):
    cfg, db, models, media = env
    Indexer(db, models, cfg).run()
    # simulate a crash in the middle of processing one asset
    h = db.one("SELECT hash FROM files WHERE filename='IMG_bl01.jpg'")["hash"]
    db.exec("UPDATE assets SET status='processing' WHERE hash=?", (h,))
    res = Indexer(db, models, cfg).run()
    assert res["processed"] == 1
    assert db.one("SELECT status FROM assets WHERE hash=?", (h,))["status"] == "done"


def test_caption_model_failure_is_non_fatal(env):
    cfg, db, _, media = env
    models = FakeModels(cfg, fail_captions=True)
    res = Indexer(db, models, cfg).run()
    assert res["processed"] == 6
    w = db.one("SELECT warnings FROM assets a JOIN files f ON f.hash=a.hash WHERE f.filename='IMG_bl01.jpg'")["warnings"]
    assert "captioning failed" in w
    # still searchable via visual embeddings
    top2 = [r["filename"] for r in Searcher(db, models).search("blue")["results"][:2]]
    assert "IMG_bl01.jpg" in top2


def test_model_load_failure_stops_job_cleanly(env):
    cfg, db, models, media = env
    from dam.models import ModelError

    class Broken(FakeModels):
        def warmup(self):
            raise ModelError("no internet to download CLIP")

    with pytest.raises(ModelError):
        Indexer(db, Broken(cfg), cfg).run()
    assert db.one("SELECT COUNT(*) n FROM assets WHERE status='failed'")["n"] == 0
    assert db.last_job()["state"] == "error"
    # next run with working models processes everything
    assert Indexer(db, models, cfg).run()["processed"] == 6


def test_search_ranking_filters_and_video_timestamp(env):
    cfg, db, models, media = env
    Indexer(db, models, cfg).run()
    s = Searcher(db, models)
    assert s.search("a yellow picture")["results"][0]["filename"] == "IMG_ye01.jpg"
    # video: best frame for "blue" must be in the second half (blue starts at 3s)
    r = s.search("blue", {"kinds": ["video"]})["results"]
    assert r and r[0]["kind"] == "video"
    assert r[0]["match"]["visual"]["ref"] >= 3
    # type intent from the query
    res = s.search("videos with green")
    assert res["detected_type"] == "video" and res["results"][0]["kind"] == "video"
    # pdf text search
    res = s.search("brochures about residential homes")
    assert res["detected_type"] == "pdf" and res["results"][0]["kind"] == "pdf"
    # filters
    assert all(x["kind"] == "image" for x in s.search("red", {"kinds": ["image"]})["results"])
    assert s.search("red", {"min_mb": 100})["results"] == []
    assert all("backup" in x["folder"] for x in s.search("", {"folder": "backup"})["results"])


def test_deleted_files_disappear_from_search(env):
    cfg, db, models, media = env
    Indexer(db, models, cfg).run()
    (media / "photos" / "IMG_ye01.jpg").unlink()
    Indexer(db, models, cfg).run()
    names = [r["filename"] for r in Searcher(db, models).search("yellow", {"kinds": ["image"]})["results"]]
    assert "IMG_ye01.jpg" not in names


def test_parse_query():
    assert parse_query("Customer testimonial videos") == ("Customer testimonial", "video")
    assert parse_query("Brochures related to residential projects") == ("residential projects", "pdf")
    assert parse_query("Images showing a modern living room") == ("a modern living room", "image")
    assert parse_query("Videos containing construction activity") == ("construction activity", "video")
    assert parse_query("A woman standing with a cat") == ("A woman standing with a cat", None)
