"""Command line entry point.

    python -m dam index  [--root PATH] [--fast]   # scan + index a folder (incremental)
    python -m dam serve                           # web UI on http://127.0.0.1:8000
    python -m dam search "woman with a cat" [--type image]
    python -m dam stats                           # dataset summary -> docs/DATASET.md
    python -m dam failures                        # list failed / unsupported files
    python -m dam eval-export                     # eval/RESULTS.md from saved judgments
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from .config import settings


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _setup(fast: bool = False):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if fast:
        settings.enable_captions = False
        settings.enable_transcription = False
    settings.ensure_dirs()
    from .app import make_models
    from .db import DB

    return DB(settings.db_path), make_models(settings)


def cmd_index(a):
    from .indexer import Indexer

    db, models = _setup(a.fast)
    idx = Indexer(db, models, settings)
    t0 = time.time()

    def progress(d):
        if d["phase"] == "processing":
            done, total = d["done"], d["total"]
            el = time.time() - t0
            eta = (el / done * (total - done)) if done else 0
            print(f"\r[{done + 1}/{total}] ETA {eta / 60:5.1f} min  {Path(d['current']).name[:60]:<60}", end="", flush=True)
        else:
            print(f"\rscanning... {d['total']} files  {Path(d['current']).name[:50]:<50}", end="", flush=True)

    try:
        res = idx.run(Path(a.root) if a.root else None, progress=progress)
    except KeyboardInterrupt:
        print("\nStopped. Progress is saved - run the same command again to resume.")
        return
    print()
    print(json.dumps(res, indent=2))


def cmd_serve(a):
    import uvicorn

    _setup()
    from .app import create_app

    print(f"\n  AssetLens running at  http://{settings.host}:{settings.port}\n  media folder: {settings.media_dir}\n")
    uvicorn.run(create_app(), host=settings.host, port=settings.port, log_level="warning")


def cmd_search(a):
    from .search import Searcher

    db, models = _setup()
    s = Searcher(db, models)
    res = s.search(a.query, {"kinds": [a.type] if a.type else []}, top_k=a.k)
    print(f"query='{res['query']}' embedded='{res.get('embedded_query')}' type={res.get('detected_type')} ({res['ms']} ms)")
    for i, r in enumerate(res["results"], 1):
        best = (r.get("match") or {}).get("best") or {}
        where = f"{best.get('source')}@{best.get('ref')}" if best else ""
        print(f"{i:2d}. {r['score']:6.2f} [{r['kind']:5}] {r['filename']:<45} {where:<18} {(r['caption'] or '')[:60]}")


def cmd_stats(a):
    db, _ = _setup()
    rows = db.q("""SELECT kind, COUNT(*) files, SUM(size) bytes, COUNT(DISTINCT hash) uniq FROM files
                   WHERE present=1 AND file_status='ok' GROUP BY kind ORDER BY kind""")
    other = db.q("SELECT file_status, ext, COUNT(*) n, SUM(size) b FROM files WHERE present=1 AND file_status!='ok' GROUP BY file_status, ext")
    status = db.q("""SELECT kind, status, COUNT(*) n, ROUND(AVG(process_ms)) ms FROM assets a
                     WHERE EXISTS (SELECT 1 FROM files f WHERE f.hash=a.hash AND f.present=1) GROUP BY kind, status""")
    vid = db.one("""SELECT COUNT(*) n, SUM(json_extract(meta,'$.duration')) d, SUM(json_extract(meta,'$.frames_sampled')) fr,
                    SUM(json_extract(meta,'$.has_speech')) sp FROM assets WHERE kind='video' AND status='done'""")
    pdf = db.one("SELECT SUM(json_extract(meta,'$.pages')) p FROM assets WHERE kind='pdf' AND status='done'")
    tot_files = sum(r["files"] for r in rows)
    tot_bytes = sum(r["bytes"] or 0 for r in rows)
    lines = ["# Dataset summary", "", f"_Generated {time.strftime('%Y-%m-%d %H:%M')} by `python -m dam stats`._", "",
             f"Media folder: `{settings.media_dir}`", "",
             "| Type | Files | Unique (after de-dup) | Total size |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['kind']} | {r['files']} | {r['uniq']} | {_fmt_bytes(r['bytes'] or 0)} |")
    lines.append(f"| **Total supported** | **{tot_files}** | | **{_fmt_bytes(tot_bytes)}** |")
    if other:
        lines += ["", "**Skipped files (by design):**", ""]
        for r in other:
            lines.append(f"- {r['n']} × `{r['ext'] or '(no ext)'}` — {r['file_status']}")
    lines += ["", "**Processing status:**", "", "| Type | Status | Count | Avg time / file |", "|---|---|---|---|"]
    for r in status:
        lines.append(f"| {r['kind']} | {r['status']} | {r['n']} | {(r['ms'] or 0) / 1000:.1f} s |")
    if vid and vid["n"]:
        lines += ["", f"Videos: {vid['n']} indexed, {(vid['d'] or 0) / 60:.0f} min total footage, "
                      f"{int(vid['fr'] or 0)} keyframes analysed, {int(vid['sp'] or 0)} with detected speech."]
    if pdf and pdf["p"]:
        lines.append(f"PDFs: {int(pdf['p'])} pages total.")
    md = "\n".join(lines) + "\n"
    out = Path(__file__).resolve().parents[1] / "docs" / "DATASET.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(md)
    print(f"written to {out}")


def cmd_failures(a):
    db, _ = _setup()
    for r in db.q("""SELECT a.kind, a.error, a.attempts, (SELECT path FROM files f WHERE f.hash=a.hash LIMIT 1) p
                     FROM assets a WHERE status='failed'"""):
        print(f"FAILED  [{r['kind']}] {r['p']}\n        {r['error'].splitlines()[0]}")
    for r in db.q("SELECT path, file_status, file_error FROM files WHERE present=1 AND file_status!='ok'"):
        print(f"SKIPPED [{r['file_status']}] {r['path']}: {r['file_error']}")


def cmd_eval_export(a):
    from .evaluation import Evaluator
    from .search import Searcher

    db, models = _setup()
    print(json.dumps(Evaluator(db, Searcher(db, models)).export(a.k), indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m dam", description="AssetLens - AI digital asset management")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("index", help="scan and index the media folder")
    s.add_argument("--root", help="folder to index (default MEDIA_DIR from .env)")
    s.add_argument("--fast", action="store_true", help="skip captioning + speech-to-text (much faster, lower quality)")
    s.set_defaults(fn=cmd_index)
    sub.add_parser("serve", help="start the web UI").set_defaults(fn=cmd_serve)
    s = sub.add_parser("search", help="search from the terminal")
    s.add_argument("query")
    s.add_argument("--type", choices=["image", "video", "pdf"])
    s.add_argument("-k", type=int, default=10)
    s.set_defaults(fn=cmd_search)
    sub.add_parser("stats", help="dataset summary").set_defaults(fn=cmd_stats)
    sub.add_parser("failures", help="list failed and skipped files").set_defaults(fn=cmd_failures)
    s = sub.add_parser("eval-export", help="write eval/RESULTS.md")
    s.add_argument("-k", type=int, default=5)
    s.set_defaults(fn=cmd_eval_export)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
