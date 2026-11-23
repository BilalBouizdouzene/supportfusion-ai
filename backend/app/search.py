from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Incident


TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]{2,}")
ERROR_RE = re.compile(
    r"\b(?:ERR[_-]?[A-Z0-9_-]+|[A-Z][A-Z0-9_]{2,}_ERROR|HTTP\s*[45]\d\d|[45]\d\d)\b"
)


@dataclass
class RankedIncident:
    incident: Incident
    score: float
    excerpt: str
    verification: str


def tokenize(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value or "")]


def incident_text(incident: Incident) -> str:
    parts = [
        incident.title,
        incident.description or "",
        incident.affected_component or "",
        incident.affected_version or "",
    ]
    parts.extend(incident.error_codes or [])
    parts.extend(incident.logs or [])
    return " ".join(parts)


def _excerpt(text: str, query_tokens: list[str], width: int = 280) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return "No text available."
    lower = cleaned.lower()
    offsets = [lower.find(token) for token in query_tokens if lower.find(token) >= 0]
    start = max(0, (min(offsets) if offsets else 0) - 70)
    excerpt = cleaned[start : start + width]
    return (
        ("…" if start else "") + excerpt + ("…" if start + width < len(cleaned) else "")
    )


def rank_incidents(
    db: Session, query: str, limit: int = 10
) -> tuple[list[RankedIncident], float]:
    started = time.perf_counter()
    query_tokens = tokenize(query)
    if not query_tokens:
        return [], (time.perf_counter() - started) * 1000

    incidents = list(
        db.scalars(select(Incident).order_by(Incident.updated_at.desc())).all()
    )
    document_tokens = [tokenize(incident_text(item)) for item in incidents]
    document_frequency = Counter(
        token for tokens in document_tokens for token in set(tokens)
    )
    avg_len = sum(len(tokens) for tokens in document_tokens) / max(
        len(document_tokens), 1
    )
    query_errors = {match.lower() for match in ERROR_RE.findall(query)}
    ranked: list[RankedIncident] = []

    for incident, tokens in zip(incidents, document_tokens, strict=False):
        if not tokens:
            continue
        counts = Counter(tokens)
        score = 0.0
        for term in query_tokens:
            tf = counts[term]
            if not tf:
                continue
            idf = 1 + (len(incidents) / (1 + document_frequency[term]))
            score += idf * (
                (tf * 2.2) / (tf + 1.2 * (0.35 + 0.65 * len(tokens) / max(avg_len, 1)))
            )
            if term in tokenize(incident.title):
                score += 2.0
        incident_errors = {code.lower() for code in (incident.error_codes or [])}
        exact_errors = query_errors.intersection(incident_errors)
        if exact_errors:
            score += 6.0 * len(exact_errors)
        if incident.status.lower() in {"closed", "resolved"}:
            score += 0.15
        if score > 0:
            verification = (
                "observed source match" if exact_errors else "lexical similarity"
            )
            ranked.append(
                RankedIncident(
                    incident,
                    score,
                    _excerpt(incident_text(incident), query_tokens),
                    verification,
                )
            )

    ranked.sort(key=lambda item: (-item.score, item.incident.id))
    return ranked[:limit], (time.perf_counter() - started) * 1000
