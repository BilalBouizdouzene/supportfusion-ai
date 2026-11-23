from __future__ import annotations

import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from .config import get_settings
from .db import get_db, init_db
from .github import sync_repository
from .logs import signature_for_log
from .models import (
    Analysis,
    DataSource,
    Documentation,
    EvidenceBundle,
    ImageAsset,
    Incident,
    IncidentMedia,
    SyncJob,
    Ticket,
)
from .retrieval import RetrievalHit, retrieve
from .schemas import (
    DashboardResponse,
    GitHubSyncRequest,
    GitHubSyncResponse,
    HealthResponse,
    IncidentDetail,
    IncidentListItem,
    SearchResponse,
    SearchResult,
    TicketAnalysisRequest,
    TicketAnalysisResponse,
)


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="SupportFusion AI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    db.execute(select(func.count(Incident.id)))
    return HealthResponse(status="ok", database="connected", version="0.1.0")


@app.get("/api/dashboard", response_model=DashboardResponse)
def dashboard(db: Session = Depends(get_db)) -> DashboardResponse:
    product_rows = db.execute(
        select(Incident.product, func.count(Incident.id))
        .where(Incident.product.is_not(None))
        .group_by(Incident.product)
        .order_by(desc(func.count(Incident.id)))
        .limit(8)
    ).all()
    error_counter: dict[str, int] = {}
    for codes in db.scalars(select(Incident.error_codes)).all():
        for code in codes or []:
            error_counter[code] = error_counter.get(code, 0) + 1
    sync_rows = (
        db.scalars(
            select(SyncJob)
            .options(joinedload(SyncJob.source))
            .order_by(desc(SyncJob.started_at))
            .limit(8)
        )
        .unique()
        .all()
    )
    return DashboardResponse(
        incidents=db.scalar(select(func.count(Incident.id))) or 0,
        documents=db.scalar(select(func.count(Documentation.id))) or 0,
        images=(db.scalar(select(func.count(ImageAsset.id))) or 0)
        + (db.scalar(select(func.count(IncidentMedia.id))) or 0),
        logs=sum(len(logs or []) for logs in db.scalars(select(Incident.logs)).all()),
        tickets=db.scalar(select(func.count(Ticket.id))) or 0,
        products=[{"name": name, "count": count} for name, count in product_rows],
        frequent_errors=[
            {"name": name, "count": count}
            for name, count in sorted(
                error_counter.items(), key=lambda pair: (-pair[1], pair[0])
            )[:8]
        ],
        recent_syncs=[
            {
                "id": job.id,
                "source": job.source.name if job.source else "Unknown",
                "status": job.status,
                "items": job.items_seen,
                "created": job.items_created,
                "started_at": job.started_at.isoformat(),
            }
            for job in sync_rows
        ],
        search_mode=settings.search_mode,
    )


def _incident_item(incident: Incident) -> IncidentListItem:
    return IncidentListItem(
        id=incident.id,
        title=incident.title,
        description=incident.description,
        product=incident.product,
        repository=incident.repository.full_name if incident.repository else None,
        status=incident.status,
        source_url=incident.source_url,
        error_codes=incident.error_codes,
        affected_component=incident.affected_component,
        observed_at=incident.observed_at,
    )


def _search_result(hit: RetrievalHit, rank: int) -> SearchResult:
    return SearchResult(
        source_id=hit.source_id,
        source_type=hit.source_type,
        title=hit.title,
        excerpt=hit.excerpt,
        source_url=hit.source_url,
        score=round(hit.score, 4),
        rank=rank,
        verification=hit.verification,
        metadata=hit.metadata,
    )


@app.get("/api/incidents", response_model=list[IncidentListItem])
def incidents(
    db: Session = Depends(get_db),
    q: str | None = None,
    product: str | None = None,
    status: str | None = None,
    limit: int = Query(default=40, ge=1, le=100),
) -> list[IncidentListItem]:
    statement = (
        select(Incident)
        .options(joinedload(Incident.repository))
        .order_by(desc(Incident.source_updated_at))
        .limit(limit)
    )
    if product:
        statement = statement.where(Incident.product == product)
    if status:
        statement = statement.where(Incident.status == status)
    rows = list(db.scalars(statement).unique().all())
    if q:
        query_lower = q.lower()
        rows = [
            row
            for row in rows
            if query_lower in f"{row.title} {row.description or ''}".lower()
        ]
    return [_incident_item(row) for row in rows]


@app.get("/api/incidents/{incident_id}", response_model=IncidentDetail)
def incident_detail(incident_id: int, db: Session = Depends(get_db)) -> IncidentDetail:
    incident = db.scalar(
        select(Incident)
        .options(
            joinedload(Incident.repository),
            joinedload(Incident.comments),
            joinedload(Incident.media),
        )
        .where(Incident.id == incident_id)
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    item = _incident_item(incident)
    return IncidentDetail(
        **item.model_dump(),
        comments=[
            {
                "author": comment.author,
                "body": comment.body,
                "source_url": comment.source_url,
                "created_at": comment.created_at.isoformat()
                if comment.created_at
                else None,
            }
            for comment in incident.comments
        ],
        media=[
            {
                "media_type": media.media_type,
                "source_url": media.source_url,
                "ocr_text": media.ocr_text,
            }
            for media in incident.media
        ],
        provenance=incident.provenance,
        license_metadata=incident.license_metadata,
    )


@app.get("/api/search", response_model=SearchResponse)
def search(
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=50),
    mode: str | None = None,
    product: str | None = None,
    source_type: str | None = None,
    rerank: bool = True,
    db: Session = Depends(get_db),
) -> SearchResponse:
    retrieval = retrieve(
        db,
        q,
        limit=limit,
        mode=(mode or settings.search_mode).upper(),
        product=product,
        source_type=source_type,
        rerank=rerank,
    )
    return SearchResponse(
        query=q,
        results=[
            _search_result(item, index)
            for index, item in enumerate(retrieval.hits, start=1)
        ],
        retrieval_method=retrieval.method,
        dense_backend=retrieval.dense_backend,
        reranker_status=retrieval.reranker_status,
        latency_ms=retrieval.latency_ms,
        model_status=retrieval.model_status,
    )


@app.get("/api/sources")
def sources(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    rows = (
        db.scalars(
            select(DataSource)
            .options(joinedload(DataSource.sync_jobs))
            .order_by(DataSource.created_at.desc())
        )
        .unique()
        .all()
    )
    return [
        {
            "id": source.id,
            "name": source.name,
            "source_type": source.source_type,
            "uri": source.uri,
            "enabled": source.enabled,
            "last_cursor": source.last_cursor,
            "last_synced_at": source.last_synced_at.isoformat()
            if source.last_synced_at
            else None,
            "syncs": [
                {
                    "id": job.id,
                    "status": job.status,
                    "items_seen": job.items_seen,
                    "items_created": job.items_created,
                    "started_at": job.started_at.isoformat(),
                }
                for job in source.sync_jobs[-5:]
            ],
        }
        for source in rows
    ]


@app.get("/api/documents")
def documents(
    db: Session = Depends(get_db), limit: int = Query(default=50, ge=1, le=100)
) -> list[dict[str, object]]:
    rows = db.scalars(
        select(Documentation).order_by(desc(Documentation.collected_at)).limit(limit)
    ).all()
    return [
        {
            "id": document.id,
            "title": document.title,
            "source_url": document.source_url,
            "chunks": len(document.chunks),
            "content_hash": document.content_hash,
            "collected_at": document.collected_at.isoformat(),
        }
        for document in rows
    ]


@app.get("/api/logs")
def logs(
    db: Session = Depends(get_db), limit: int = Query(default=50, ge=1, le=200)
) -> list[dict[str, object]]:
    rows = db.scalars(select(Incident).order_by(desc(Incident.updated_at))).all()
    results: list[dict[str, object]] = []
    for incident in rows:
        for index, excerpt in enumerate(incident.logs or []):
            results.append(
                {
                    "incident_id": incident.id,
                    "title": incident.title,
                    "source_url": incident.source_url,
                    "excerpt": excerpt,
                    "signature": signature_for_log(excerpt),
                    "error_codes": incident.error_codes or [],
                    "index": index,
                }
            )
    return results[:limit]


@app.post("/api/sync/github", response_model=GitHubSyncResponse)
def sync_github(
    payload: GitHubSyncRequest, db: Session = Depends(get_db)
) -> GitHubSyncResponse:
    result = sync_repository(
        db,
        payload.repository,
        payload.limit,
        settings.github_token,
        include_comments=payload.include_comments,
    )
    return GitHubSyncResponse(
        status="completed",
        repository=result.repository,
        items_seen=result.items_seen,
        items_created=result.items_created,
        items_updated=result.items_updated,
        source_id=result.source_id,
        sync_job_id=result.sync_job_id,
        message="Public GitHub issues synchronized with provenance and pull requests excluded.",
    )


@app.post("/api/tickets/analyze", response_model=TicketAnalysisResponse)
def analyze_ticket(
    payload: TicketAnalysisRequest, db: Session = Depends(get_db)
) -> TicketAnalysisResponse:
    ticket = Ticket(
        title=payload.title, description=payload.description, priority=payload.priority
    )
    db.add(ticket)
    db.flush()
    retrieval = retrieve(
        db,
        f"{payload.title}\n{payload.description}",
        limit=5,
        mode=settings.search_mode,
        rerank=True,
    )
    evidence = [
        _search_result(item, index)
        for index, item in enumerate(retrieval.hits, start=1)
    ]
    if evidence and evidence[0].score >= 4:
        classification = "strong candidate match"
        hypotheses = [
            {
                "label": "Related public incident",
                "confidence": min(0.95, round(evidence[0].score / 12, 2)),
                "basis": evidence[0].verification,
                "source_id": evidence[0].source_id,
            }
        ]
        draft = f"We found a potentially related public incident: {evidence[0].title}. We are validating whether the same conditions apply to your environment before confirming a resolution."
    elif evidence:
        classification = "partial match"
        hypotheses = [
            {
                "label": "Partial lexical match",
                "confidence": 0.45,
                "basis": evidence[0].verification,
                "source_id": evidence[0].source_id,
            }
        ]
        draft = "We found a partial match in the public incident knowledge base. We need additional environment and version details before recommending a fix."
    else:
        classification = "insufficient evidence"
        hypotheses = []
        draft = "We could not find a reliable public match yet. We are requesting more diagnostic details before proposing a resolution."
    missing = []
    if not re.search(r"\b\d+\.\d+(?:\.\d+)?\b", payload.description):
        missing.append("Software version")
    if not re.search(
        r"\b(?:ERR|HTTP|error|exception|failed)\b", payload.description, re.I
    ):
        missing.append("Exact error message or code")
    bundle = EvidenceBundle(
        query=f"{payload.title}\n{payload.description}",
        results=[item.model_dump() for item in evidence],
        retrieval_method=retrieval.method,
        latency_ms=retrieval.latency_ms,
    )
    db.add(bundle)
    db.flush()
    result = {
        "classification": classification,
        "hypotheses": hypotheses,
        "missing_information": missing,
        "draft_response": draft,
        "evidence": [item.model_dump() for item in evidence],
        "validation_required": True,
        "evidence_bundle_id": bundle.id,
        "retrieval_method": retrieval.method,
        "dense_backend": retrieval.dense_backend,
        "reranker_status": retrieval.reranker_status,
        "model_status": retrieval.model_status,
        "latency_ms": retrieval.latency_ms,
    }
    analysis = Analysis(ticket_id=ticket.id, mode=settings.search_mode, result=result)
    db.add(analysis)
    db.commit()
    return TicketAnalysisResponse(
        ticket_id=ticket.id, analysis_id=analysis.id, **result
    )
