"""`load`: append new SAP extract CSVs into the DuckDB warehouse."""

import argparse
import sys
from pathlib import Path

from loader.load import LoadError, load_extracts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load SAP extract CSVs into DuckDB raw tables.")
    parser.add_argument("--extracts", type=Path, default=Path("data/extracts"))
    parser.add_argument("--db", type=Path, default=Path("data/warehouse.duckdb"))
    args = parser.parse_args(argv)
    try:
        r = load_extracts(args.extracts, args.db)
    except LoadError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"loaded {r.files_loaded} files ({r.rows_loaded} rows), skipped {r.files_skipped}")
    return 0
