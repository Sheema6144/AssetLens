"""SQLite persistence layer.

One database file holds everything: file locations, per-content AI results,
embedding vectors, a full-text index and indexing-job history.

Key idea: *content* (identified by SHA-256 hash) is separated from *file
locations* (paths). Two identical files in different folders share one
`assets` row, so the AI work is done only once.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY,
    path        TEXT UNIQUE NOT NULL,
    folder      TEXT NOT NULL,
    filename    TEXT NOT NULL,
    ext         TEXT NOT NULL,
    kind        TEXT,               -- image | video | pdf | NULL (unsupported)
    size        INTEGER NOT NULL,
    mtime       REAL NOT NULL,
    hash        TEXT,               -- sha256 of content (NULL for unsupported)
    file_status TEXT NOT NULL,      -- ok | unsupported | too_large | unreadable
    file_error  TEXT,
    present     INTEGER NOT NULL DEFAULT 1,
    first_seen  REAL NOT NULL,
    last_seen   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash);
CREATE INDEX IF NOT EXISTS idx_files_kind ON files(kind);

CREATE TABLE IF NOT EXISTS assets (
    hash         TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,
    size         INTEGER NOT NULL,
    status       TEXT NOT NULL,     -- pending | processing | done | failed
    error        TEXT,
    attempts     INTEGER NOT NULL DEFAULT 0,
    model_sig    TEXT,
    caption      TEXT,
    tags         TEXT,              -- JSON list
    body         TEXT,              -- PDF text / video transcript (truncated)
    meta         TEXT,              -- JSON: width, height, duration, pages ...
    warnings     TEXT,              -- JSON list of non-fatal problems
    thumb        TEXT,
    processed_at REAL,
    process_ms   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);

CREATE TABLE IF NOT EXISTS vectors (
    id     INTEGER PRIMARY KEY,
    hash   TEXT NOT NULL,
    space  TEXT NOT NULL,           -- clip | text
    source TEXT NOT NULL,           -- image | frame | page | caption | transcript | pdf_text | ocr
    ref    REAL,                    -- timestamp (s) for frames, page number for pages/chunks
    label  TEXT,                    -- snippet / caption used to explain matches
    thumb  TEXT,                    -- thumbnail for this frame/page
    vec    BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vectors_hash ON vectors(hash);

CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts USING fts5(
    hash UNINDEXED, filenames, caption, tags, body,
    tokenize = 'porter unicode61'
);

CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY,
    started_at  REAL NOT NULL,
    finished_at REAL,
    state       TEXT NOT NULL,      -- running | finished | stopped | error
    phase       TEXT,
    root        TEXT,
    total       INTEGER DEFAULT 0,
    processed   INTEGER DEFAULT 0,
    skipped     INTEGER DEFAULT 0,
    failed      INTEGER DEFAULT 0,
    duplicates  INTEGER DEFAULT 0,
    unsupported INTEGER DEFAULT 0,
    current     TEXT,
    message     TEXT
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS judgments (
    query    TEXT NOT NULL,
    hash     TEXT NOT NULL,
    relevant INTEGER NOT NULL,
    PRIMARY KEY (query, hash)
);
"""


class DB:
    """Thread-safe-enough wrapper: one connection per thread, WAL mode."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.write_lock = threading.RLock()
        with self.write_lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
            self._local.conn = c
        return c

    # ---------- generic helpers ----------
    def q(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchall()

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def exec(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self.write_lock:
            cur = self.conn.execute(sql, tuple(params))
            self.conn.commit()
            return cur

    # ---------- meta / versioning ----------
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        r = self.one("SELECT value FROM meta WHERE key=?", (key,))
        return r["value"] if r else default

    def set_meta(self, key: str, value: str) -> None:
        self.exec("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def bump_vectors_version(self) -> None:
        self.set_meta("vectors_version", str(time.time_ns()))

    # ---------- asset results ----------
    def save_asset_result(self, hash_: str, result: dict, model_sig: str, process_ms: int) -> None:
        """Atomically replace all AI output for one asset."""
        with self.write_lock:
            c = self.conn
            try:
                c.execute("BEGIN")
                c.execute("DELETE FROM vectors WHERE hash=?", (hash_,))
                for v in result.get("vectors", []):
                    vec = np.asarray(v["vec"], dtype=np.float32)
                    c.execute(
                        "INSERT INTO vectors(hash,space,source,ref,label,thumb,vec) VALUES(?,?,?,?,?,?,?)",
                        (hash_, v["space"], v["source"], v.get("ref"), v.get("label"), v.get("thumb"), vec.tobytes()),
                    )
                c.execute(
                    """UPDATE assets SET status='done', error=NULL, model_sig=?, caption=?, tags=?, body=?,
                       meta=?, warnings=?, thumb=?, processed_at=?, process_ms=? WHERE hash=?""",
                    (
                        model_sig,
                        result.get("caption"),
                        json.dumps(result.get("tags", [])),
                        (result.get("body") or "")[:20000],
                        json.dumps(result.get("meta", {})),
                        json.dumps(result.get("warnings", [])),
                        result.get("thumb"),
                        time.time(),
                        process_ms,
                        hash_,
                    ),
                )
                self._refresh_fts(c, hash_)
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        self.bump_vectors_version()

    def refresh_fts(self, hash_: str) -> None:
        with self.write_lock:
            self._refresh_fts(self.conn, hash_)
            self.conn.commit()

    @staticmethod
    def _refresh_fts(c: sqlite3.Connection, hash_: str) -> None:
        a = c.execute("SELECT caption, tags, body FROM assets WHERE hash=?", (hash_,)).fetchone()
        if a is None:
            return
        names = c.execute("SELECT filename FROM files WHERE hash=? AND present=1", (hash_,)).fetchall()
        filenames = " ".join(n[0].rsplit(".", 1)[0].replace("_", " ").replace("-", " ") for n in names)
        tags = " ".join(json.loads(a["tags"] or "[]"))
        c.execute("DELETE FROM assets_fts WHERE hash=?", (hash_,))
        c.execute(
            "INSERT INTO assets_fts(hash, filenames, caption, tags, body) VALUES(?,?,?,?,?)",
            (hash_, filenames, a["caption"] or "", tags, a["body"] or ""),
        )

    def mark_failed(self, hash_: str, error: str) -> None:
        self.exec(
            "UPDATE assets SET status='failed', error=?, processed_at=? WHERE hash=?",
            (error[:2000], time.time(), hash_),
        )

    def load_vectors(self, space: str) -> tuple[np.ndarray, list[sqlite3.Row]]:
        rows = self.q(
            """SELECT v.id, v.hash, v.source, v.ref, v.label, v.thumb, v.vec FROM vectors v
               JOIN assets a ON a.hash=v.hash WHERE v.space=? AND a.status='done'""",
            (space,),
        )
        if not rows:
            return np.zeros((0, 0), dtype=np.float32), []
        mat = np.stack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
        return mat, rows

    # ---------- jobs ----------
    def new_job(self, root: str) -> int:
        cur = self.exec(
            "INSERT INTO jobs(started_at, state, phase, root) VALUES(?, 'running', 'scanning', ?)",
            (time.time(), root),
        )
        return int(cur.lastrowid)

    def update_job(self, job_id: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        self.exec(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id))

    def last_job(self) -> sqlite3.Row | None:
        return self.one("SELECT * FROM jobs ORDER BY id DESC LIMIT 1")
