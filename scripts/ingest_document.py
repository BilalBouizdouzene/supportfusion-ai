import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal, init_db  # noqa: E402
from backend.app.documents import chunk_document, parse_document  # noqa: E402
from backend.app.models import DocumentChunk, Documentation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest one local document into the SupportFusion knowledge base"
    )
    parser.add_argument("path", type=Path)
    parser.add_argument("--source-url", default=None)
    args = parser.parse_args()
    parsed = parse_document(args.path)
    content_hash = hashlib.sha256(parsed.content.encode("utf-8")).hexdigest()
    source_url = args.source_url or f"file://{Path(args.path).resolve()}"
    init_db()
    with SessionLocal() as db:
        document = db.scalar(
            select(Documentation).where(Documentation.source_url == source_url)
        )
        if not document:
            document = Documentation(
                title=parsed.title,
                source_url=source_url,
                content=parsed.content,
                content_hash=content_hash,
                license_metadata={"source": "local import"},
                collected_at=datetime.now(timezone.utc),
            )
            db.add(document)
            db.flush()
        else:
            document.title = parsed.title
            document.content = parsed.content
            document.content_hash = content_hash
            document.chunks.clear()
        for index, chunk in enumerate(chunk_document(parsed.content)):
            document.chunks.append(
                DocumentChunk(chunk_index=index, content=chunk, section=None)
            )
        db.commit()
        print(
            f"document_id={document.id} chunks={len(document.chunks)} source_url={source_url}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
