# SAP Order-to-Cash Pipeline — Design

Date: 2026-10-03

## Purpose

A public GitHub portfolio project demonstrating an end-to-end analytics pipeline over SAP order-to-cash data.

Focus: analytics modeling (star schema, SCD2), dbt, data quality tests, orchestration, automated tests and CI, applied to real SAP table structures.

### Success criteria

- A recruiter can clone the repo and run the whole pipeline with one command, free, with no cloud accounts or Docker.
- CI runs the full pipeline (generate → load → `dbt build`) on every push and is green.
- Every design decision is documented in the README.

### Constraints

- Runs locally on Linux/macOS with Python 3.12; no admin rights needed.
- Steady pace (a few hours a week, no deadline): every milestone leaves the repo runnable.

## Architecture

```
generator (Python) ──CSV──▶ loader (Python) ──▶ DuckDB raw.* ──dbt──▶ staging.* ──dbt──▶ marts.*
                         └──────────── orchestrated by Dagster, verified in GitHub Actions ───────────┘
```

Stack: Python 3.12, uv, DuckDB, dbt (dbt-duckdb adapter), Dagster (dagster-dbt), pytest, ruff, GitHub Actions.

## 1. Source data — fake SAP system (`generator/`)

Generates SAP-style extract CSVs using real SAP table and field names.

| Stage | Tables |
|---|---|
| v1 | `KNA1` (customer), `MARA` + `MAKT` (material + description), `VBAK`/`VBAP` (sales order header/item), `VBRK`/`VBRP` (billing header/item) |
| v2 | `LIKP`/`LIPS` (delivery header/item) |
| v3 | `BSID`/`BSAD` (open/cleared receivables) |

Key fields: `VBELN`, `POSNR`, `KUNNR`, `MATNR`, `NETWR`, `WAERK`, `ERDAT`, `AEDAT`, `FKSTO`. Dates and amounts are written as text, as in real SAP extracts.

Deliberate data issues:
- Orders changed after creation (later `AEDAT`), re-extracted in later files.
- Cancelled invoices (`FKSTO = 'X'`).
- A small number of duplicate rows and invoice items referencing missing order items.
- Two currencies: USD and CAD.

Behavior:
- `generate --days N` simulates N more business days, writing one dated CSV per table per day (new and changed records).
- A fixed seed makes output reproducible.

Out of scope: pricing conditions (`KONV`), document flow (`VBFA`), partner functions, full multi-currency handling.

## 2. Loading (`loader/`)

CSV extracts → DuckDB `raw` schema, one raw table per SAP table.

- Append-only: every row is inserted with `_loaded_at` and `_source_file`; raw is never updated or deleted, so it holds every version of every record.
- Idempotent: `raw._load_log` records loaded files; already-loaded files are skipped.
- A file with missing columns or that cannot be parsed fails the run with a message naming the file and problem; nothing from that file is loaded (one transaction per file).
- Row-level data quality is not the loader's job; dbt tests own it.
- Uses DuckDB's native CSV reader; no custom parsing.

## 3. dbt models and tests (`dbt/`)

Layers: `raw` (loader) → `staging` → `marts`.

### Staging (one model per SAP table, e.g. `stg_sap__vbak`)
- Rename SAP fields to readable names (`VBELN` → `sales_order_id`, `KUNNR` → `customer_id`, `NETWR` → `net_value`, ...).
- Cast dates and amounts to proper types.
- Keep the latest version per business key: `ROW_NUMBER()` over the key ordered by `AEDAT` desc, then `_loaded_at` desc.

### Marts

| Model | Grain | Notes |
|---|---|---|
| `dim_customer` | customer version | SCD type 2 via a dbt snapshot on customer master |
| `dim_material` | material | |
| `dim_date` | calendar day | |
| `fct_sales_order_items` | sales order item | ordered quantity and value |
| `fct_billing_items` | billing item | cancelled invoices flagged, not removed |

Currency: amounts kept in document currency; a dbt seed of exchange rates provides USD reporting values.

v1 business questions: ordered and billed value by customer, material and month; open (unbilled) order value; order-to-invoice days.

### Tests
- Generic: `unique` and `not_null` on keys, `relationships` (billing item → order item), `accepted_values` (currency in USD, CAD).
- Singular (custom SQL): billed quantity never exceeds ordered quantity; no active invoice for a cancelled order.
- The deliberate data issues are expected to fail some tests initially; each is resolved by fixing the model or setting the test to `warn`, with the reason documented.

Out of scope for v1: an intermediate layer (added only if a model grows too complex), dashboards, a semantic/metrics layer.

## 4. Orchestration, testing and CI

### Dagster (`orchestration/`)
- Assets: `generate` → `load_raw` → dbt models (via dagster-dbt, one asset per model).
- Daily schedule, retries on failure, backfills by day.
- Local UI via `dagster dev`.
- Failure alerts (email) deferred to a later milestone.

### Python tests (`tests/`, pytest)
- Generator: same seed gives identical output; foreign keys between tables resolve (except the deliberate bad rows); the deliberate issues are present.
- Loader: loading the same file twice adds no rows; a malformed file fails with a clear error and loads nothing.

### CI (`.github/workflows/`)
On every push: `ruff` → `pytest` → generate a small dataset → load → `dbt build`.

## Repo layout

```
generator/          fake SAP system
loader/             CSV → DuckDB raw
dbt/                dbt project: staging, marts, snapshots, seeds, tests
orchestration/      Dagster definitions and schedule
tests/              pytest
.github/workflows/  CI
README.md           architecture diagram, how to run, design decisions
```

Run: `uv sync`, then `uv run dagster dev` (UI) or `uv run pipeline` (one headless run).

## Milestones

1. Repo setup, generator (v1 tables), loader, pytest tests.
2. dbt staging models and tests.
3. Marts and SCD2 snapshot.
4. Dagster orchestration and schedule.
5. CI and README; make the repo public.
6. Later: deliveries (v2), receivables (v3), Snowflake target, failure alerts.
