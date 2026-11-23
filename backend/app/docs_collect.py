from __future__ import annotations

import hashlib
import json
import ipaddress
import socket
from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import ROOT_DIR, get_settings
from .documents import chunk_document
from .models import (
    DataSource,
    DocumentChunk,
    Documentation,
    Repository,
    SyncJob,
    utcnow,
)


DOC_SEEDS = {
    "appsmith": ("https://docs.appsmith.com/", "docs.appsmith.com", "/"),
    "grafana": (
        "https://grafana.com/docs/grafana/latest/",
        "grafana.com",
        "/docs/grafana/latest/",
    ),
    "n8n": ("https://docs.n8n.io/", "docs.n8n.io", "/"),
    "supabase": ("https://supabase.com/docs", "supabase.com", "/docs"),
}


def _public_host(hostname: str) -> bool:
    try:
        addresses = {socket.gethostbyname_ex(hostname)[2][0]}
        return all(
            not ipaddress.ip_address(address).is_private
            and not ipaddress.ip_address(address).is_loopback
            for address in addresses
        )
    except (socket.gaierror, ValueError):
        return False


class OfficialDocsCrawler:
    def __init__(self) -> None:
        self.user_agent = get_settings().collector_user_agent
        self._robots: dict[str, RobotFileParser] = {}

    def allowed(self, url: str, host: str, path_prefix: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path or "/"
        normalized_prefix = path_prefix.rstrip("/") or "/"
        path_ok = (
            normalized_prefix == "/"
            or path == normalized_prefix
            or path.startswith(normalized_prefix + "/")
        )
        return (
            parsed.scheme == "https"
            and parsed.hostname == host
            and path_ok
            and _public_host(host)
        )

    def robots_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.hostname:
            return False
        base = f"{parsed.scheme}://{parsed.hostname}"
        if base not in self._robots:
            robots_url = f"{base}/robots.txt"
            parser = RobotFileParser()
            parser.set_url(robots_url)
            try:
                request = Request(robots_url, headers={"User-Agent": self.user_agent})
                with urlopen(request, timeout=20) as response:
                    parser.parse(
                        response.read().decode("utf-8", errors="replace").splitlines()
                    )
            except Exception:
                return False
            self._robots[base] = parser
        return self._robots[base].can_fetch(self.user_agent, url)

    def fetch(self, url: str) -> str:
        request = Request(
            url, headers={"Accept": "text/html", "User-Agent": self.user_agent}
        )
        with urlopen(request, timeout=30) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                raise RuntimeError(
                    f"Skipped non-HTML documentation response: {content_type}"
                )
            return response.read(2_000_000).decode("utf-8", errors="replace")

    def crawl(
        self, product: str, limit: int = 20, max_depth: int = 1
    ) -> list[dict[str, str]]:
        if product not in DOC_SEEDS:
            raise ValueError(f"Unsupported documentation product: {product}")
        seed, host, path_prefix = DOC_SEEDS[product]
        queue = deque([(seed, 0)])
        visited: set[str] = set()
        pages: list[dict[str, str]] = []
        while queue and len(pages) < limit:
            url, depth = queue.popleft()
            url = urldefrag(url)[0].rstrip("/") or url
            if (
                url in visited
                or depth > max_depth
                or not self.allowed(url, host, path_prefix)
            ):
                continue
            visited.add(url)
            if not self.robots_allowed(url):
                continue
            try:
                html = self.fetch(url)
            except Exception:
                continue
            soup = BeautifulSoup(html, "html.parser")
            for node in soup(["script", "style", "noscript", "nav", "footer"]):
                node.decompose()
            root = soup.find("main") or soup.find("article") or soup.body or soup
            text = root.get_text("\n", strip=True)
            if len(text) < 80:
                continue
            title_node = soup.find("h1") or soup.find("title")
            title = title_node.get_text(" ", strip=True) if title_node else url
            pages.append({"url": url, "title": title[:500], "content": text[:100_000]})
            if depth < max_depth:
                for link in soup.select("a[href]"):
                    child = urldefrag(urljoin(url + "/", link.get("href", "")))[0]
                    if self.allowed(child, host, path_prefix) and child not in visited:
                        queue.append((child, depth + 1))
        return pages


def collect_official_docs(
    db: Session, product: str, limit: int = 20
) -> dict[str, int | str]:
    crawler = OfficialDocsCrawler()
    pages = crawler.crawl(product, limit=limit)
    repo_name = {
        "appsmith": "appsmithorg/appsmith",
        "grafana": "grafana/grafana",
        "n8n": "n8n-io/n8n",
        "supabase": "supabase/supabase",
    }[product]
    repository = db.scalar(select(Repository).where(Repository.full_name == repo_name))
    source = db.scalar(
        select(DataSource).where(DataSource.uri == DOC_SEEDS[product][0])
    )
    if not source:
        source = DataSource(
            source_type="documentation",
            name=f"Official docs · {product}",
            uri=DOC_SEEDS[product][0],
            repository_id=repository.id if repository else None,
            license_metadata={"product": product, "attribution_required": True},
        )
        db.add(source)
    db.flush()
    job = SyncJob(source_id=source.id, status="running")
    db.add(job)
    db.flush()
    raw_dir = ROOT_DIR / "data" / "raw" / "docs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{product}.jsonl"
    created = updated = 0
    with raw_path.open("a", encoding="utf-8") as raw_file:
        for page in pages:
            content_hash = hashlib.sha256(page["content"].encode("utf-8")).hexdigest()
            raw_file.write(
                json.dumps(
                    {
                        "product": product,
                        "url": page["url"],
                        "title": page["title"],
                        "content_hash": content_hash,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            document = db.scalar(
                select(Documentation).where(Documentation.source_url == page["url"])
            )
            if not document:
                document = Documentation(
                    title=page["title"],
                    source_url=page["url"],
                    content=page["content"],
                    content_hash=content_hash,
                    license_metadata={
                        "product": product,
                        "source": "official public documentation",
                        "robots_checked": True,
                    },
                    collected_at=utcnow(),
                )
                db.add(document)
                created += 1
            elif document.content_hash != content_hash:
                document.title = page["title"]
                document.content = page["content"]
                document.content_hash = content_hash
                document.collected_at = utcnow()
                document.chunks.clear()
                updated += 1
            if not document.chunks:
                document.chunks.extend(
                    DocumentChunk(chunk_index=index, content=chunk)
                    for index, chunk in enumerate(chunk_document(page["content"]))
                )
    source.last_cursor = str(len(pages))
    source.last_synced_at = utcnow()
    job.status = "completed"
    job.items_seen = len(pages)
    job.items_created = created
    job.items_updated = updated
    job.finished_at = utcnow()
    db.commit()
    return {
        "product": product,
        "pages_seen": len(pages),
        "created": created,
        "updated": updated,
        "source_id": source.id,
    }
