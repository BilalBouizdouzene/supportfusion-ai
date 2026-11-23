import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="appsmithorg/appsmith")
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()
    return subprocess.call(
        [
            sys.executable,
            "scripts/collect_github.py",
            "--repo",
            args.repo,
            "--limit",
            str(args.limit),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
