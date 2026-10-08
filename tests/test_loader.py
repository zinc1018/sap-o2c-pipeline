import duckdb
import pytest

from generator.cli import main as generate
from generator.schema import TABLES
from loader.cli import main as load_cli
from loader.load import LoadError, load_extracts


@pytest.fixture
def extracts(tmp_path):
    generate(["--days", "5", "--out", str(tmp_path / "x")])
    return tmp_path / "x"


def q(db, sql):
    with duckdb.connect(str(db)) as con:
        return con.execute(sql).fetchall()


def test_loads_every_file_and_row(extracts, tmp_path):
    db = tmp_path / "w.duckdb"
    r = load_extracts(extracts, db)
    assert r.files_loaded == 5 * len(TABLES) and r.files_skipped == 0
    assert q(db, "select count(*) from raw._load_log") == [(5 * len(TABLES),)]
    assert q(db, "select count(*) from raw.KNA1")[0][0] >= 50
    assert r.rows_loaded == sum(n for (n,) in q(db, "select row_count from raw._load_log"))


def test_second_run_adds_nothing(extracts, tmp_path):
    db = tmp_path / "w.duckdb"
    load_extracts(extracts, db)
    before = q(db, "select count(*) from raw.VBAP")
    second = load_extracts(extracts, db)
    files = 5 * len(TABLES)
    assert (second.files_loaded, second.files_skipped, second.rows_loaded) == (0, files, 0)
    assert q(db, "select count(*) from raw.VBAP") == before


def test_new_days_load_incrementally(extracts, tmp_path):
    db = tmp_path / "w.duckdb"
    load_extracts(extracts, db)
    generate(["--days", "2", "--out", str(extracts)])
    assert load_extracts(extracts, db).files_loaded == 2 * len(TABLES)


def test_text_preserved_exactly(extracts, tmp_path):
    db = tmp_path / "w.duckdb"
    load_extracts(extracts, db)
    assert q(db, "select min(KUNNR) from raw.KNA1") == [("0000000001",)]
    names = [n for (n,) in q(db, "select NAME1 from raw.KNA1")]
    assert 'Smith, Jones & "Co"' in names
    first = q(db, "select min(_source_file) from raw.KNA1")
    assert first == [("KNA1_20260101.csv",)]


def test_raw_columns_are_schema_plus_lineage(extracts, tmp_path):
    db = tmp_path / "w.duckdb"
    load_extracts(extracts, db)
    cols = q(db, "select column_name, data_type from information_schema.columns "
                 "where table_schema = 'raw' and table_name = 'VBRK' order by ordinal_position")
    assert [c for c, _ in cols][-2:] == ["_loaded_at", "_source_file"]
    assert {t for c, t in cols if not c.startswith("_")} == {"VARCHAR"}


def test_header_only_file_loads_zero_rows(extracts, tmp_path):
    db = tmp_path / "w.duckdb"
    load_extracts(extracts, db)
    sql = "select row_count from raw._load_log where file_name = 'VBRK_20260101.csv'"
    assert q(db, sql) == [(0,)]


def test_bad_file_fails_cleanly_and_loads_nothing_from_it(extracts, tmp_path):
    bad = extracts / "VBAK" / "VBAK_20260106.csv"
    bad.write_text("MANDT,VBELN\n100,0000099999\n")
    db = tmp_path / "w.duckdb"
    with pytest.raises(LoadError, match="VBAK_20260106.csv"):
        load_extracts(extracts, db)
    assert q(db, "select count(*) from raw.VBAK where _source_file = 'VBAK_20260106.csv'") == [(0,)]
    assert q(db, "select count(*) from raw._load_log where file_name = 'VBAK_20260106.csv'") == [
        (0,)
    ]


def test_cli_missing_folder_exits_1(tmp_path, capsys):
    assert load_cli(["--extracts", str(tmp_path / "nope"), "--db", str(tmp_path / "w.duckdb")]) == 1
    assert "nope" in capsys.readouterr().err


def test_cli_reports_counts(extracts, tmp_path, capsys):
    args = ["--extracts", str(extracts), "--db", str(tmp_path / "w.duckdb")]
    assert load_cli(args) == 0
    assert load_cli(args) == 0
    first, second = capsys.readouterr().out.splitlines()
    files = 5 * len(TABLES)
    assert first.startswith(f"loaded {files} files (") and first.endswith("rows), skipped 0")
    assert second == f"loaded 0 files (0 rows), skipped {files}"


def test_empty_sap_fields_load_as_empty_text_not_null(extracts, tmp_path):
    db = tmp_path / "w.duckdb"
    load_extracts(extracts, db)
    assert q(db, "select count(*) from raw.VBRK where FKSTO is null") == [(0,)]
    assert q(db, "select count(*) from raw.VBRK where FKSTO = ''")[0][0] > 0
    assert q(db, "select count(*) from raw.VBAP where ABGRU = ''")[0][0] > 0


def test_non_utf8_file_fails_cleanly(extracts, tmp_path):
    bad = extracts / "KNA1" / "KNA1_20260106.csv"
    bad.write_bytes(b"MANDT,KUNNR,NAME1,ORT01,REGIO,LAND1,ERDAT\n100,0000000099,M\xfcller,X,Y,US,20260106\n")
    with pytest.raises(LoadError, match="KNA1_20260106.csv"):
        load_extracts(extracts, tmp_path / "w.duckdb")
