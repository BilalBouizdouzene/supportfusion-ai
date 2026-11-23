"""Phase 1 indexing hook.

The LIGHT search backend indexes directly from SQLite, so this command validates
that the searchable corpus is available and reports its measured size.
"""

import sys
import argparse
from pathlib import Path

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal, init_db  # noqa: E402
from backend.app.models import Incident  # noqa: E402
from backend.app.retrieval import load_corpus  # noqa: E402
from backend.app.dense import dense_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dense",
        action="store_true",
        help="Build the persistent FAISS index and load the embedding model",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even when a compatible index exists",
    )
    args = parser.parse_args()
    init_db()
    with SessionLocal() as db:
        count = db.scalar(select(func.count(Incident.id))) or 0
        print(f"LIGHT lexical index ready: {count} incidents available from SQLite")
        if args.dense:
            records = load_corpus(db)
            result = dense_service.build_index(db, records, force=args.force)
            print(
                f"FAISS dense index {result['status']}: {result['items']} records, dimension={result['dimension']}, model={result['model']}, latency_ms={result['latency_ms']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
