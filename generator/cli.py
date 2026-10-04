"""`generate --days N`: write N more days of SAP extract CSVs."""

import argparse
import csv
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from generator.schema import TABLES
from generator.simulate import simulate


def _positive(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return n


def _complete_days(out: Path, start: date) -> int:
    """Consecutive days from `start` that have a file for every table."""
    n = 0
    while all(
        (out / t / f"{t}_{start + timedelta(days=n):%Y%m%d}.csv").exists() for t in TABLES
    ):
        n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate daily SAP extract CSVs.")
    parser.add_argument("--days", type=_positive, required=True, help="days to add")
    parser.add_argument("--out", type=Path, default=Path("data/extracts"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 1, 1))
    args = parser.parse_args(argv)

    # The folder remembers its seed and start; mixing two histories would corrupt it.
    settings = {"start": args.start.isoformat(), "seed": args.seed}
    manifest = args.out / "_generator.json"
    if manifest.exists():
        saved = json.loads(manifest.read_text())
        if saved != settings:
            print(
                f"error: {args.out} was generated with start {saved['start']} and seed "
                f"{saved['seed']}; use those values or a new --out folder",
                file=sys.stderr,
            )
            return 1
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(settings) + "\n")

    # Complete days are replayed, not rewritten, so history stays identical.
    # A day left partial by an interrupted run is written again in full.
    existing = _complete_days(args.out, args.start)
    written = []
    for i, (day, extracts) in enumerate(simulate(args.start, existing + args.days, args.seed)):
        if i < existing:
            continue
        for table, rows in extracts.items():
            folder = args.out / table
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{table}_{day:%Y%m%d}.csv"
            tmp = path.with_suffix(".tmp")  # renamed into place only once fully written
            with open(tmp, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, lineterminator="\n")
                writer.writerow(TABLES[table])
                writer.writerows(row.values() for row in rows)
            os.replace(tmp, path)
        written.append(day)

    print(f"wrote days {written[0]}..{written[-1]} to {args.out}")
    return 0
