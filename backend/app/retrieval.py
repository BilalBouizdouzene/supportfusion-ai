from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .dense import dense_service
from .models import DocumentChunk, Incident
from .search import ERROR_RE, tokenize
from ml.retrieval.rrf import reciprocal_rank_fusion


@dataclass
class CorpusRecord:
    key: str
    source_type: str
    source_id: int
    title: str
    content: str
    source_url: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class RetrievalHit:
    key: str
    source_type: str
    source_id: int
    title: str
    excerpt: str
    source_url: str
    score: float
    verification: str
    metadata: dict[str, object]


@dataclass
class RetrievalResult:
    hits: list[RetrievalHit]
    method: str
    dense_backend: str
    reranker_status: str
    model_status: str
    latency_ms: float


def load_corpus(
    db: Session, product: str | None = None, source_type: str | None = None
) -> list[CorpusRecord]:
    records: list[CorpusRecord] = []
    if source_type in (None, "github_issue"):
        incidents = (
            db.scalars(
                select(Incident)
                .options(joinedload(Incident.repository))
                .order_by(Incident.id)
            )
            .unique()
            .all()
        )
        for incident in incidents:
            if product and incident.product != product:
                continue
            content = " ".join(
                [
                    incident.description or "",
                    " ".join(incident.logs or []),
                    " ".join(incident.error_codes or []),
                    incident.affected_component or "",
                    incident.affected_version or "",
                ]
            )
            records.append(
                CorpusRecord(
                    key=f"github_issue:{incident.id}",
                    source_type="github_issue",
                    source_id=incident.id,
                    title=incident.title,
                    content=content,
                    source_url=incident.source_url,
                    metadata={
                        "product": incident.product,
                        "status": incident.status,
                        "error_codes": incident.error_codes or [],
                        "affected_component": incident.affected_component,
                        "affected_version": incident.affected_version,
                    },
                )
            )
    if source_type in (None, "documentation"):
        chunks = (
            db.scalars(
                select(DocumentChunk)
                .options(joinedload(DocumentChunk.document))
                .order_by(DocumentChunk.id)
            )
            .unique()
            .all()
        )
        for chunk in chunks:
            product_name = (
                (chunk.document.license_metadata or {}).get("product")
                if chunk.document
                else None
            )
            if product and product_name != product:
                continue
            if chunk.document:
                records.append(
                    CorpusRecord(
                        key=f"documentation:{chunk.id}",
                        source_type="documentation",
                        source_id=chunk.id,
                        title=f"{chunk.document.title} · section {chunk.chunk_index + 1}",
                        content=chunk.content,
                        source_url=chunk.document.source_url,
                        metadata={
                            "product": product_name,
                            "document_id": chunk.document.id,
                            "section": chunk.section,
                            "chunk_index": chunk.chunk_index,
                        },
                    )
                )
    return records


def excerpt(text: str, query_tokens: list[str], width: int = 300) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return "No text available."
    lower = cleaned.lower()
    offsets = [lower.find(token) for token in query_tokens if lower.find(token) >= 0]
    start = max(0, (min(offsets) if offsets else 0) - 70)
    result = cleaned[start : start + width]
    return (
        ("…" if start else "") + result + ("…" if start + width < len(cleaned) else "")
    )


def lexical_search(
    db: Session,
    query: str,
    limit: int = 30,
    product: str | None = None,
    source_type: str | None = None,
) -> list[RetrievalHit]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    records = load_corpus(db, product=product, source_type=source_type)
    tokenized = [tokenize(record.title + " " + record.content) for record in records]
    df = Counter(token for tokens in tokenized for token in set(tokens))
    avg_len = sum(len(tokens) for tokens in tokenized) / max(len(tokenized), 1)
    query_errors = {match.lower().replace(" ", "") for match in ERROR_RE.findall(query)}
    hits: list[RetrievalHit] = []
    for record, tokens in zip(records, tokenized, strict=False):
        counts = Counter(tokens)
        score = 0.0
        for term in query_tokens:
            if not counts[term]:
                continue
            idf = 1 + len(records) / (1 + df[term])
            score += idf * (
                (counts[term] * 2.2)
                / (counts[term] + 1.2 * (0.35 + 0.65 * len(tokens) / max(avg_len, 1)))
            )
            if term in tokenize(record.title):
                score += 2.0
        if (
            query_errors
            and set(code.lower() for code in record.metadata.get("error_codes", []))
            & query_errors
        ):
            score += 6.0
        if score:
            hits.append(
                RetrievalHit(
                    record.key,
                    record.source_type,
                    record.source_id,
                    record.title,
                    excerpt(record.content, query_tokens),
                    record.source_url,
                    score,
                    "exact error match"
                    if query_errors
                    and set(
                        code.lower() for code in record.metadata.get("error_codes", [])
                    )
                    & query_errors
                    else "lexical similarity",
                    record.metadata,
                )
            )
    hits.sort(key=lambda hit: (-hit.score, hit.key))
    return hits[:limit]


def retrieve(
    db: Session,
    query: str,
    limit: int = 10,
    mode: str = "LIGHT",
    product: str | None = None,
    source_type: str | None = None,
    rerank: bool = True,
) -> RetrievalResult:
    started = time.perf_counter()
    lexical = lexical_search(
        db, query, limit=max(limit * 4, 20), product=product, source_type=source_type
    )
    if mode.upper() == "LIGHT":
        return RetrievalResult(
            lexical[:limit],
            "BM25-style lexical + exact error boost",
            "not loaded",
            "not requested",
            "deterministic fallback active",
            round((time.perf_counter() - started) * 1000, 2),
        )
    records = load_corpus(db, product=product, source_type=source_type)
    by_key = {record.key: record for record in records}
    dense = dense_service.search(db, records, query, limit=max(limit * 4, 20))
    dense_keys = [item.key for item in dense]
    lexical_keys = [item.key for item in lexical]
    if not dense_keys:
        candidates = lexical[: max(limit * 2, 10)]
        method = "BM25-style lexical fallback (dense unavailable)"
    else:
        fused_keys = [
            key for key, _ in reciprocal_rank_fusion([lexical_keys, dense_keys])
        ]
        lexical_by_key = {hit.key: hit for hit in lexical}
        candidates = []
        for key in fused_keys:
            if key in lexical_by_key:
                candidates.append(lexical_by_key[key])
            elif key in by_key:
                record = by_key[key]
                candidates.append(
                    RetrievalHit(
                        record.key,
                        record.source_type,
                        record.source_id,
                        record.title,
                        excerpt(record.content, tokenize(query)),
                        record.source_url,
                        0.0,
                        "dense semantic match",
                        record.metadata,
                    )
                )
        method = "Hybrid RRF"
    reranker_status = "not requested"
    if rerank and candidates:
        pairs = [
            (
                candidate.key,
                (
                    by_key.get(candidate.key).title
                    + "\n"
                    + by_key.get(candidate.key).content
                )
                if by_key.get(candidate.key)
                else candidate.excerpt,
            )
            for candidate in candidates[: min(20, len(candidates))]
        ]
        reranked = dense_service.rerank(query, pairs)
        if reranked:
            candidate_by_key = {candidate.key: candidate for candidate in candidates}
            candidates = [
                candidate_by_key[key] for key, _ in reranked if key in candidate_by_key
            ]
            rerank_scores = dict(reranked)
            for candidate in candidates:
                candidate.score = rerank_scores.get(candidate.key, candidate.score)
                candidate.verification = "cross-encoder rerank"
            method += " + Cross-Encoder"
            reranker_status = f"loaded: {dense_service.status.reranker_model}"
        else:
            reranker_status = "unavailable; RRF order retained"
    model_status = (
        "embedding loaded"
        if dense_service.status.embedding_loaded
        else (dense_service.status.error or "embedding not loaded")
    )
    return RetrievalResult(
        candidates[:limit],
        method,
        dense_service.status.dense_backend,
        reranker_status,
        model_status,
        round((time.perf_counter() - started) * 1000, 2),
    )
