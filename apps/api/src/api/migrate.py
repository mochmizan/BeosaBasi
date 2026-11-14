"""CLI: python -m api.migrate --db <path> [--to N]. Up/down migrations (TK-020)."""

import argparse

from api.db import LATEST_VERSION, migrate
from api.db import connect as db_connect


def main() -> None:
    parser = argparse.ArgumentParser(description="BeosaBasi SQLite migrations (TK-020)")
    parser.add_argument("--db", required=True, help="SQLite file path")
    parser.add_argument("--to", type=int, default=None,
                        help=f"target version 0..{LATEST_VERSION} (default: latest)")
    args = parser.parse_args()
    version = migrate(args.db, args.to)
    conn = db_connect(args.db)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        print(f"migrated to version {version} (journal_mode={mode})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
