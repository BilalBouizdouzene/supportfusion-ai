from __future__ import annotations

import math


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return float(bool(set(ranked[:k]).intersection(relevant)))


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return len(set(ranked[:k]).intersection(relevant)) / max(k, 1)


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for rank, item_id in enumerate(ranked, start=1):
        if item_id in relevant:
            return 1 / rank
    return 0.0


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    gains = [1 if item_id in relevant else 0 for item_id in ranked[:k]]
    dcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))
    ideal = sum(1 / math.log2(index + 2) for index in range(min(len(relevant), k)))
    return dcg / ideal if ideal else 0.0
