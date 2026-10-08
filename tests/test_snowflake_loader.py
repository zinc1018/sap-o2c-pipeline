"""Logic of the Snowflake loader, run against a fake connection (no account needed)."""

import pytest

from generator.cli import main as generate
from generator.schema import TABLES
from loader.checks import LoadError
from loader.snowflake import connect_from_env, load_extracts_snowflake


class FakeCursor:
    def __init__(self, already_loaded=()):
        self.statements = []
        self.loaded = list(already_loaded)

    def execute(self, sql, params=None):
        self.statements.append(sql)
        return self

    def fetchall(self):
        return [(name,) for name in self.loaded]

    def fetchone(self):
        return (None, "LOADED", None, 7)  # COPY result: rows_loaded is the fourth column


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


@pytest.fixture
def extracts(tmp_path):
    generate(["--days", "2", "--out", str(tmp_path / "x")])
    return tmp_path / "x"


def test_loads_every_file_through_stage_and_copy(extracts):
    cur = FakeCursor()
    result = load_extracts_snowflake(extracts, FakeConnection(cur))
    files = 2 * len(TABLES)
    assert (result.files_loaded, result.files_skipped) == (files, 0)
    assert result.rows_loaded == 7 * files
    assert sum(s.startswith("put ") for s in cur.statements) == files
    assert sum(s.startswith("copy into") for s in cur.statements) == files
    assert sum("insert into RAW._LOAD_LOG" in s for s in cur.statements) == files


def test_skips_files_already_in_the_load_log(extracts):
    done = [p.name for p in (extracts / "KNA1").glob("*.csv")]
    result = load_extracts_snowflake(extracts, FakeConnection(FakeCursor(already_loaded=done)))
    assert result.files_skipped == len(done)
    assert result.files_loaded == 2 * len(TABLES) - len(done)


def test_bad_header_fails_before_any_upload(tmp_path):
    folder = tmp_path / "x" / "KNA1"
    folder.mkdir(parents=True)
    (folder / "KNA1_20260101.csv").write_text("MANDT,KUNNR\n100,1\n", encoding="utf-8")
    cur = FakeCursor()
    with pytest.raises(LoadError, match="missing columns"):
        load_extracts_snowflake(tmp_path / "x", FakeConnection(cur))
    assert not any(s.startswith("put ") for s in cur.statements)


def test_reordered_columns_are_read_by_name(tmp_path):
    generate(["--days", "1", "--out", str(tmp_path / "x")])
    folder = tmp_path / "x" / "KNA1"
    path = folder / "KNA1_20260101.csv"
    header, *rows = path.read_text(encoding="utf-8").splitlines()
    cols = header.split(",")
    swapped = [",".join([cols[1], cols[0], *cols[2:]])] + [
        ",".join([r.split(",")[1], r.split(",")[0], *r.split(",")[2:]]) for r in rows
    ]
    path.write_text("\n".join(swapped) + "\n", encoding="utf-8")
    cur = FakeCursor()
    load_extracts_snowflake(tmp_path / "x", FakeConnection(cur))
    copy = next(s for s in cur.statements if s.startswith("copy into RAW.KNA1"))
    assert "$2" in copy and "$1" in copy  # MANDT now sits in column 2 of the file


def test_connect_reports_missing_settings():
    with pytest.raises(LoadError, match="SNOWFLAKE_ACCOUNT"):
        connect_from_env({})
