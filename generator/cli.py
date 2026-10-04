"""`generate --days N`: write N more days of SAP extract CSVs."""

import argparse
import csv
from datetime import date
from pathlib import Path

from generator.schema import TABLES
from generator.simulate import simulate


def _positive(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate daily SAP extract CSVs.")
    parser.add_argument("--days", type=_positive, required=True, help="days to add")
    parser.add_argument("--out", type=Path, default=Path("data/extracts"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 1, 1))
    args = parser.parse_args(argv)

    # Days already on disk are replayed (not rewritten) so history stays identical.
    existing = len(list((args.out / "KNA1").glob("KNA1_*.csv")))
    written = []
    for i, (day, extracts) in enumerate(simulate(args.start, existing + args.days, args.seed)):
        if i < existing:
            continue
        for table, rows in extracts.items():
            folder = args.out / table
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{table}_{day:%Y%m%d}.csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, lineterminator="\n")
                writer.writerow(TABLES[table])
                writer.writerows(row.values() for row in rows)
        written.append(day)

    print(f"wrote days {written[0]}..{written[-1]} to {args.out}")
    return 0
