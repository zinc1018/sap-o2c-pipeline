"""`load`: append new SAP extract CSVs into the warehouse (DuckDB by default, or Snowflake)."""

import argparse
import sys
from pathlib import Path

from loader.checks import LoadError
from loader.load import load_extracts
from loader.snowflake import connect_from_env, load_extracts_snowflake


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load SAP extract CSVs into raw tables.")
    parser.add_argument("--extracts", type=Path, default=Path("data/extracts"))
    parser.add_argument("--db", type=Path, default=Path("data/warehouse.duckdb"))
    parser.add_argument("--target", choices=["duckdb", "snowflake"], default="duckdb")
    args = parser.parse_args(argv)
    try:
        if args.target == "snowflake":
            connection = connect_from_env()
            try:
                r = load_extracts_snowflake(args.extracts, connection)
            finally:
                connection.close()
        else:
            r = load_extracts(args.extracts, args.db)
    except LoadError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"loaded {r.files_loaded} files ({r.rows_loaded} rows), skipped {r.files_skipped}")
    return 0
