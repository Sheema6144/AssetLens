"""Scanning + indexing pipeline.

Phase 1 - scan   : walk the folder, record metadata for every file, compute a
                   SHA-256 content hash only for new/changed files.
Phase 2 - process: run the AI processors for every content hash that still
                   needs work, one at a time, committing after each file.

Reliability properties
  * Incremental      : unchanged (path, size, mtime) -> no re-hash, no re-processing.
  * De-duplication   : identical content in several folders is processed once.
  * Resumable        : every finished file is committed immediately; on start-up any
                       asset left in 'processing' (crash / power cut) goes back to 'pending'.
  * Failure isolation: one bad file is marked failed with its error and the job continues.
  * Retries          : transient failures are retried on the next run (MAX_ATTEMPTS);
                       corrupt files are not retried until the file changes.
  * Model failure    : if a core model cannot load, the job stops early with a clear
                       message and nothing is marked failed.
  * Model upgrades   : changing models changes the signature -> assets are re-processed.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
import traceback
from pathlib import Path
from typing import Callable

from .config import Settings, kind_for_ext
from .db import DB
from .models import ModelError
from .processors import PROCESSORS, ProcessingError

log = logging.getLogger("dam.indexer")

KIND_ORDER = {"image": 0, "pdf": 1, "video": 2}  # quick wins first: search is usable early


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def iter_files(root: Path, skip: set[Path]):
    """Iterative directory walk (no recursion limit), skipping hidden dirs and our data dir."""
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError as e:
            log.warning("cannot list %s: %s", d, e)
            continue
        subdirs: list[Path] = []
        for e in entries:
            if e.name.startswith(".") or e.name in ("__pycache__", "Thumbs.db", "desktop.ini"):
                continue
            p = Path(e.path)
            try:
                if e.is_dir(follow_symlinks=False):
                    if p.resolve() not in skip:
                        subdirs.append(p)
                elif e.is_file(follow_symlinks=False):
                    yield p, e.stat()
            except OSError as err:
                log.warning("cannot stat %s: %s", p, err)
        stack.extend(reversed(subdirs))  # visit folders in alphabetical order


class Indexer:
    def __init__(self, db: DB, models, cfg: Settings):
        self.db, self.models, self.cfg = db, models, cfg
        self.stop_event = threading.Event()
        self.job_id: int | None = None

    # ------------------------------------------------------------------ scan
    def scan(self, root: Path, job_id: int, progress: Callable[[dict], None] | None = None) -> dict:
        now = time.time()
        stats = {"seen": 0, "new": 0, "changed": 0, "unchanged": 0, "unsupported": 0, "duplicates": 0, "errors": 0}
        db = self.db
        seen_ids: list[int] = []
        for path, st in iter_files(root, {self.cfg.data_dir.resolve()}):
            if self.stop_event.is_set():
                break
            stats["seen"] += 1
            spath = str(path.resolve())
            ext = path.suffix.lower()
            kind = kind_for_ext(ext)
            row = db.one("SELECT id, size, mtime, hash, file_status FROM files WHERE path=?", (spath,))

            if row and row["size"] == st.st_size and abs(row["mtime"] - st.st_mtime) < 1e-3 and (row["hash"] or row["file_status"] != "ok"):
                stats["unchanged"] += 1
                if row["file_status"] == "unsupported":
                    stats["unsupported"] += 1
                db.exec("UPDATE files SET present=1, last_seen=? WHERE id=?", (now, row["id"]))
                seen_ids.append(row["id"])
                continue

            stats["changed" if row else "new"] += 1
            file_status, err, h = "ok", None, None
            if kind is None:
                file_status, err = "unsupported", f"unsupported file type '{ext or '(none)'}'"
                stats["unsupported"] += 1
            elif st.st_size == 0:
                file_status, err = "unreadable", "empty file (0 bytes)"
                stats["errors"] += 1
            elif st.st_size > self.cfg.max_file_mb * 1024 * 1024:
                file_status, err = "too_large", f"larger than MAX_FILE_MB={self.cfg.max_file_mb}"
                stats["errors"] += 1
            else:
                try:
                    h = sha256_file(path)
                except OSError as e:
                    file_status, err = "unreadable", f"cannot read file: {e}"
                    stats["errors"] += 1

            if progress and stats["seen"] % 25 == 0:
                progress({"phase": "scanning", "current": spath, "total": stats["seen"]})

            with db.write_lock:
                c = db.conn
                c.execute(
                    """INSERT INTO files(path, folder, filename, ext, kind, size, mtime, hash, file_status, file_error,
                                         present, first_seen, last_seen)
                       VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?)
                       ON CONFLICT(path) DO UPDATE SET size=excluded.size, mtime=excluded.mtime, kind=excluded.kind,
                         hash=excluded.hash, file_status=excluded.file_status, file_error=excluded.file_error,
                         present=1, last_seen=excluded.last_seen""",
                    (spath, str(path.parent.resolve()), path.name, ext, kind, st.st_size, st.st_mtime, h,
                     file_status, err, now, now),
                )
                fid = c.execute("SELECT id FROM files WHERE path=?", (spath,)).fetchone()[0]
                if h:
                    existed = c.execute("SELECT 1 FROM assets WHERE hash=?", (h,)).fetchone()
                    if existed:
                        stats["duplicates"] += 1  # same bytes already known from another path
                    else:
                        c.execute("INSERT INTO assets(hash, kind, size, status) VALUES(?,?,?, 'pending')", (h, kind, st.st_size))
                c.commit()
            seen_ids.append(fid)
            if h:
                db.refresh_fts(h)

        if not self.stop_event.is_set():
            # files that disappeared from disk are hidden from search (kept for history)
            root_s = str(root.resolve())
            with db.write_lock:
                c = db.conn
                c.execute("CREATE TEMP TABLE IF NOT EXISTS _seen(id INTEGER PRIMARY KEY)")
                c.execute("DELETE FROM _seen")
                c.executemany("INSERT OR IGNORE INTO _seen(id) VALUES(?)", [(i,) for i in seen_ids])
                cur = c.execute(
                    "UPDATE files SET present=0 WHERE present=1 AND (path LIKE ? OR path=?) AND id NOT IN (SELECT id FROM _seen)",
                    (root_s.rstrip("/\\") + os.sep + "%", root_s),
                )
                stats["missing"] = cur.rowcount
                c.commit()
            db.bump_vectors_version()
        return stats

    # ------------------------------------------------------------------ queue
    def pending_hashes(self) -> list[str]:
        sig = self.cfg.model_signature()
        rows = self.db.q(
            """SELECT a.hash, a.kind, a.size FROM assets a
               WHERE EXISTS (SELECT 1 FROM files f WHERE f.hash=a.hash AND f.present=1)
                 AND (a.status IN ('pending','processing')
                      OR (a.status='failed' AND a.attempts < ?)
                      OR (a.status='done' AND (a.model_sig IS NULL OR a.model_sig != ?)))""",
            (self.cfg.max_attempts, sig),
        )
        rows = sorted(rows, key=lambda r: (KIND_ORDER.get(r["kind"], 9), r["size"]))
        return [r["hash"] for r in rows]

    # ------------------------------------------------------------------ run
    def run(self, root: Path | None = None, progress: Callable[[dict], None] | None = None) -> dict:
        root = Path(root or self.cfg.media_dir).resolve()
        db = self.db
        self.stop_event.clear()
        if not root.is_dir():
            raise FileNotFoundError(f"media folder not found: {root}")

        # crash recovery: anything interrupted mid-way goes back to the queue
        db.exec("UPDATE assets SET status='pending' WHERE status='processing'")
        job = self.job_id = db.new_job(str(root))
        t0 = time.time()
        try:
            scan_stats = self.scan(root, job, progress=lambda d: db.update_job(job, phase=d["phase"], current=d["current"], total=d["total"]))
            queue = self.pending_hashes()
            db.update_job(job, phase="processing", total=len(queue), duplicates=scan_stats["duplicates"],
                          unsupported=scan_stats["unsupported"], skipped=scan_stats["unchanged"],
                          message=f"scanned {scan_stats['seen']} files: {scan_stats['new']} new, {scan_stats['changed']} changed, "
                                  f"{scan_stats['unchanged']} unchanged, {scan_stats['duplicates']} duplicates, "
                                  f"{scan_stats['unsupported']} unsupported")
            log.info("scan done: %s; %d assets to process", scan_stats, len(queue))

            if queue and not self.stop_event.is_set():
                try:
                    self.models.warmup()
                except ModelError as e:
                    db.update_job(job, state="error", finished_at=time.time(), message=str(e))
                    raise

            processed = failed = 0
            for i, h in enumerate(queue):
                if self.stop_event.is_set():
                    break
                f = db.one("SELECT path FROM files WHERE hash=? AND present=1 ORDER BY id LIMIT 1", (h,))
                if not f:
                    continue
                db.update_job(job, current=f["path"], processed=processed, failed=failed)
                if progress:
                    progress({"phase": "processing", "current": f["path"], "done": i, "total": len(queue)})
                ok = self.process_one(h, Path(f["path"]))
                if ok:
                    processed += 1
                else:
                    failed += 1
            state = "stopped" if self.stop_event.is_set() else "finished"
            db.update_job(job, state=state, phase="done", processed=processed, failed=failed, current=None,
                          finished_at=time.time())
            return {"job": job, "state": state, "scan": scan_stats, "processed": processed, "failed": failed,
                    "seconds": round(time.time() - t0, 1)}
        except ModelError:
            raise
        except Exception as e:  # noqa: BLE001
            db.update_job(job, state="error", finished_at=time.time(), message=f"{type(e).__name__}: {e}")
            raise

    def process_one(self, hash_: str, path: Path) -> bool:
        db = self.db
        a = db.one("SELECT kind FROM assets WHERE hash=?", (hash_,))
        db.exec("UPDATE assets SET status='processing', attempts=attempts+1 WHERE hash=?", (hash_,))
        t0 = time.time()
        try:
            result = PROCESSORS[a["kind"]](path, hash_, self.models, self.cfg)
            db.save_asset_result(hash_, result, self.cfg.model_signature(), int((time.time() - t0) * 1000))
            return True
        except ProcessingError as e:
            # bad input: retrying will not help until the file changes (new hash)
            db.mark_failed(hash_, str(e))
            db.exec("UPDATE assets SET attempts=? WHERE hash=?", (self.cfg.max_attempts, hash_))
            log.warning("FAILED %s: %s", path, e)
            return False
        except ModelError as e:
            db.mark_failed(hash_, f"model error: {e}")
            log.error("MODEL ERROR %s: %s", path, e)
            return False
        except MemoryError:
            db.mark_failed(hash_, "out of memory while processing")
            return False
        except Exception as e:  # noqa: BLE001 - unexpected: keep going, retry next run
            tb = traceback.format_exc(limit=3)
            db.mark_failed(hash_, f"{type(e).__name__}: {e}\n{tb}")
            log.exception("ERROR %s", path)
            return False

    def stop(self) -> None:
        self.stop_event.set()


class IndexManager:
    """Runs one indexing job at a time in a background thread (used by the web API)."""

    def __init__(self, indexer: Indexer):
        self.indexer = indexer
        self.thread: threading.Thread | None = None
        self.last_result: dict | None = None
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start(self, root: Path | None = None) -> bool:
        if self.running:
            return False
        self.last_error = None

        def _run():
            try:
                self.last_result = self.indexer.run(root)
            except Exception as e:  # noqa: BLE001
                self.last_error = f"{type(e).__name__}: {e}"
                log.exception("index job failed")

        self.thread = threading.Thread(target=_run, name="indexer", daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        self.indexer.stop()
