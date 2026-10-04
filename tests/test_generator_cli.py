import csv

from generator.cli import main
from generator.schema import TABLES


def files(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*.csv")}


def test_writes_one_file_per_table_per_day(tmp_path):
    assert main(["--days", "2", "--out", str(tmp_path)]) == 0
    assert len(files(tmp_path)) == 2 * len(TABLES)
    assert (tmp_path / "VBAK" / "VBAK_20260102.csv").exists()


def test_chunked_runs_match_single_run(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for _ in range(3):
        main(["--days", "1", "--out", str(a)])
    main(["--days", "3", "--out", str(b)])
    assert files(a) == files(b)


def test_header_only_file_when_nothing_happened(tmp_path):
    main(["--days", "1", "--out", str(tmp_path)])
    with open(tmp_path / "VBRK" / "VBRK_20260101.csv", newline="") as f:
        assert list(csv.reader(f)) == [list(TABLES["VBRK"])]


def test_name_with_comma_and_quote_round_trips(tmp_path):
    main(["--days", "1", "--out", str(tmp_path)])
    with open(tmp_path / "KNA1" / "KNA1_20260101.csv", newline="") as f:
        names = [r["NAME1"] for r in csv.DictReader(f)]
    assert 'Smith, Jones & "Co"' in names


def test_prints_written_range(tmp_path, capsys):
    main(["--days", "2", "--out", str(tmp_path)])
    main(["--days", "1", "--out", str(tmp_path)])
    out = capsys.readouterr().out.splitlines()
    assert out == [
        f"wrote days 2026-01-01..2026-01-02 to {tmp_path}",
        f"wrote days 2026-01-03..2026-01-03 to {tmp_path}",
    ]
