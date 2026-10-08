"""`pipeline`: run the whole pipeline once, headless, without the Dagster UI.

Example: `uv run pipeline --days 30`
"""

import argparse

from orchestration.definitions import defs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run generate → load → dbt build once.")
    parser.add_argument("--days", type=int, default=30, help="simulated days to add")
    args = parser.parse_args(argv)
    if args.days < 1:
        parser.error("--days must be at least 1")

    result = defs.resolve_job_def("daily_pipeline").execute_in_process(
        run_config={
            "ops": {"sap_extracts": {"config": {"days": args.days}}},
        }
    )
    return 0 if result.success else 1
