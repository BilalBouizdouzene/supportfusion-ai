from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import ROOT_DIR, get_settings
from .logs import extract_log_excerpts
from .models import (
    DataSource,
    Incident,
    IncidentComment,
    IncidentMedia,
    IncidentRelation,
    Repository,
    SyncJob,
    utcnow,
)


ERROR_PATTERN = re.compile(
    r"\b(?:ERR[_-]?[A-Z0-9_-]+|[A-Z][A-Z0-9_]{2,}_ERROR|HTTP\s*[45]\d\d|[45]\d\d)\b"
)
IMAGE_PATTERN = re.compile(
    r"https?://[^\s)\]>]+\.(?:png|jpe?g|gif|webp)(?:\?[^\s)\]>]+)?", re.I
)
PR_PATTERN = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+", re.I)
VERSION_PATTERN = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?(?:[-+][0-9A-Za-z.-]+)?\b")
SECRET_PATTERN = re.compile(
    r"(?i)(bearer\s+)[A-Za-z0-9._-]+|((?:token|password|secret|api[_-]?key)\s*[:=]\s*)[^\s,;]+"
)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def sanitize_text(value: str | None) -> str:
    if not value:
        return ""
    return SECRET_PATTERN.sub(
        lambda match: f"{match.group(1) or match.group(2) or ''}[REDACTED]", value
    ).strip()


def extract_error_codes(text: str) -> list[str]:
    normalized: set[str] = set()
    for match in ERROR_PATTERN.findall(text or ""):
        compact = match.replace(" ", "")
        normalized.add(compact.removeprefix("HTTP"))
    return sorted(normalized)


def extract_component(labels: list[str], text: str) -> str | None:
    for label in labels:
        if ":" in label and label.lower().split(":", 1)[0] in {
            "component",
            "area",
            "module",
            "team",
        }:
            return label.split(":", 1)[1].strip() or None
    for label in labels:
        if any(
            marker in label.lower()
            for marker in (
                "api",
                "auth",
                "database",
                "datasource",
                "editor",
                "workflow",
            )
        ):
            return label
    match = re.search(r"(?i)\b(?:component|module|service)\s*[:=]\s*([\w./-]+)", text)
    return match.group(1) if match else None


def extract_version(text: str) -> str | None:
    match = VERSION_PATTERN.search(text or "")
    return match.group(0) if match else None


def content_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class CollectorResult:
    repository: str
    items_seen: int
    items_created: int
    items_updated: int
    source_id: int
    sync_job_id: int


class GitHubClient:
    def __init__(self, token: str | None = None, user_agent: str | None = None) -> None:
        self.token = token
        self.user_agent = user_agent or get_settings().collector_user_agent

    def get(self, url: str, retries: int = 3) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(retries):
            try:
                request = Request(url, headers=headers, method="GET")
                with urlopen(request, timeout=45) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                if error.code in {403, 429} and attempt < retries - 1:
                    time.sleep(2**attempt)
                    continue
                body = error.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"GitHub API HTTP {error.code}: {body[:300]}"
                ) from error
            except (URLError, TimeoutError) as error:
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError(f"GitHub API network error: {error}") from error
        raise RuntimeError("GitHub API request failed")

    def fetch_issues(
        self, repository: str, limit: int, since: str | None = None
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while len(items) < limit and page <= 10:
            since_query = f"&since={quote(since)}" if since else ""
            url = f"https://api.github.com/repos/{repository}/issues?state=all&sort=updated&direction=desc&per_page=100&page={page}{since_query}"
            payload = self.get(url)
            if not isinstance(payload, list) or not payload:
                break
            items.extend(item for item in payload if "pull_request" not in item)
            page += 1
        return items[:limit]

    def fetch_comments(
        self, repository: str, issue_number: int, limit: int = 20
    ) -> list[dict[str, Any]]:
        payload = self.get(
            f"https://api.github.com/repos/{repository}/issues/{issue_number}/comments?per_page={min(limit, 100)}"
        )
        return payload if isinstance(payload, list) else []


def _raw_path(repository: str) -> Path:
    safe_name = repository.replace("/", "__")
    path = ROOT_DIR / "data" / "raw" / "github"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{safe_name}.jsonl"


def _incident_payload(item: dict[str, Any], repository: str) -> dict[str, Any]:
    body = sanitize_text(item.get("body") or "")
    labels = [
        label.get("name") for label in item.get("labels", []) if label.get("name")
    ]
    combined_text = f"{item.get('title', '')}\n{body}"
    errors = extract_error_codes(combined_text)
    logs = extract_log_excerpts(body)
    pull_requests = sorted(set(PR_PATTERN.findall(combined_text)))
    return {
        "source_type": "github_issue",
        "external_id": str(item["id"]),
        "repository": repository,
        "title": sanitize_text(item.get("title")),
        "body": body,
        "labels": labels,
        "error_codes": errors,
        "logs": logs,
        "affected_component": extract_component(labels, combined_text),
        "affected_version": extract_version(combined_text),
        "pull_requests": pull_requests,
        "source_url": item.get("html_url"),
        "state": item.get("state"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "user": (item.get("user") or {}).get("login"),
        "comments_count": item.get("comments", 0),
    }


def sync_repository(
    db: Session,
    repository: str,
    limit: int,
    token: str | None = None,
    include_comments: bool = False,
    incremental: bool = True,
) -> CollectorResult:
    client = GitHubClient(token=token)
    source = db.scalar(
        select(DataSource).where(DataSource.uri == f"https://github.com/{repository}")
    )
    if not source:
        repo = db.scalar(select(Repository).where(Repository.full_name == repository))
        if not repo:
            repo = Repository(
                full_name=repository, html_url=f"https://github.com/{repository}"
            )
            db.add(repo)
            db.flush()
        source = DataSource(
            source_type="github",
            name=f"GitHub · {repository}",
            uri=f"https://github.com/{repository}",
            repository_id=repo.id,
            license_metadata={"attribution_required": True},
        )
        db.add(source)
        db.flush()
    job = SyncJob(source_id=source.id, status="running")
    db.add(job)
    db.flush()
    try:
        items = client.fetch_issues(
            repository, limit, since=source.last_cursor if incremental else None
        )
        raw_file = _raw_path(repository)
        created = updated = 0
        with raw_file.open("a", encoding="utf-8") as handle:
            for item in items:
                payload = _incident_payload(item, repository)
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
                current_hash = content_hash(payload)
                incident = db.scalar(
                    select(Incident).where(
                        Incident.source_type == "github_issue",
                        Incident.external_id == payload["external_id"],
                    )
                )
                if not incident:
                    incident = Incident(
                        source_type="github_issue",
                        external_id=payload["external_id"],
                        repository_id=source.repository_id,
                        created_at=utcnow(),
                    )
                    db.add(incident)
                    created += 1
                elif incident.source_hash != current_hash:
                    updated += 1
                incident.product = repository.split("/", 1)[-1]
                incident.title = payload["title"]
                incident.description = payload["body"]
                incident.symptoms = payload["labels"]
                incident.error_codes = payload["error_codes"]
                incident.logs = payload["logs"]
                incident.affected_component = payload["affected_component"]
                incident.affected_version = payload["affected_version"]
                incident.status = payload["state"]
                incident.source_url = payload["source_url"]
                incident.source_hash = current_hash
                incident.observed_at = parse_datetime(payload["created_at"])
                incident.source_updated_at = parse_datetime(payload["updated_at"])
                incident.license_metadata = {
                    "source": "GitHub public issue",
                    "attribution_url": payload["source_url"],
                }
                incident.provenance = {
                    "collector": "github_rest_api",
                    "raw_file": str(raw_file.relative_to(ROOT_DIR)),
                    "observed_fields": [
                        "title",
                        "body",
                        "labels",
                        "state",
                        "timestamps",
                    ],
                    "inferred_fields": ["product"],
                }
                for image_url in sorted(set(IMAGE_PATTERN.findall(payload["body"]))):
                    if not any(
                        media.source_url == image_url for media in incident.media
                    ):
                        incident.media.append(
                            IncidentMedia(
                                media_type="image",
                                source_url=image_url,
                                license_metadata={
                                    "parent_source_url": payload["source_url"]
                                },
                            )
                        )
                if not any(
                    comment.external_id == str(item.get("id"))
                    for comment in incident.comments
                ):
                    incident.comments.append(
                        IncidentComment(
                            external_id=str(item.get("id")),
                            author=payload["user"],
                            body=payload["body"],
                            source_url=payload["source_url"],
                            created_at=incident.observed_at,
                        )
                    )
                for pull_request_url in payload["pull_requests"]:
                    relation_exists = db.scalar(
                        select(IncidentRelation).where(
                            IncidentRelation.source_incident_id == incident.id,
                            IncidentRelation.relation_type == "ISSUE_LINKED_TO_PR",
                            IncidentRelation.target_id == pull_request_url,
                        )
                    )
                    if not relation_exists:
                        db.add(
                            IncidentRelation(
                                source_incident_id=incident.id,
                                relation_type="ISSUE_LINKED_TO_PR",
                                target_type="PullRequest",
                                target_id=pull_request_url,
                                evidence="Explicit pull request URL observed in the public issue body",
                                confidence=1.0,
                            )
                        )
                if include_comments:
                    for public_comment in client.fetch_comments(
                        repository, int(item.get("number", 0))
                    ):
                        comment_id = str(public_comment.get("id"))
                        if any(
                            existing.external_id == comment_id
                            for existing in incident.comments
                        ):
                            continue
                        incident.comments.append(
                            IncidentComment(
                                external_id=comment_id,
                                author=(public_comment.get("user") or {}).get("login"),
                                body=sanitize_text(public_comment.get("body")),
                                source_url=public_comment.get("html_url"),
                                created_at=parse_datetime(
                                    public_comment.get("created_at")
                                ),
                            )
                        )
        job.status = "completed"
        job.items_seen = len(items)
        job.items_created = created
        job.items_updated = updated
        job.finished_at = utcnow()
        source.last_cursor = (
            items[-1].get("updated_at") if items else source.last_cursor
        )
        source.last_synced_at = utcnow()
        db.commit()
        return CollectorResult(
            repository, len(items), created, updated, source.id, job.id
        )
    except Exception as error:
        db.rollback()
        job.status = "failed"
        job.error_message = str(error)[:2000]
        job.finished_at = utcnow()
        db.add(job)
        db.commit()
        raise
