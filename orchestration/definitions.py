"""Dagster definitions: generate → load → dbt build, on a daily schedule.

Run the UI with `uv run dagster dev -m orchestration.definitions`.
"""

import os
import subprocess
import sys
from pathlib import Path

import dagster as dg
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets
from pydantic import Field

from generator.cli import main as generate_main
from generator.schema import TABLES
from loader.checks import LoadError
from loader.load import load_extracts
from loader.snowflake import connect_from_env, load_extracts_snowflake
from orchestration.alerts import alert_settings, build_alert, send_alert

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EXTRACTS_DIR = DATA_DIR / "extracts"
WAREHOUSE = DATA_DIR / "warehouse.duckdb"

# SAP_TARGET picks the warehouse: "duckdb" (default) or "snowflake" (needs SNOWFLAKE_* env vars).
# Each maps to the dbt target of the same role.
TARGETS = {"duckdb": "dev", "snowflake": "snowflake"}
SAP_TARGET = os.environ.get("SAP_TARGET", "duckdb")
if SAP_TARGET not in TARGETS:
    raise ValueError(f"SAP_TARGET must be one of {sorted(TARGETS)}, got {SAP_TARGET!r}")

# dbt connects to the warehouse while parsing, before the first run creates it.
DATA_DIR.mkdir(exist_ok=True)

# Parse the dbt project on every load, so the manifest always matches the models
# and sources. (prepare_if_dev only does this under `dagster dev`.)
dbt_bin = Path(sys.executable).parent / "dbt"
subprocess.run([dbt_bin, "parse"], cwd=ROOT / "dbt", check=True)
dbt_project = DbtProject(project_dir=ROOT / "dbt", profiles_dir=ROOT / "dbt")


class GenerateConfig(dg.Config):
    """How many simulated business days to add to the extracts on each run."""

    days: int = Field(default=1, ge=1)


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
        if SAP_TARGET == "snowflake":
            connection = connect_from_env()
            try:
                result = load_extracts_snowflake(EXTRACTS_DIR, connection)
            finally:
                connection.close()
        else:
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
    yield from dbt.cli(["build", "--target", TARGETS[SAP_TARGET]], context=context).stream()


daily_pipeline = dg.define_asset_job(
    "daily_pipeline",
    selection=dg.AssetSelection.all(),
)

daily_schedule = dg.ScheduleDefinition(
    name="daily_schedule",
    job=daily_pipeline,
    cron_schedule="0 6 * * *",
    description="Simulate one more business day, load it, and rebuild the dbt models.",
    default_status=dg.DefaultScheduleStatus.RUNNING,
)

def _root_cause(error) -> str:
    """The original exception message. Retries wrap it in "Exceeded max_retries"."""
    return (error.cause or error).message.strip()


@dg.run_failure_sensor(
    monitored_jobs=[daily_pipeline],
    default_status=dg.DefaultSensorStatus.RUNNING,
)
def pipeline_failure_alert(context: dg.RunFailureSensorContext):
    """Email the failed steps and error whenever a daily run fails."""
    step_failures = [
        e for e in context.get_step_failure_events() if e.step_key and e.event_specific_data.error
    ]
    settings = alert_settings()
    if settings is None:
        context.log.warning(f"run {context.dagster_run.run_id} failed; alerts not configured")
        return

    failed_steps = [e.step_key for e in step_failures]
    error = "\n\n".join(
        f"{e.step_key}: {_root_cause(e.event_specific_data.error)}" for e in step_failures
    ) or context.failure_event.message or "no error message"
    message = build_alert(
        job_name=context.dagster_run.job_name,
        run_id=context.dagster_run.run_id,
        failed_steps=failed_steps,
        error=error,
        sender=settings["sender"],
        recipient=settings["recipient"],
    )
    send_alert(message, settings)
    context.log.info(f"sent failure alert to {settings['recipient']}")


defs = dg.Definitions(
    assets=[sap_extracts, raw_tables, sap_dbt_assets],
    schedules=[daily_schedule],
    sensors=[pipeline_failure_alert],
    # Use the dbt installed alongside this Python, so it works without an activated venv.
    resources={
        "dbt": DbtCliResource(
            project_dir=dbt_project,
            dbt_executable=str(Path(sys.executable).parent / "dbt"),
        )
    },
)
