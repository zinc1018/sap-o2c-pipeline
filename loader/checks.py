"""Checks every loader runs before loading a file."""

import csv
from pathlib import Path

from generator.schema import TABLES


class LoadError(Exception):
    """A file or folder could not be loaded; the message starts with its path."""


def read_header(path: Path, table: str) -> list[str]:
    """The file's column names. Fails if it isn't UTF-8 or doesn't match the table."""
    try:
        with open(path, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f), [])
            f.read()  # decode the whole file so a non-UTF-8 byte fails here, clearly
    except (UnicodeDecodeError, OSError) as e:
        raise LoadError(f"{path}: cannot read as UTF-8 text ({e})") from e
    columns = TABLES[table]
    missing, extra = set(columns) - set(header), set(header) - set(columns)
    if missing or extra:
        raise LoadError(f"{path}: missing columns {sorted(missing)}, unexpected {sorted(extra)}")
    return header
