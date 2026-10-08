# Milestone 1: Generator and Loader — Implementation Plan

**Goal:** A reproducible fake SAP order-to-cash system that writes daily extract CSVs, and an idempotent loader that appends them into DuckDB `raw` tables, both covered by pytest.

**Architecture:** `generator/` replays a seeded day-by-day simulation from a fixed start date and writes only the days not yet on disk, so output never depends on how runs are chunked. `loader/` reads each CSV as all-text with DuckDB, validates columns against the shared schema in `generator/schema.py`, and appends rows plus lineage columns inside one transaction per file, recording each file in `raw._load_log`.

**Tech Stack:** Python 3.12, uv, DuckDB, pytest, ruff. Generator uses the standard library only (`random`, `csv`, `datetime`, `argparse`).

**Spec:** `docs/design.md` (sections 1, 2, 4 "Python tests", Repo layout, Milestone 1)

## Global Constraints

- Python `>=3.12`; runtime dependency: `duckdb` only. Dev dependencies: `pytest`, `ruff`.
- Real SAP table and field names; all values written as text. Dates `YYYYMMDD`; the SAP initial (empty) date is `00000000`. Amounts with two decimals, e.g. `1234.50`.
- Keys zero-padded: `KUNNR` and `VBELN` 10 digits, `MATNR` 18 digits, `POSNR` 6 digits. `MANDT` is always `100`.
- Currencies: `USD` and `CAD` only.
- Raw tables are append-only; each row gets `_loaded_at` (TIMESTAMP) and `_source_file` (file name only, e.g. `VBAK_20260101.csv`).
- `data/` is git-ignored. Default paths: extracts `data/extracts`, warehouse `data/warehouse.duckdb`.

## Review Focus

1. **Leading zeros** — `KUNNR` `0000000001` must stay `0000000001` in DuckDB, not become `1`. Test in Task 5.
2. **Header-only files** — a day with no billing still writes `VBRK_<day>.csv` with only a header; the loader loads 0 rows and still logs the file. Tests in Tasks 4 and 5.
3. **Chunked runs** — `generate --days 1` run 3 times must produce byte-identical files to `generate --days 3` once. Test in Task 4.
4. **Commas and quotes in names** — a customer `NAME1` like `Smith, Jones & "Co"` must round-trip through CSV and DuckDB unchanged. Tests in Tasks 2 and 5.
5. **Missing extracts folder** — `load` with a non-existent folder exits 1 with a message naming the folder, not a stack trace. Test in Task 5.

---

### Task 1: Project setup and shared SAP schema

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `generator/__init__.py`, `generator/schema.py`, `loader/__init__.py`
- Test: `tests/test_schema.py`

**Interfaces:**
- Produces: `generator.schema.TABLES: dict[str, tuple[str, ...]]` (table → ordered column names) and `generator.schema.KEYS: dict[str, tuple[str, ...]]` (table → business-key columns).

- [x] **Step 1: Install uv** (user-level, no admin rights)

Run: `curl -LsSf https://astral.sh/uv/install.sh | sh` then `uv --version`
Expected: prints a version.

- [x] **Step 2: Create `pyproject.toml`**

Project name `sap-o2c-pipeline`, `requires-python = ">=3.12"`, dependency `duckdb`, dev group `pytest`, `ruff`. Build backend `hatchling` with packages `generator` and `loader`. Scripts: `generate = "generator.cli:main"`, `load = "loader.cli:main"`. Ruff: `line-length = 100`, `select = ["E", "F", "I", "B", "UP"]`. Pytest: `testpaths = ["tests"]`.

`.gitignore`: `data/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`.

- [x] **Step 3: Write the failing test** in `tests/test_schema.py`

```python
from generator.schema import KEYS, TABLES

def test_v1_tables():
    assert set(TABLES) == {"KNA1", "MARA", "MAKT", "VBAK", "VBAP", "VBRK", "VBRP"}

def test_every_table_starts_with_client():
    assert all(cols[0] == "MANDT" for cols in TABLES.values())

def test_keys_are_columns_of_their_table():
    for table, key in KEYS.items():
        assert set(key) <= set(TABLES[table])

def test_change_date_columns():
    for table in ("VBAK", "VBAP", "VBRK", "VBRP"):
        assert "AEDAT" in TABLES[table]
    assert "LAEDA" in TABLES["MARA"]
    assert "AEDAT" not in TABLES["KNA1"]  # real KNA1 has no change date
```

- [x] **Step 4: Run to verify it fails**

Run: `uv run pytest tests/test_schema.py -v`
Expected: FAIL, `ModuleNotFoundError: generator.schema`.

- [x] **Step 5: Implement `generator/schema.py`** with exactly these columns and keys:

| Table | Columns (in order) | Key |
|---|---|---|
| KNA1 | MANDT, KUNNR, NAME1, ORT01, REGIO, LAND1, ERDAT | KUNNR |
| MARA | MANDT, MATNR, MTART, MATKL, MEINS, ERSDA, LAEDA | MATNR |
| MAKT | MANDT, MATNR, SPRAS, MAKTX | MATNR, SPRAS |
| VBAK | MANDT, VBELN, AUART, ERDAT, AUDAT, KUNNR, WAERK, NETWR, AEDAT | VBELN |
| VBAP | MANDT, VBELN, POSNR, MATNR, KWMENG, VRKME, NETWR, WAERK, ABGRU, ERDAT, AEDAT | VBELN, POSNR |
| VBRK | MANDT, VBELN, FKART, FKDAT, KUNRG, WAERK, NETWR, FKSTO, ERDAT, AEDAT | VBELN |
| VBRP | MANDT, VBELN, POSNR, AUBEL, AUPOS, MATNR, FKIMG, VRKME, NETWR, ERDAT, AEDAT | VBELN, POSNR |

`ABGRU` (rejection reason) on VBAP is how an order item is cancelled; `AUBEL`/`AUPOS` on VBRP reference the sales order item.

- [x] **Step 6: Run tests and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: 4 passed; ruff reports no errors.

- [x] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .gitignore generator loader tests
git commit -m "chore: project setup and SAP v1 table schema"
```

---

### Task 2: Simulation — master data and sales orders

**Files:**
- Create: `generator/simulate.py`
- Test: `tests/test_simulate_orders.py`

**Interfaces:**
- Consumes: `TABLES` from Task 1.
- Produces: `simulate(start: date, days: int, seed: int = 42) -> Iterator[tuple[date, dict[str, list[dict[str, str]]]]]`. Yields one `(day, extracts)` per day; `extracts` has a key for **every** table in `TABLES` (empty list when nothing happened); each row is a dict with exactly that table's columns, all values `str`. Each day's rows are a delta: records created or changed that day.

Behavior for this task (one `random.Random(seed)` consumed in day order — the only randomness source):
- Day 1 only: 50 customers (80% `LAND1=US`/`WAERK` USD, 20% `CA`/CAD), 30 materials (each with a fixed unit price between 10.00 and 500.00, `MEINS=EA`, one `MAKT` row with `SPRAS=E`). At least one customer `NAME1` contains a comma and a double quote.
- Every day: `randint(5, 15)` new orders, each with `randint(1, 4)` items numbered `000010`, `000020`, …; `VBELN` sequential from `0000000001`; order `WAERK` = customer currency; item `NETWR` = qty × unit price; header `NETWR` = sum of items; new records have `AEDAT=00000000` and `ABGRU=""`.

- [x] **Step 1: Write the failing tests**

```python
from datetime import date
from generator.schema import TABLES
from generator.simulate import simulate

START = date(2026, 1, 1)

def days(n, seed=42):
    return list(simulate(START, n, seed))

def test_same_seed_same_output():
    assert days(5) == days(5)

def test_different_seed_different_output():
    assert days(2, seed=1) != days(2, seed=2)

def test_every_table_every_day_with_exact_columns():
    for _, extracts in days(3):
        assert set(extracts) == set(TABLES)
        for table, rows in extracts.items():
            assert all(list(r) == list(TABLES[table]) for r in rows)

def test_master_data_on_day_one():
    (_, d1), (_, d2) = days(2)
    assert len(d1["KNA1"]) == 50 and len(d1["MARA"]) == 30 and len(d1["MAKT"]) == 30
    assert all(len(r["KUNNR"]) == 10 and len(r["MATNR"]) == 18 for r in d1["KNA1"] + d1["MARA"])
    assert any("," in r["NAME1"] and '"' in r["NAME1"] for r in d1["KNA1"])

def test_orders_link_and_sum():
    _, d1 = days(1)[0]
    customers = {r["KUNNR"]: r for r in d1["KNA1"]}
    assert 5 <= len(d1["VBAK"]) <= 15
    for h in d1["VBAK"]:
        items = [i for i in d1["VBAP"] if i["VBELN"] == h["VBELN"]]
        assert 1 <= len(items) <= 4
        assert h["KUNNR"] in customers
        assert h["WAERK"] == ("USD" if customers[h["KUNNR"]]["LAND1"] == "US" else "CAD")
        assert f'{sum(float(i["NETWR"]) for i in items):.2f}' == h["NETWR"]
        assert h["AEDAT"] == "00000000"
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_simulate_orders.py -v`
Expected: FAIL, `ModuleNotFoundError: generator.simulate`.

- [x] **Step 3: Implement `simulate`** in `generator/simulate.py` per the behavior above. Keep simulation state (customers, materials, open orders) in plain dicts inside the function; format values to text only when emitting rows.

- [x] **Step 4: Run tests and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add generator/simulate.py tests/test_simulate_orders.py
git commit -m "feat: simulate SAP master data and sales orders"
```

---

### Task 3: Simulation — changes, billing, cancellations and deliberate data issues

**Files:**
- Modify: `generator/simulate.py`
- Test: `tests/test_simulate_billing.py`

**Interfaces:**
- Consumes/produces: same `simulate` signature as Task 2. Adds module constants: `CHANGE_RATE = 0.10`, `REJECT_RATE = 0.03`, `BILL_RATE = 0.40`, `CANCEL_RATE = 0.03`, `CUSTOMER_CHANGE_RATE = 0.02`, `DUPLICATE_RATE = 0.01`, `ORPHAN_RATE = 0.005`.

Behavior added (applied each day after new orders, in this order):
1. **Order changes:** each unbilled order, with `CHANGE_RATE`, has one item's qty changed (recompute item and header `NETWR`); separately, with `REJECT_RATE`, one not-yet-rejected item gets `ABGRU="02"`. A changed order's header and all its items are re-emitted with `AEDAT` = today.
2. **Customer changes:** each customer, with `CUSTOMER_CHANGE_RATE`, moves city (`ORT01`, `REGIO`); the full KNA1 row is re-emitted.
3. **Billing:** each unbilled order created at least 2 days earlier is billed with `BILL_RATE`: one VBRK (`FKART=F2`, `FKSTO=""`, `KUNRG` = order customer) plus one VBRP per non-rejected item with `FKIMG` = ordered qty; invoice `VBELN` sequential from `0090000001`. Billed orders are never changed again. An order whose items are all rejected is never billed.
4. **Cancellations:** each active invoice, with `CANCEL_RATE`, gets `FKSTO="X"` and `AEDAT` = today; the VBRK row is re-emitted.
5. **Deliberate issues:** with `ORPHAN_RATE` per new billing item, `AUBEL` points to an order number never created; with `DUPLICATE_RATE` per emitted row (any table), the row is emitted twice in the same day.

- [x] **Step 1: Write the failing tests** (60 simulated days, seed 42)

```python
from datetime import date
from generator.simulate import simulate

ALL = list(simulate(date(2026, 1, 1), 60, 42))
rows = lambda t: [r for _, e in ALL for r in e[t]]

def test_billing_starts_no_earlier_than_day_three():
    assert all(not e["VBRK"] for _, e in ALL[:2])
    assert rows("VBRK")

def test_billing_items_match_ordered_qty_and_skip_rejected():
    latest = {(r["VBELN"], r["POSNR"]): r for r in rows("VBAP")}
    for b in rows("VBRP"):
        item = latest.get((b["AUBEL"], b["AUPOS"]))
        if item:  # orphans have no order item
            assert item["ABGRU"] == "" and b["FKIMG"] == item["KWMENG"]

def test_changes_and_cancellations_reemit_with_aedat():
    changed = [r for r in rows("VBAK") if r["AEDAT"] != "00000000"]
    cancelled = [r for r in rows("VBRK") if r["FKSTO"] == "X"]
    assert changed and cancelled
    assert all(r["AEDAT"] != "00000000" for r in cancelled)
    assert any(r["ABGRU"] == "02" for r in rows("VBAP"))

def test_customer_changes_reemit_kna1():
    cities = {}
    for r in rows("KNA1"):
        cities.setdefault(r["KUNNR"], set()).add(r["ORT01"])
    assert any(len(c) > 1 for c in cities.values())

def test_deliberate_issues_present():
    order_ids = {r["VBELN"] for r in rows("VBAK")}
    assert any(b["AUBEL"] not in order_ids for b in rows("VBRP"))
    assert any(len(e[t]) != len({tuple(r.values()) for r in e[t]})
               for _, e in ALL for t in e)
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_simulate_billing.py -v`
Expected: FAIL (no billing rows yet).

- [x] **Step 3: Implement the behavior above** in `generator/simulate.py`.

- [x] **Step 4: Run all tests and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: all pass, including Task 2 tests.

- [x] **Step 5: Commit**

```bash
git add generator/simulate.py tests/test_simulate_billing.py
git commit -m "feat: simulate order changes, billing, cancellations and data issues"
```

---

### Task 4: Generator CLI — write daily CSV extracts incrementally

**Files:**
- Create: `generator/cli.py`
- Test: `tests/test_generator_cli.py`

**Interfaces:**
- Consumes: `simulate` (Tasks 2–3), `TABLES`.
- Produces: `main(argv: list[str] | None = None) -> int`. Options: `--days N` (required, ≥1), `--out PATH` (default `data/extracts`), `--seed INT` (default 42), `--start YYYY-MM-DD` (default `2026-01-01`). File layout: `<out>/<TABLE>/<TABLE>_<YYYYMMDD>.csv`, header row = `TABLES[table]`, written with `csv.writer` (minimal quoting), UTF-8, `\n` line endings.

Behavior: count existing days as the number of `KNA1_*.csv` files in `<out>/KNA1`; simulate `existing + N` days from `--start`; write only the days after the existing ones. Every table gets a file every day (header-only when empty). Prints `wrote days <first>..<last> to <out>`.

- [x] **Step 1: Write the failing tests**

```python
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
    assert any("," in n and '"' in n for n in names)
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_generator_cli.py -v`
Expected: FAIL, `ModuleNotFoundError: generator.cli`.

- [x] **Step 3: Implement `main`** in `generator/cli.py` with `argparse`.

- [x] **Step 4: Run all tests, lint, and a manual run**

Run: `uv run pytest -v && uv run ruff check . && uv run generate --days 3 && ls data/extracts/VBAK`
Expected: all pass; prints `wrote days 2026-01-01..2026-01-03 to data/extracts`; lists 3 VBAK files.

- [x] **Step 5: Commit**

```bash
git add generator/cli.py tests/test_generator_cli.py
git commit -m "feat: generate command writes daily SAP extract CSVs"
```

---

### Task 5: Loader — idempotent append into DuckDB raw

**Files:**
- Create: `loader/load.py`, `loader/cli.py`
- Test: `tests/test_loader.py`

**Interfaces:**
- Consumes: `TABLES` (Task 1); CSV layout from Task 4.
- Produces:
  - `class LoadError(Exception)`; message always starts with the offending file or folder path.
  - `@dataclass LoadResult: files_loaded: int; files_skipped: int; rows_loaded: int`
  - `load_extracts(extracts_dir: Path, db_path: Path) -> LoadResult`
  - `loader.cli.main(argv: list[str] | None = None) -> int` with `--extracts` (default `data/extracts`) and `--db` (default `data/warehouse.duckdb`); prints `loaded N files (R rows), skipped S`; on `LoadError` prints `error: <message>` to stderr and returns 1.

Behavior:
- Missing `extracts_dir` → `LoadError`. Creates schema `raw` and `raw._load_log(file_name VARCHAR PRIMARY KEY, table_name VARCHAR, row_count BIGINT, loaded_at TIMESTAMP)` if absent.
- For each table in `TABLES`, each `<TABLE>/*.csv` in sorted order: skip if `file_name` is in `_load_log`; otherwise, in one transaction: read the header line with the `csv` module and require its column set to equal `TABLES[table]` (else `LoadError` naming missing/extra columns); read the data with `read_csv(path, header=true, columns={col: 'VARCHAR' for col in header})` so nothing is type-guessed and header-only files work; create `raw.<TABLE>` if absent (all `VARCHAR` columns in schema order, plus `_loaded_at TIMESTAMP`, `_source_file VARCHAR`), insert rows with `current_timestamp` and the file name, insert the log row. Any error rolls back that file and raises `LoadError(f"{path}: {problem}")`. Files loaded earlier in the run stay committed.
- Header-only CSVs: load 0 rows, still logged.

- [x] **Step 1: Write the failing tests**

```python
import duckdb, pytest
from generator.cli import main as generate
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
    assert r.files_loaded == 35 and r.files_skipped == 0
    assert q(db, "select count(*) from raw._load_log") == [(35,)]
    assert q(db, "select count(*) from raw.KNA1")[0][0] >= 50

def test_second_run_adds_nothing(extracts, tmp_path):
    db = tmp_path / "w.duckdb"
    first = load_extracts(extracts, db)
    before = q(db, "select count(*) from raw.VBAP")
    second = load_extracts(extracts, db)
    assert (second.files_loaded, second.files_skipped, second.rows_loaded) == (0, 35, 0)
    assert q(db, "select count(*) from raw.VBAP") == before
    assert first.rows_loaded == sum(n for (n,) in q(db, "select row_count from raw._load_log"))

def test_new_days_load_incrementally(extracts, tmp_path):
    db = tmp_path / "w.duckdb"
    load_extracts(extracts, db)
    generate(["--days", "2", "--out", str(extracts)])
    assert load_extracts(extracts, db).files_loaded == 14

def test_text_preserved_exactly(extracts, tmp_path):
    db = tmp_path / "w.duckdb"
    load_extracts(extracts, db)
    assert q(db, "select min(KUNNR) from raw.KNA1") == [("0000000001",)]
    assert q(db, """select count(*) from raw.KNA1 where NAME1 like '%,%' and NAME1 like '%"%'""")[0][0] >= 1
    assert q(db, "select distinct _source_file from raw.KNA1 order by 1 limit 1") == [("KNA1_20260101.csv",)]

def test_header_only_file_loads_zero_rows(extracts, tmp_path):
    db = tmp_path / "w.duckdb"
    load_extracts(extracts, db)
    assert q(db, "select row_count from raw._load_log where file_name = 'VBRK_20260101.csv'") == [(0,)]

def test_bad_file_fails_cleanly_and_loads_nothing_from_it(extracts, tmp_path):
    bad = extracts / "VBAK" / "VBAK_20260106.csv"
    bad.write_text("MANDT,VBELN\n100,0000099999\n")
    db = tmp_path / "w.duckdb"
    with pytest.raises(LoadError, match="VBAK_20260106.csv"):
        load_extracts(extracts, db)
    assert q(db, "select count(*) from raw.VBAK where _source_file = 'VBAK_20260106.csv'") == [(0,)]
    assert q(db, "select count(*) from raw._load_log where file_name = 'VBAK_20260106.csv'") == [(0,)]

def test_cli_missing_folder_exits_1(tmp_path, capsys):
    assert load_cli(["--extracts", str(tmp_path / "nope"), "--db", str(tmp_path / "w.duckdb")]) == 1
    assert "nope" in capsys.readouterr().err
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_loader.py -v`
Expected: FAIL, `ModuleNotFoundError: loader.load`.

- [x] **Step 3: Implement `load_extracts`, `LoadError`, `LoadResult`** in `loader/load.py` and `main` in `loader/cli.py`, per the behavior above. Build table names only from `TABLES` keys, never from file names.

- [x] **Step 4: Run all tests, lint, and the end-to-end manual check**

Run: `uv run pytest -v && uv run ruff check . && rm -rf data && uv run generate --days 30 && uv run load && uv run load`
Expected: all tests pass; first `load` prints `loaded 210 files (… rows), skipped 0`; second prints `loaded 0 files (0 rows), skipped 210`.

- [x] **Step 5: Commit**

```bash
git add loader tests/test_loader.py
git commit -m "feat: idempotent loader for SAP extracts into DuckDB raw"
```
