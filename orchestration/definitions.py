"""Dagster definitions: generate → load → dbt build, on a daily schedule.

Run the UI with `uv run dagster dev -m orchestration.definitions`.
"""

import subprocess
import sys
from pathlib import Path

import dagster as dg
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

from generator.cli import main as generate_main
from generator.schema import TABLES
from loader.load import LoadError, load_extracts

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EXTRACTS_DIR = DATA_DIR / "extracts"
WAREHOUSE = DATA_DIR / "warehouse.duckdb"

# dbt connects to the warehouse while parsing, before the first run creates it.
DATA_DIR.mkdir(exist_ok=True)

# Parse the dbt project on every load, so the manifest always matches the models
# and sources. (prepare_if_dev only does this under `dagster dev`.)
dbt_bin = Path(sys.executable).parent / "dbt"
subprocess.run([dbt_bin, "parse"], cwd=ROOT / "dbt", check=True)
dbt_project = DbtProject(project_dir=ROOT / "dbt", profiles_dir=ROOT / "dbt")


class GenerateConfig(dg.Config):
    """How many simulated business days to add to the extracts on each run."""

    days: int = 1


@dg.asset(
    group_name="sap",
    retry_policy=dg.RetryPolicy(max_retries=2, delay=5),
)
def sap_extracts(context: dg.AssetExecutionContext, config: GenerateConfig) -> None:
    code = generate_main(["--days", str(config.days), "--out", str(EXTRACTS_DIR)])
    if code != 0:
        raise dg.Failure(f"generate exited with code {code}")
    context.log.info(f"added {config.days} day(s) to {EXTRACTS_DIR}")


@dg.multi_asset(
    outs={
        f"raw_{table}": dg.AssetOut(key=dg.AssetKey(["raw", table]), group_name="sap")
        for table in TABLES
    },
    deps=[sap_extracts],
    retry_policy=dg.RetryPolicy(max_retries=2, delay=5),
)
def raw_tables(context: dg.AssetExecutionContext):
    """Load every extract into raw. One asset per raw table, which dbt sources point at."""
    try:
        result = load_extracts(EXTRACTS_DIR, WAREHOUSE)
    except LoadError as e:
        raise dg.Failure(str(e)) from e
    context.log.info(
        f"loaded {result.files_loaded} files ({result.rows_loaded} rows), "
        f"skipped {result.files_skipped}"
    )
    for table in TABLES:
        yield dg.MaterializeResult(asset_key=dg.AssetKey(["raw", table]))


@dbt_assets(manifest=dbt_project.manifest_path)
def sap_dbt_assets(context: dg.AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


daily_pipeline = dg.define_asset_job(
    "daily_pipeline",
    selection=dg.AssetSelection.all(),
)

daily_schedule = dg.ScheduleDefinition(
    name="daily_schedule",
    job=daily_pipeline,
    cron_schedule="0 6 * * *",
    description="Simulate one more business day, load it, and rebuild the dbt models.",
)

defs = dg.Definitions(
    assets=[sap_extracts, raw_tables, sap_dbt_assets],
    schedules=[daily_schedule],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
