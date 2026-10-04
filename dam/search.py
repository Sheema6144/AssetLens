"""Hybrid semantic search.

Signals per asset (an asset = one unique content hash):
  1. visual  : CLIP(query text) vs CLIP(image / video keyframes / PDF page renders)  -> max over the asset
  2. semantic: MiniLM(query)   vs MiniLM(captions, transcripts, PDF text chunks)     -> max over the asset
  3. keyword : SQLite FTS5 BM25 over captions, tags, PDF text, transcripts (+ filenames, low weight)

The raw similarities live on different scales (CLIP ~0.15-0.35, MiniLM ~0.1-0.8),
so each signal is standardised per query (z-score across the whole collection)
before a weighted sum. Weights depend on the file type: pixels matter most for
images/videos, text matters most for PDFs. If the query names a type
("videos of ...", "brochures about ...") that type gets a soft boost, and the
type words are removed before embedding.

Everything is brute-force numpy matrix multiplication: for <= ~200k vectors this
is a few milliseconds and needs no extra service. (See README: swap for FAISS /
Qdrant / pgvector beyond that.)
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
from dataclasses import dataclass

import numpy as np

from .db import DB

WEIGHTS = {  # (visual, semantic)
    "image": (0.60, 0.40),
    "video": (0.55, 0.45),
    "pdf": (0.25, 0.75),
}
KEYWORD_WEIGHT = 0.35
INTENT_BOOST = 1.5      # asset type named in the query ("videos of ...")
INTENT_PENALTY = 0.5    # other types are pushed down a little (soft filter, not a hard one)

INTENT_WORDS = {
    "video": r"\b(videos?|clips?|footage|films?|recordings?|movies?)\b",
    "image": r"\b(images?|photos?|photographs?|pictures?|pics?|stills?)\b",
    "pdf": r"\b(pdfs?|brochures?|documents?|docs?|leaflets?|flyers?|catalogu?es?|reports?|booklets?)\b",
}
FILLER = r"\b(show me|find|search for|look for|i want|give me|showing|containing|that contain|with|of|related to|about|any|all|some)\b"
STOP = {"a", "an", "the", "of", "with", "and", "or", "in", "on", "to", "for", "showing", "containing", "related",
        "about", "show", "me", "find", "some", "any", "all", "is", "are", "that", "this", "at", "by", "from"}


def parse_query(q: str) -> tuple[str, str | None]:
    """Return (cleaned query for embedding, detected type or None)."""
    detected = None
    for kind, pat in INTENT_WORDS.items():
        if re.search(pat, q, flags=re.I):
            detected = kind
            break
    clean = q
    if detected:
        clean = re.sub(INTENT_WORDS[detected], " ", clean, flags=re.I)
        clean = re.sub(r"^\s*(" + FILLER + r"\s*)+", " ", clean, flags=re.I)
    clean = re.sub(r"\s+", " ", clean).strip(" ,.-")
    return (clean or q.strip()), detected


def fts_query(q: str) -> str | None:
    toks = [t for t in re.findall(r"[a-zA-Z0-9]+", q.lower()) if t not in STOP and len(t) > 1]
    if not toks:
        return None
    return " OR ".join(f'"{t}"' for t in toks[:12])


@dataclass
class _Space:
    mat: np.ndarray
    rows: list
    hashes: np.ndarray        # unique asset hashes (sorted)
    starts: np.ndarray        # group start index per asset in mat
    order: np.ndarray         # permutation that groups rows by hash
    summary_idx: np.ndarray   # per asset: row index of its document-summary vector, or -1


class VectorIndex:
    """In-memory copy of the vectors table; reloaded when the DB version changes."""

    def __init__(self, db: DB):
        self.db = db
        self._lock = threading.Lock()
        self._version = None
        self.spaces: dict[str, _Space | None] = {}

    def ensure_fresh(self) -> None:
        v = self.db.get_meta("vectors_version", "0")
        if v == self._version:
            return
        with self._lock:
            if v == self._version:
                return
            for space in ("clip", "text"):
                mat, rows = self.db.load_vectors(space)
                if not rows:
                    self.spaces[space] = None
                    continue
                hs = np.array([r["hash"] for r in rows])
                order = np.argsort(hs, kind="stable")
                hs_sorted = hs[order]
                uniq, starts = np.unique(hs_sorted, return_index=True)
                rows_sorted = [rows[i] for i in order]
                summary_idx = np.full(len(uniq), -1, dtype=np.int64)
                pos = {h: k for k, h in enumerate(uniq)}
                for j, r in enumerate(rows_sorted):
                    if r["source"] == "pdf_summary":
                        summary_idx[pos[r["hash"]]] = j
                self.spaces[space] = _Space(mat[order], rows_sorted, uniq, starts, order, summary_idx)
            self._version = v

    def best_per_asset(self, space: str, qvec: np.ndarray) -> dict[str, tuple[float, object]]:
        s = self.spaces.get(space)
        if s is None or qvec is None or s.mat.shape[1] != qvec.shape[0]:
            return {}
        sims = s.mat @ qvec
        best = np.maximum.reduceat(sims, s.starts)
        # argmax inside each group
        out = {}
        ends = np.append(s.starts[1:], len(sims))
        for h, st, en, b, si in zip(s.hashes, s.starts, ends, best, s.summary_idx):
            j = st + int(np.argmax(sims[st:en]))
            score = float(b)
            if si >= 0:
                # Long PDFs have hundreds of chunks, so "best chunk" alone favours long
                # documents that mention the words once. Blend with the whole-document
                # summary so the document must be *about* the topic.
                score = 0.5 * score + 0.5 * float(sims[si])
            out[str(h)] = (score, s.rows[j])
        return out


def _zscores(d: dict[str, float]) -> dict[str, float]:
    if not d:
        return {}
    vals = np.array(list(d.values()), dtype=np.float64)
    mu, sd = vals.mean(), vals.std()
    sd = sd if sd > 1e-6 else 1.0
    return {k: (v - mu) / sd for k, v in d.items()}


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


class Searcher:
    def __init__(self, db: DB, models):
        self.db = db
        self.models = models
        self.index = VectorIndex(db)

    # -------------------------------------------------------------- filters
    def _allowed(self, f: dict) -> dict[str, dict]:
        """Return {hash: info} for assets passing metadata filters (present files only)."""
        where = ["a.status='done'", "f.present=1"]
        params: list = []
        if f.get("kinds"):
            where.append(f"a.kind IN ({','.join('?' * len(f['kinds']))})")
            params += list(f["kinds"])
        if f.get("min_mb") not in (None, ""):
            where.append("f.size >= ?")
            params.append(float(f["min_mb"]) * 1024 * 1024)
        if f.get("max_mb") not in (None, ""):
            where.append("f.size <= ?")
            params.append(float(f["max_mb"]) * 1024 * 1024)
        if f.get("folder"):
            where.append("f.folder LIKE ?")
            params.append(f"%{f['folder']}%")
        if f.get("ext"):
            where.append("f.ext = ?")
            params.append("." + f["ext"].lower().lstrip("."))
        if f.get("modified_after"):
            where.append("f.mtime >= ?")
            params.append(float(f["modified_after"]))
        rows = self.db.q(
            f"""SELECT a.hash, a.kind, a.caption, a.tags, a.meta, a.thumb, a.warnings,
                       f.id AS file_id, f.path, f.filename, f.folder, f.ext, f.size, f.mtime
                FROM assets a JOIN files f ON f.hash=a.hash
                WHERE {' AND '.join(where)} ORDER BY f.folder, f.filename""",
            params,
        )
        out: dict[str, dict] = {}
        for r in rows:
            meta = json.loads(r["meta"] or "{}")
            if f.get("orientation") and r["kind"] in ("image", "video"):
                w, h = meta.get("width") or 0, meta.get("height") or 0
                o = "landscape" if w > h else "portrait" if h > w else "square"
                if o != f["orientation"]:
                    continue
            if f.get("max_duration") not in (None, "") and r["kind"] == "video":
                if (meta.get("duration") or 0) > float(f["max_duration"]):
                    continue
            if f.get("has_speech") and r["kind"] == "video" and not meta.get("has_speech"):
                continue
            item = out.get(r["hash"])
            if item is None:
                out[r["hash"]] = {
                    "hash": r["hash"], "kind": r["kind"], "caption": r["caption"],
                    "tags": json.loads(r["tags"] or "[]"), "meta": meta, "thumb": r["thumb"],
                    "warnings": json.loads(r["warnings"] or "[]"),
                    "file_id": r["file_id"], "path": r["path"], "filename": r["filename"], "folder": r["folder"],
                    "ext": r["ext"], "size": r["size"], "mtime": r["mtime"], "duplicates": [],
                }
            else:  # same content in another folder
                item["duplicates"].append({"file_id": r["file_id"], "path": r["path"]})
        return out

    # -------------------------------------------------------------- search
    def search(self, query: str, filters: dict | None = None, top_k: int = 24) -> dict:
        t0 = time.time()
        filters = dict(filters or {})
        allowed = self._allowed(filters)
        query = (query or "").strip()
        if not query:  # browse mode
            items = sorted(allowed.values(), key=lambda x: -x["mtime"])[:top_k]
            return {"query": "", "results": items, "total_candidates": len(allowed), "ms": int((time.time() - t0) * 1000)}

        clean, intent = parse_query(query)
        if filters.get("kinds"):
            intent = None  # explicit filter wins over guessed intent
        self.index.ensure_fresh()
        warnings = []

        visual: dict = {}
        try:
            qc = self.models.clip_text([clean])[0]
            visual = self.index.best_per_asset("clip", qc)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"visual search unavailable: {e}")
        semantic: dict = {}
        try:
            qt = self.models.text_embed([clean])[0]
            semantic = self.index.best_per_asset("text", qt)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"text search unavailable: {e}")

        keyword: dict[str, float] = {}
        fq = fts_query(clean)
        if fq:
            try:
                rows = self.db.q(
                    "SELECT hash, bm25(assets_fts, 0.0, 0.3, 1.0, 0.8, 0.6) AS s FROM assets_fts WHERE assets_fts MATCH ?",
                    (fq,),
                )
                if rows:
                    best = min(r["s"] for r in rows)  # bm25: more negative = better
                    keyword = {r["hash"]: (r["s"] / best if best < 0 else 0.0) for r in rows}
            except Exception as e:  # noqa: BLE001
                warnings.append(f"keyword search error: {e}")

        zv = _zscores({h: v[0] for h, v in visual.items()})
        zs = _zscores({h: v[0] for h, v in semantic.items()})

        results = []
        for h, item in allowed.items():
            wv, ws = WEIGHTS.get(item["kind"], (0.5, 0.5))
            has_v, has_s = h in zv, h in zs
            if not has_v and not has_s and h not in keyword:
                continue
            if has_v and not has_s:
                wv, ws = 1.0, 0.0
            elif has_s and not has_v:
                wv, ws = 0.0, 1.0
            score = wv * zv.get(h, 0.0) + ws * zs.get(h, 0.0) + KEYWORD_WEIGHT * keyword.get(h, 0.0)
            if intent:
                score += INTENT_BOOST if item["kind"] == intent else -INTENT_PENALTY
            match = self._explain(visual.get(h), semantic.get(h), item["kind"])
            r = dict(item)
            r.update({
                "score": round(score, 3),
                "relevance": round(100 * _sigmoid(1.6 * (score - 1.2)), 1),
                "signals": {
                    "visual": round(visual[h][0], 3) if h in visual else None,
                    "semantic": round(semantic[h][0], 3) if h in semantic else None,
                    "keyword": round(keyword.get(h, 0.0), 3),
                },
                "match": match,
            })
            results.append(r)

        results.sort(key=lambda r: -r["score"])
        for r in results:
            r["confidence"] = "high" if r["score"] >= 2.0 else "medium" if r["score"] >= 1.0 else "low"
        return {
            "query": query, "embedded_query": clean, "detected_type": intent,
            "results": results[:top_k], "total_candidates": len(results),
            "warnings": warnings, "ms": int((time.time() - t0) * 1000),
        }

    @staticmethod
    def _explain(vis, sem, kind: str) -> dict:
        """Tell the user *where* inside the asset the match is (frame time, page, snippet)."""
        m: dict = {}
        if vis:
            row = vis[1]
            m["visual"] = {"source": row["source"], "ref": row["ref"], "thumb": row["thumb"], "label": row["label"]}
        if sem:
            row = sem[1]
            m["text"] = {"source": row["source"], "ref": row["ref"], "thumb": row["thumb"], "label": row["label"]}
        # pick the stronger one as the headline "match point"
        best = m.get("visual")
        if sem and (not vis or kind == "pdf" or (sem[1]["source"] == "transcript" and sem[0] > 0.45)):
            best = m.get("text")
        m["best"] = best
        return m
