from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable


def reciprocal_rank_fusion(
    rankings: Iterable[Iterable[str]], k: int = 60
) -> list[tuple[str, float]]:
    """Fuse independent rankings without mixing incompatible raw scores."""
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] += 1 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
