"""Append SAP extract CSVs into DuckDB `raw` tables, one transaction per file."""

import csv
from dataclasses import dataclass
from pathlib import Path

import duckdb

from generator.schema import TABLES


class LoadError(Exception):
    """A file or folder could not be loaded; the message starts with its path."""


@dataclass
class LoadResult:
    files_loaded: int = 0
    files_skipped: int = 0
    rows_loaded: int = 0


def load_extracts(extracts_dir: Path, db_path: Path) -> LoadResult:
    if not extracts_dir.is_dir():
        raise LoadError(f"{extracts_dir}: extracts folder not found")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    result = LoadResult()
    with duckdb.connect(str(db_path)) as con:
        con.execute("create schema if not exists raw")
        con.execute(
            "create table if not exists raw._load_log (file_name varchar primary key, "
            "table_name varchar, row_count bigint, loaded_at timestamp)"
        )
        loaded = {name for (name,) in con.execute("select file_name from raw._load_log").fetchall()}
        for table in TABLES:
            for path in sorted((extracts_dir / table).glob(f"{table}_*.csv")):
                if path.name in loaded:
                    result.files_skipped += 1
                    continue
                result.rows_loaded += _load_file(con, table, path)
                result.files_loaded += 1
    return result


def _load_file(con: duckdb.DuckDBPyConnection, table: str, path: Path) -> int:
    columns = TABLES[table]
    try:
        with open(path, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f), [])
            f.read()  # decode the whole file so a non-UTF-8 byte fails here, clearly
    except (UnicodeDecodeError, OSError) as e:
        raise LoadError(f"{path}: cannot read as UTF-8 text ({e})") from e
    missing, extra = set(columns) - set(header), set(header) - set(columns)
    if missing or extra:
        raise LoadError(f"{path}: missing columns {sorted(missing)}, unexpected {sorted(extra)}")

    # Header names are now known-good schema names, safe to place in SQL.
    # Every column is read as text so SAP values (leading zeros, 00000000) stay exact,
    # and nullstr is a value that never occurs so empty fields stay '' instead of NULL.
    col_defs = ", ".join(f'"{c}" varchar' for c in columns)
    col_list = ", ".join(f'"{c}"' for c in columns)
    read_spec = "{" + ", ".join(f"'{c}': 'varchar'" for c in header) + "}"
    con.begin()
    try:
        con.execute(
            f"create table if not exists raw.{table} "
            f"({col_defs}, _loaded_at timestamp, _source_file varchar)"
        )
        (rows,) = con.execute(
            f"insert into raw.{table} select {col_list}, current_timestamp, ? "
            f"from read_csv(?, header = true, delim = ',', quote = '\"', escape = '\"', "
            f"nullstr = '\\N', "
            f"columns = {read_spec})",
            [path.name, str(path)],
        ).fetchone()
        con.execute(
            "insert into raw._load_log values (?, ?, ?, current_timestamp)",
            [path.name, table, rows],
        )
        con.commit()
    except duckdb.Error as e:
        con.rollback()
        raise LoadError(f"{path}: {e}") from e
    return rows
