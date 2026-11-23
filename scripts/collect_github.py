import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal, init_db  # noqa: E402
from backend.app.github import sync_repository  # noqa: E402
from backend.app.config import get_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect public GitHub issues into SupportFusion AI"
    )
    parser.add_argument("--repo", default=get_settings().github_default_repository)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument(
        "--include-comments",
        action="store_true",
        help="Fetch public issue comments; use with a token and a small limit",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Ignore the source cursor and reprocess the bounded window",
    )
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    init_db()
    with SessionLocal() as db:
        result = sync_repository(
            db,
            args.repo,
            args.limit,
            get_settings().github_token,
            include_comments=args.include_comments,
            incremental=not args.full,
        )
    print(f"repository={result.repository}")
    print(
        f"items_seen={result.items_seen} items_created={result.items_created} items_updated={result.items_updated}"
    )
    print(f"source_id={result.source_id} sync_job_id={result.sync_job_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
