"""Load SAP extract CSVs into Snowflake RAW, the same way loader/load.py loads DuckDB.

Connection settings come from environment variables: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER,
SNOWFLAKE_PASSWORD, SNOWFLAKE_DATABASE, SNOWFLAKE_WAREHOUSE, and optionally SNOWFLAKE_ROLE.

This path is not yet verified against a live Snowflake account. The logic is covered by tests
that use a fake connection; see the README.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from generator.schema import TABLES
from loader.checks import LoadError, read_header
from loader.load import LoadResult

REQUIRED_ENV = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_WAREHOUSE",
)


def connect_from_env(env: Mapping[str, str] = os.environ):
    missing = [name for name in REQUIRED_ENV if not env.get(name)]
    if missing:
        raise LoadError(f"missing environment variables: {', '.join(missing)}")
    # Imported here so DuckDB runs don't need the Snowflake package installed.
    import snowflake.connector

    return snowflake.connector.connect(
        account=env["SNOWFLAKE_ACCOUNT"],
        user=env["SNOWFLAKE_USER"],
        password=env["SNOWFLAKE_PASSWORD"],
        database=env["SNOWFLAKE_DATABASE"],
        warehouse=env["SNOWFLAKE_WAREHOUSE"],
        role=env.get("SNOWFLAKE_ROLE") or None,
        schema="RAW",
    )


def load_extracts_snowflake(extracts_dir: Path, connection) -> LoadResult:
    if not extracts_dir.is_dir():
        raise LoadError(f"{extracts_dir}: extracts folder not found")
    cur = connection.cursor()
    cur.execute("create schema if not exists RAW")
    # Snowflake doesn't enforce primary keys, so FILE_NAME uniqueness is kept by this loader.
    cur.execute(
        "create table if not exists RAW._LOAD_LOG (FILE_NAME varchar, TABLE_NAME varchar, "
        "ROW_COUNT number, LOADED_AT timestamp_ntz)"
    )
    loaded = {row[0] for row in cur.execute("select FILE_NAME from RAW._LOAD_LOG").fetchall()}

    result = LoadResult()
    for table in TABLES:
        for path in sorted((extracts_dir / table).glob(f"{table}_*.csv")):
            if path.name in loaded:
                result.files_skipped += 1
                continue
            result.rows_loaded += _load_file(cur, table, path)
            result.files_loaded += 1
    return result


def _load_file(cur, table: str, path: Path) -> int:
    header = read_header(path, table)
    columns = TABLES[table]
    col_defs = ", ".join(f'"{c}" varchar' for c in columns)
    col_list = ", ".join(f'"{c}"' for c in columns)
    # Read each column by its position in this file's header, so the file's column order is free.
    positions = ", ".join(f"${header.index(c) + 1}" for c in columns)
    stage_file = f"{path.name}.gz"
    try:
        cur.execute(
            f"create table if not exists RAW.{table} "
            f"({col_defs}, _loaded_at timestamp_ntz, _source_file varchar)"
        )
        # Upload to the user's stage, then COPY from it. Empty fields stay '' and \N is NULL,
        # matching the DuckDB loader.
        cur.execute(f"put 'file://{path.resolve()}' @~ auto_compress = true overwrite = true")
        cur.execute(
            f"copy into RAW.{table} ({col_list}, _loaded_at, _source_file) "
            f"from (select {positions}, current_timestamp(), '{path.name}' from @~/{stage_file}) "
            "file_format = (type = csv skip_header = 1 field_optionally_enclosed_by = '\"' "
            "empty_field_as_null = false null_if = ('\\\\N')) on_error = abort_statement"
        )
        rows = cur.fetchone()[3]  # rows_loaded in COPY's result
        cur.execute(
            "insert into RAW._LOAD_LOG (FILE_NAME, TABLE_NAME, ROW_COUNT, LOADED_AT) "
            "values (%s, %s, %s, current_timestamp())",
            (path.name, table, rows),
        )
        cur.execute(f"remove @~/{stage_file}")
    except Exception as e:  # the connector raises its own error types; report them with the file
        raise LoadError(f"{path}: {e}") from e
    return rows
