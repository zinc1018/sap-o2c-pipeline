import dagster as dg

from generator.schema import TABLES
from orchestration.definitions import defs


def test_daily_job_covers_every_stage():
    job = defs.resolve_job_def("daily_pipeline")
    keys = {tuple(k.path) for k in job.asset_layer.executable_asset_keys}

    assert ("sap_extracts",) in keys
    assert all(("raw", table) in keys for table in TABLES)
    assert ("staging", "stg_sap__vbak") in keys
    assert ("marts", "fct_billing_items") in keys


def test_schedule_runs_once_a_day_at_six():
    schedule = defs.resolve_schedule_def("daily_schedule")
    assert schedule.cron_schedule == "0 6 * * *"
    assert isinstance(schedule, dg.ScheduleDefinition)
