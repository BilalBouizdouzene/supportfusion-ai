from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str


class DashboardResponse(BaseModel):
    incidents: int
    documents: int
    images: int
    logs: int
    tickets: int
    products: list[dict[str, Any]]
    frequent_errors: list[dict[str, Any]]
    recent_syncs: list[dict[str, Any]]
    search_mode: str


class IncidentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    product: str | None
    repository: str | None = None
    status: str
    source_url: str
    error_codes: list[str] | None
    affected_component: str | None
    observed_at: datetime | None


class IncidentDetail(IncidentListItem):
    comments: list[dict[str, Any]] = []
    media: list[dict[str, Any]] = []
    provenance: dict[str, Any] | None = None
    license_metadata: dict[str, Any] | None = None


class SearchResult(BaseModel):
    source_id: int
    source_type: str
    title: str
    excerpt: str
    source_url: str
    score: float
    rank: int
    verification: str
    metadata: dict[str, Any] = {}


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    retrieval_method: str
    dense_backend: str
    reranker_status: str
    latency_ms: float
    model_status: str


class GitHubSyncRequest(BaseModel):
    repository: str = Field(min_length=3, pattern=r"^[\w.-]+/[\w.-]+$")
    limit: int = Field(default=50, ge=1, le=100)
    include_comments: bool = False


class GitHubSyncResponse(BaseModel):
    status: str
    repository: str
    items_seen: int
    items_created: int
    items_updated: int
    source_id: int
    sync_job_id: int
    message: str


class TicketAnalysisRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=20000)
    priority: str = Field(default="medium", pattern=r"^(low|medium|high|urgent)$")


class TicketAnalysisResponse(BaseModel):
    ticket_id: int
    analysis_id: int
    classification: str
    hypotheses: list[dict[str, Any]]
    missing_information: list[str]
    draft_response: str
    evidence: list[SearchResult]
    validation_required: bool
    evidence_bundle_id: int
    retrieval_method: str
    dense_backend: str
    reranker_status: str
    model_status: str
    latency_ms: float
