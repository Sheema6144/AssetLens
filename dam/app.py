"""FastAPI backend + static web UI."""
from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import time
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, settings as default_settings
from .db import DB
from .evaluation import Evaluator
from .indexer import IndexManager, Indexer
from .search import Searcher

log = logging.getLogger("dam.app")
STATIC = Path(__file__).parent / "static"


def make_models(cfg: Settings):
    if os.getenv("DAM_FAKE_MODELS") == "1":
        from .models import FakeModels

        return FakeModels(cfg)
    from .models import Models

    return Models(cfg)


def create_app(cfg: Settings | None = None, models=None) -> FastAPI:
    cfg = cfg or default_settings
    cfg.ensure_dirs()
    db = DB(cfg.db_path)
    models = models or make_models(cfg)
    indexer = Indexer(db, models, cfg)
    manager = IndexManager(indexer)
    searcher = Searcher(db, models)
    evaluator = Evaluator(db, searcher)

    app = FastAPI(title="AssetLens – AI Digital Asset Management", version="1.0")
    app.state.db, app.state.manager, app.state.searcher, app.state.cfg = db, manager, searcher, cfg
    app.mount("/thumbs", StaticFiles(directory=cfg.thumbs_dir), name="thumbs")
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    # ------------------------------------------------------------------ search
    @app.get("/api/search")
    def search(
        q: str = "",
        kinds: str = "",
        min_mb: float | None = None,
        max_mb: float | None = None,
        folder: str = "",
        ext: str = "",
        orientation: str = "",
        max_duration: float | None = None,
        has_speech: bool = False,
        modified_after: float | None = None,
        top_k: int = Query(cfg.default_top_k, ge=1, le=200),
    ):
        filters = {
            "kinds": [k for k in kinds.split(",") if k], "min_mb": min_mb, "max_mb": max_mb, "folder": folder,
            "ext": ext, "orientation": orientation, "max_duration": max_duration, "has_speech": has_speech,
            "modified_after": modified_after,
        }
        return searcher.search(q, filters, top_k)

    @app.get("/api/assets/{hash_}")
    def asset(hash_: str):
        a = db.one("SELECT * FROM assets WHERE hash=?", (hash_,))
        if not a:
            raise HTTPException(404, "asset not found")
        files = [dict(r) for r in db.q("SELECT id, path, folder, filename, size, mtime, present FROM files WHERE hash=?", (hash_,))]
        parts = [dict(r) for r in db.q(
            "SELECT source, ref, label, thumb FROM vectors WHERE hash=? AND space='clip' ORDER BY ref", (hash_,))]
        out = dict(a)
        for k in ("tags", "meta", "warnings"):
            out[k] = json.loads(out[k] or ("[]" if k != "meta" else "{}"))
        out["body"] = (out["body"] or "")[:4000]
        out["files"], out["parts"] = files, parts
        return out

    @app.get("/api/file/{file_id}")
    def file(file_id: int):
        r = db.one("SELECT path FROM files WHERE id=?", (file_id,))
        if not r or not Path(r["path"]).is_file():
            raise HTTPException(404, "file not found on disk")
        return FileResponse(r["path"], content_disposition_type="inline")

    @app.post("/api/open/{file_id}")
    def open_location(file_id: int):
        """Open the OS file explorer with the file selected (local app only)."""
        r = db.one("SELECT path FROM files WHERE id=?", (file_id,))
        if not r:
            raise HTTPException(404, "file not found")
        p = r["path"]
        try:
            system = platform.system()
            if system == "Windows":
                subprocess.Popen(f'explorer /select,"{os.path.normpath(p)}"')
            elif system == "Darwin":
                subprocess.Popen(["open", "-R", p])
            else:
                subprocess.Popen(["xdg-open", str(Path(p).parent)])
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"ok": False, "path": p, "error": str(e)}, status_code=500)
        return {"ok": True, "path": p}

    # ------------------------------------------------------------------ indexing
    @app.post("/api/index/start")
    def index_start(body: dict = Body(default={})):
        root = Path(body.get("root") or cfg.media_dir)
        if not root.is_dir():
            raise HTTPException(400, f"folder not found: {root}")
        started = manager.start(root)
        return {"started": started, "running": manager.running, "root": str(root.resolve())}

    @app.post("/api/index/stop")
    def index_stop():
        manager.stop()
        return {"stopping": True}

    @app.get("/api/index/status")
    def index_status():
        job = db.last_job()
        counts = {r["status"]: r["n"] for r in db.q(
            """SELECT status, COUNT(*) n FROM assets a
               WHERE EXISTS (SELECT 1 FROM files f WHERE f.hash=a.hash AND f.present=1) GROUP BY status""")}
        return {
            "running": manager.running,
            "job": dict(job) if job else None,
            "error": manager.last_error,
            "asset_status": counts,
            "media_dir": str(cfg.media_dir),
            "now": time.time(),
        }

    @app.get("/api/failures")
    def failures():
        failed = [dict(r) for r in db.q(
            """SELECT a.hash, a.kind, a.error, a.attempts, a.processed_at,
                      (SELECT path FROM files f WHERE f.hash=a.hash AND f.present=1 LIMIT 1) AS path
               FROM assets a WHERE a.status='failed' ORDER BY a.processed_at DESC""")]
        skipped = [dict(r) for r in db.q(
            "SELECT id, path, ext, size, file_status, file_error FROM files WHERE present=1 AND file_status!='ok' ORDER BY path")]
        warned = [dict(r) for r in db.q(
            """SELECT a.hash, a.kind, a.warnings, (SELECT path FROM files f WHERE f.hash=a.hash LIMIT 1) AS path
               FROM assets a WHERE a.status='done' AND a.warnings IS NOT NULL AND a.warnings != '[]'""")]
        for w in warned:
            w["warnings"] = json.loads(w["warnings"])
        return {"failed": [f for f in failed if f["path"]], "skipped": skipped, "warnings": warned}

    @app.post("/api/retry-failed")
    def retry_failed():
        cur = db.exec("UPDATE assets SET attempts=0, status='pending' WHERE status='failed'")
        return {"reset": cur.rowcount}

    @app.get("/api/stats")
    def stats():
        by_kind = [dict(r) for r in db.q(
            """SELECT kind, COUNT(*) files, SUM(size) bytes, COUNT(DISTINCT hash) unique_assets
               FROM files WHERE present=1 AND file_status='ok' GROUP BY kind""")]
        dup_files = db.one(
            """SELECT COALESCE(SUM(c-1),0) n FROM (SELECT COUNT(*) c FROM files
               WHERE present=1 AND hash IS NOT NULL GROUP BY hash HAVING c>1)""")["n"]
        other = [dict(r) for r in db.q(
            "SELECT file_status, COUNT(*) n, SUM(size) bytes FROM files WHERE present=1 AND file_status!='ok' GROUP BY file_status")]
        vec = [dict(r) for r in db.q("SELECT space, source, COUNT(*) n FROM vectors GROUP BY space, source")]
        timing = [dict(r) for r in db.q(
            "SELECT kind, COUNT(*) n, AVG(process_ms) avg_ms, SUM(process_ms) total_ms FROM assets WHERE status='done' GROUP BY kind")]
        return {"by_kind": by_kind, "duplicate_files": dup_files, "other": other, "vectors": vec, "timing": timing}

    @app.get("/api/folders")
    def folders():
        return [r["folder"] for r in db.q("SELECT DISTINCT folder FROM files WHERE present=1 ORDER BY folder")]

    # ------------------------------------------------------------------ evaluation
    @app.get("/api/eval")
    def eval_run(k: int = 5):
        return evaluator.run(k)

    @app.post("/api/eval/judge")
    def eval_judge(body: dict = Body(...)):
        evaluator.judge(body["query"], body["hash"], body.get("relevant"))
        return {"ok": True}

    @app.post("/api/eval/notes")
    def eval_notes(body: dict = Body(...)):
        evaluator.save_note(body["query"], body.get("note", ""))
        return {"ok": True}

    @app.post("/api/eval/export")
    def eval_export(k: int = 5):
        return evaluator.export(k)

    return app
