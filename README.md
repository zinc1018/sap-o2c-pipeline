# sap-o2c-pipeline

An end-to-end analytics pipeline over SAP-style order-to-cash data. A Python generator
simulates an SAP system's daily extracts, a loader lands them in DuckDB, and dbt models
them into a star schema. The whole thing runs locally with no cloud accounts or Docker.

> **Status:** the generator, loader, dbt staging and marts, Dagster orchestration, deliveries,
> and receivables are done, and CI runs the whole pipeline on every push. Snowflake and failure
> alerts are in the [Roadmap](#roadmap).

## Why this exists

Real SAP systems are the usual source for order-to-cash analytics, but they aren't available
to learn on. This project generates data with real SAP table and field names (`VBAK`, `VBAP`,
`VBRK`, `KNA1`, ...) and the messiness of real extracts: changed orders, cancelled invoices,
duplicate rows, and orphaned items. The analytics modeling on top is the point of the repo.

## Quick start

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). No admin rights needed.

```bash
uv sync                                  # install dependencies
uv run generate --days 30                # simulate 30 business days of SAP extracts
uv run load                              # load the extracts into DuckDB
cd dbt && uv run dbt build && cd ..      # build staging models and run dbt tests
uv run pytest                            # run the test suite
```

To run generate, load, and dbt build as one step, use `uv run pipeline --days 30`. It shows each
step's progress and stops at the first failure.

dbt runs from the `dbt/` folder so its profile finds the warehouse at `data/warehouse.duckdb`.
`dbt build` reports one known warning: some billing items reference sales order items that don't
exist in the source data. The count depends on how much data was generated. The warning is
intentional and documented in [`dbt/models/staging/schema.yml`](dbt/models/staging/schema.yml).

Output goes to `data/` (git-ignored):

- `data/extracts/<TABLE>/<TABLE>_<YYYYMMDD>.csv`: one CSV per table per simulated day
- `data/warehouse.duckdb`: the DuckDB warehouse, with raw tables under `raw` and staging views under `staging`

You can inspect the result with the DuckDB CLI or Python:

```python
import duckdb
con = duckdb.connect("data/warehouse.duckdb", read_only=True)
con.sql("select count(*) from raw.VBAK").show()
con.sql("select count(*) from staging.stg_sap__vbak").show()
```

### Marts

`dbt/models/marts/` is a star schema for order-to-cash analysis:

| Model | Grain | What it's for |
|---|---|---|
| `dim_customer` | customer version | Customer attributes as they were on a given date (SCD type 2) |
| `dim_material` | material | Material description and type |
| `dim_date` | calendar day | Date attributes for reporting |
| `fct_sales_order_items` | sales order item | Ordered quantity and value |
| `fct_billing_items` | billing item | Billed quantity and value, with cancelled and orphaned items flagged |
| `fct_delivery_items` | delivery item | Quantity shipped against each sales order item, and days from order to delivery |
| `fct_receivable_items` | accounting item | Customer receivables with status `open` or `cleared`, and days to clear |

Each fact joins to the customer version in effect on its date, so a customer who moved
is reported under the right location for each order or invoice. Values are kept in document
currency, and `net_value_usd` uses the rates in `dbt/seeds/exchange_rates.csv`. Those rates are
illustrative fixed values for this project, not market data.

Customer history is built in SQL from every version in raw, not with a dbt snapshot. A snapshot
only records the state at the time it runs, so one build over this history would keep only the
latest version of each customer.

Tests check keys, relationships between facts and dimensions, and two business rules: billed
quantity never exceeds ordered quantity, and rejected order items are never billed.

### Staging models

`dbt/models/staging/` has one view per raw SAP table, named `stg_sap__<table>`. Each view:

- renames SAP fields to readable names (`VBELN` → `sales_order_id`, `NETWR` → `net_value`)
- casts text dates (`YYYYMMDD`) and amounts to proper types
- turns empty values (`''`, and `00000000` for dates) into NULL
- keeps the latest version of each business key, ordered by change date, then load time

Raw keeps every version, so the staging views can always be rebuilt from history.

## Orchestration

Dagster runs the pipeline as assets, one for each stage:

| Asset | What it does |
|---|---|
| `sap_extracts` | Simulates days of SAP extracts (`generate`). Retries twice on failure. |
| `raw_tables` | Loads the extracts into raw, producing one asset per raw table. Retries twice. |
| dbt models | Runs `dbt build` for staging, marts, seeds, and tests, one asset per model. |

The daily schedule (`daily_schedule`, 06:00) adds one simulated business day, loads it, and
rebuilds the dbt models. Each run adds new days after the last one, and loading is idempotent:
already-loaded files are skipped.

```bash
uv run dagster dev -m orchestration.definitions   # UI at http://localhost:3000
uv run pipeline --days 30                          # one headless run, no UI
```

Not built yet: per-day backfills. The generator only adds days after the last one, so there is
no way yet to fill a past date range.

## Commands

### `generate`

```bash
uv run generate --days N [--out data/extracts] [--seed 42] [--start 2026-01-01]
```

Adds N more simulated business days to the extract folder. Each run continues where the last
one stopped, and the same seed always produces identical output. The folder records its seed
and start date in `_generator.json`; if you rerun with different values, the command refuses
rather than mixing two histories. Use a new `--out` folder for a different history.

### `load`

```bash
uv run load [--extracts data/extracts] [--db data/warehouse.duckdb]
```

Appends extract files into `raw.<TABLE>`. Every row keeps `_loaded_at` and `_source_file`.
Files already recorded in `raw._load_log` are skipped, so running `load` again is safe. A file
with missing columns or unparseable content fails the run with a message naming the file, and
nothing from that file is loaded.

## What the data looks like

Tables (v1): `KNA1` (customers), `MARA` and `MAKT` (materials and descriptions), `VBAK` and
`VBAP` (sales order header and item), `VBRK` and `VBRP` (billing header and item).

Tables (v2): `LIKP` and `LIPS` (delivery header and item). Deliveries ship part or all of an
order item's open quantity, and each delivery item points back to the order item it ships.

Tables (v3): `BSID` (open receivables) and `BSAD` (cleared receivables). Each invoice opens a
receivable with 30-day terms. It clears on payment, usually after a few days, or on cancellation.
A receivable stays in `BSID` when it's posted, and its cleared version is written to `BSAD`.

Column order and business keys are defined in [`generator/schema.py`](generator/schema.py).

Deliberate issues, so the models have something real to handle:

- **Changed orders.** Some orders change after creation (later `AEDAT`) and reappear in later
  extracts. Raw keeps every version.
- **Cancelled invoices.** `VBRK.FKSTO = 'X'` marks a cancelled billing document.
- **Duplicates and orphans.** A few duplicate rows, and some invoice items reference sales order
  items that don't exist.
- **Orders reduced after shipping.** Some order items are reduced below the quantity already
  delivered, which SAP would normally block. The `shipped_qty_within_ordered_qty` test warns about
  these.
- **Two currencies.** USD and CAD.
- **Text-typed values.** Dates and amounts are written as text, as in real SAP extracts. Casting
  happens in dbt, not in the loader.

Out of scope for now: pricing conditions (`KONV`), document flow (`VBFA`), partner functions, and
full multi-currency handling. Billing doesn't wait for delivery, so an invoice can come before its
goods ship.

Extract folders made before v2 and v3 are missing the new tables. Generate new data into a fresh
`--out` folder rather than adding days to an old one.

## Design decisions

The full design is in [`docs/design.md`](docs/design.md). The short version:

- **Raw is append-only.** The warehouse keeps every version of every record, so history can be
  rebuilt. Idempotency comes from a load log, not from deleting and reloading.
- **Loading is per file.** Each file loads in its own transaction, so a bad file can't leave a
  partial load behind.
- **Data quality lives in dbt tests**, not in the loader. The loader only checks structure.
- **Deterministic simulation.** A fixed seed makes every run reproducible, which makes the tests
  and the data reviewable.
- **Local-first.** DuckDB and plain files mean no accounts or services to set up.

## Project layout

```
generator/   simulated SAP system: schema, simulation, `generate` CLI
loader/      CSV → DuckDB raw tables, `load` CLI
orchestration/  Dagster assets, daily schedule, `pipeline` CLI
dbt/         dbt project: staging and marts models, seeds, macros, tests
tests/       pytest suite for the generator and loader
docs/        design doc and milestone plans
```

## Development

```bash
uv run pytest           # Python tests
uv run ruff check       # lint (line length 100)
cd dbt && uv run dbt build   # dbt models and tests
```

## Roadmap

1. ✅ Generator (v1 tables), loader, pytest tests
2. ✅ dbt staging models and tests
3. ✅ Marts: star schema with customer SCD2 history
4. ✅ Dagster orchestration with a daily schedule (per-day backfills not built)
5. ✅ CI on GitHub Actions: lint, tests, generate → load → `dbt build` on every push
6. ✅ Deliveries (v2) and receivables (v3)
7. Later: a Snowflake target, failure alerts
