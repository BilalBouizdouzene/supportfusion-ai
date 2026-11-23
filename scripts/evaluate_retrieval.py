"""Evaluate retrieval against a manually reviewed JSONL annotation set.

Each line must contain ``query`` and either ``relevant_keys`` (preferred,
for example ``["github_issue:42", "documentation:7"]``) or
``relevant_ids`` for backwards compatibility. Labels are never inferred
from issue status, source order, or the retriever itself.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal, init_db  # noqa: E402
from backend.app.retrieval import RetrievalHit, retrieve  # noqa: E402


def _label_set(row: dict[str, object]) -> set[str]:
    values = row.get("relevant_keys", row.get("relevant_ids", []))
    if not isinstance(values, list):
        raise ValueError("relevant_keys/relevant_ids must be a JSON array")
    return {str(value) for value in values}


def _is_relevant(hit: RetrievalHit, labels: set[str]) -> bool:
    return hit.key in labels or str(hit.source_id) in labels


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def _metrics(
    rows: list[dict[str, object]], results: list[list[RetrievalHit]], limit: int
) -> dict[str, float | int]:
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    recalls: dict[int, list[float]] = {k: [] for k in (1, 5, 10)}
    precisions: dict[int, list[float]] = {k: [] for k in (1, 5, 10)}

    for row, hits in zip(rows, results, strict=True):
        labels = _label_set(row)
        ranked = [_is_relevant(hit, labels) for hit in hits[:limit]]
        first = next(
            (position for position, relevant in enumerate(ranked, 1) if relevant), None
        )
        reciprocal_ranks.append(1 / first if first else 0.0)
        for k in recalls:
            top_k = ranked[: min(k, limit)]
            recalls[k].append(float(any(top_k)))
            precisions[k].append(sum(top_k) / max(k, 1))
        gains = ranked[: min(5, limit)]
        dcg = sum(
            (1.0 if relevant else 0.0) / math.log2(position + 1)
            for position, relevant in enumerate(gains, 1)
        )
        ideal_count = min(len(labels), min(5, limit))
        ideal = sum(
            1.0 / math.log2(position + 1) for position in range(1, ideal_count + 1)
        )
        ndcgs.append(dcg / ideal if ideal else 0.0)

    def mean(values: list[float]) -> float:
        return sum(values) / max(len(values), 1)

    return {
        "samples": len(rows),
        "mrr": round(mean(reciprocal_ranks), 4),
        "ndcg_at_5": round(mean(ndcgs), 4),
        "recall_at_1": round(mean(recalls[1]), 4),
        "recall_at_5": round(mean(recalls[5]), 4),
        "recall_at_10": round(mean(recalls[10]), 4),
        "precision_at_1": round(mean(precisions[1]), 4),
        "precision_at_5": round(mean(precisions[5]), 4),
        "precision_at_10": round(mean(precisions[10]), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("labels", type=Path)
    parser.add_argument(
        "--mode",
        choices=("LIGHT", "STANDARD", "ADVANCED"),
        action="append",
        dest="modes",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Skip Cross-Encoder reranking in dense modes",
    )
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    if not args.labels.exists():
        parser.error(f"annotation file does not exist: {args.labels}")

    init_db()
    rows = [
        json.loads(line)
        for line in args.labels.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        parser.error("annotation file contains no JSONL rows")
    modes = args.modes or ["LIGHT", "STANDARD"]
    report: dict[str, object] = {
        "annotation_file": str(args.labels),
        "limit": args.limit,
        "modes": {},
    }
    with SessionLocal() as db:
        for mode in modes:
            results: list[list[RetrievalHit]] = []
            latencies: list[float] = []
            methods: set[str] = set()
            statuses: set[str] = set()
            for row in rows:
                query = str(row.get("query", "")).strip()
                if not query:
                    raise ValueError("each annotation row needs a non-empty query")
                started = time.perf_counter()
                result = retrieve(
                    db, query, limit=args.limit, mode=mode, rerank=not args.no_rerank
                )
                latencies.append((time.perf_counter() - started) * 1000)
                methods.add(result.method)
                statuses.add(result.model_status)
                results.append(result.hits)
            mode_report = _metrics(rows, results, args.limit)
            mode_report.update(
                {
                    "mean_latency_ms": round(sum(latencies) / len(latencies), 2),
                    "p95_latency_ms": round(_p95(latencies), 2),
                    "methods": sorted(methods),
                    "model_statuses": sorted(statuses),
                }
            )
            report["modes"][mode] = mode_report  # type: ignore[index]
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
