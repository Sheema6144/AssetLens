"""Search-quality evaluation.

Test queries live in eval/queries.json. The UI's "Evaluate" tab runs every query,
shows the top results, and lets a human mark each result relevant / not relevant.
Judgments are stored in SQLite (table `judgments`) so they survive re-indexing
and re-tuning. Metrics:

  * P@k   – share of the top-k results judged relevant
  * MRR   – 1 / rank of the first relevant result (how soon the user finds one)
  * Hit@k – did at least one relevant result appear in the top-k
  * Recall@10 (approx.) – relevant assets known for the query (judged in any run)
                          that appear in the current top-10

`export()` writes eval/RESULTS.md + eval/results.json for the submission.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .db import DB

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"


class Evaluator:
    def __init__(self, db: DB, searcher, eval_dir: Path = EVAL_DIR):
        self.db, self.searcher, self.dir = db, searcher, eval_dir

    def queries(self) -> list[dict]:
        p = self.dir / "queries.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

    def judge(self, query: str, hash_: str, relevant) -> None:
        if relevant is None:
            self.db.exec("DELETE FROM judgments WHERE query=? AND hash=?", (query, hash_))
        else:
            self.db.exec(
                "INSERT INTO judgments(query,hash,relevant) VALUES(?,?,?) ON CONFLICT(query,hash) DO UPDATE SET relevant=excluded.relevant",
                (query, hash_, 1 if relevant else 0),
            )

    def save_note(self, query: str, note: str) -> None:
        self.db.set_meta(f"evalnote:{query}", note)

    def run(self, k: int = 5) -> dict:
        out, agg = [], {"p": [], "mrr": [], "hit": [], "recall": []}
        for q in self.queries():
            res = self.searcher.search(q["query"], q.get("filters") or {}, top_k=10)
            judg = {r["hash"]: r["relevant"] for r in self.db.q("SELECT hash, relevant FROM judgments WHERE query=?", (q["query"],))}
            rows = []
            for i, r in enumerate(res["results"]):
                rows.append({
                    "rank": i + 1, "hash": r["hash"], "kind": r["kind"], "filename": r["filename"], "path": r["path"],
                    "file_id": r["file_id"], "thumb": (r.get("match", {}).get("best") or {}).get("thumb") or r["thumb"],
                    "caption": r["caption"], "score": r["score"], "confidence": r.get("confidence"),
                    "match": r.get("match", {}).get("best"), "relevant": judg.get(r["hash"]),
                })
            topk = rows[:k]
            judged = [x for x in topk if x["relevant"] is not None]
            metrics = None
            if len(judged) == len(topk) and topk:
                rel = [x["relevant"] == 1 for x in topk]
                first = next((i for i, x in enumerate(rows) if x["relevant"] == 1), None)
                known_rel = {h for h, v in judg.items() if v == 1}
                found = {x["hash"] for x in rows[:10] if x["hash"] in known_rel}
                metrics = {
                    "p_at_k": round(sum(rel) / len(topk), 2),
                    "mrr": round(1 / (first + 1), 2) if first is not None else 0.0,
                    "hit": 1 if any(rel) else 0,
                    "recall_at_10": round(len(found) / len(known_rel), 2) if known_rel else None,
                }
                agg["p"].append(metrics["p_at_k"])
                agg["mrr"].append(metrics["mrr"])
                agg["hit"].append(metrics["hit"])
                if metrics["recall_at_10"] is not None:
                    agg["recall"].append(metrics["recall_at_10"])
            out.append({**q, "detected_type": res.get("detected_type"), "embedded_query": res.get("embedded_query"),
                        "ms": res.get("ms"), "results": rows, "metrics": metrics,
                        "note": self.db.get_meta(f"evalnote:{q['query']}", "") or ""})
        mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else None  # noqa: E731
        summary = {"k": k, "queries": len(out), "fully_judged": len(agg["p"]), f"mean_p_at_{k}": mean(agg["p"]),
                   "mean_mrr": mean(agg["mrr"]), f"hit_rate_at_{k}": mean(agg["hit"]), "mean_recall_at_10": mean(agg["recall"])}
        return {"summary": summary, "queries": out}

    def export(self, k: int = 5) -> dict:
        data = self.run(k)
        self.dir.mkdir(exist_ok=True)
        (self.dir / "results.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        s = data["summary"]
        lines = [
            "# Search evaluation results", "",
            f"_Generated {time.strftime('%Y-%m-%d %H:%M')} from the Evaluate tab. Relevance judged manually by looking at each result._", "",
            "| Metric | Value |", "|---|---|",
            f"| Queries | {s['queries']} (fully judged: {s['fully_judged']}) |",
            f"| Mean Precision@{k} | {s[f'mean_p_at_{k}']} |",
            f"| Mean Reciprocal Rank | {s['mean_mrr']} |",
            f"| Hit rate@{k} (≥1 relevant in top {k}) | {s[f'hit_rate_at_{k}']} |",
            f"| Mean Recall@10 (vs. all assets judged relevant) | {s['mean_recall_at_10']} |",
            "", "## Per query", "",
            f"| # | Query | Detected type | P@{k} | MRR | Latency |", "|---|---|---|---|---|---|",
        ]
        for i, q in enumerate(data["queries"], 1):
            m = q["metrics"] or {}
            lines.append(f"| {i} | {q['query']} | {q.get('detected_type') or '-'} | {m.get('p_at_k', 'n/j')} | {m.get('mrr', 'n/j')} | {q['ms']} ms |")
        for i, q in enumerate(data["queries"], 1):
            lines += ["", f"### {i}. “{q['query']}”", "",
                      f"- **User is trying to find:** {q.get('intent', '')}",
                      f"- **Expected assets:** {q.get('expected', '')}"]
            if q["metrics"]:
                lines.append(f"- **Result:** P@{k} = {q['metrics']['p_at_k']}, MRR = {q['metrics']['mrr']}")
            lines += ["", f"| Rank | File | Type | Score | Why it matched | Relevant? |", "|---|---|---|---|---|---|"]
            for r in q["results"][:k]:
                why = ""
                if r["match"]:
                    src, ref = r["match"].get("source"), r["match"].get("ref")
                    loc = f" @ {ref:.0f}s" if src == "frame" and ref is not None else f" p.{ref:.0f}" if src in ("page", "pdf_text") and ref else ""
                    why = f"{src}{loc}: {(r['match'].get('label') or '')[:80]}".replace("|", "/")
                mark = {1: "✅", 0: "❌", None: "–"}[r["relevant"]]
                lines.append(f"| {r['rank']} | `{r['filename']}` | {r['kind']} | {r['score']} | {why} | {mark} |")
            lines += ["", f"**Observations:** {q['note'] or '_(none)_'}"]
        md = "\n".join(lines) + "\n"
        (self.dir / "RESULTS.md").write_text(md, encoding="utf-8")
        return {"written": [str(self.dir / "RESULTS.md"), str(self.dir / "results.json")], "summary": s}
