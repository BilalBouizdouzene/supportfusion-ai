import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal, init_db  # noqa: E402
from backend.app.docs_collect import collect_official_docs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect bounded official documentation pages"
    )
    parser.add_argument(
        "--product", choices=["appsmith", "grafana", "n8n", "supabase"], required=True
    )
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    init_db()
    with SessionLocal() as db:
        print(collect_official_docs(db, args.product, max(1, min(args.limit, 50))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
