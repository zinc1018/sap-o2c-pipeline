"""Day-by-day simulation of a small SAP order-to-cash system.

`simulate` replays every day from `start` with one seeded random generator, so the
same (start, seed) always yields the same history. Each day yields a delta extract:
the rows created or changed that day, for every table.
"""

import random
from collections.abc import Iterator
from datetime import date, timedelta

from generator.schema import TABLES

MANDT = "100"
INITIAL_DATE = "00000000"  # SAP's empty date

CUSTOMER_COUNT = 50
MATERIAL_COUNT = 30
CITIES = {
    "US": [("Peoria", "IL"), ("Pella", "IA"), ("Dallas", "TX"), ("Denver", "CO")],
    "CA": [("Toronto", "ON"), ("Calgary", "AB"), ("Regina", "SK")],
}
CURRENCY = {"US": "USD", "CA": "CAD"}
NAMES = ["Prairie", "Summit", "Riverbend", "Granite", "Northfield", "Ironwood", "Bluestem"]
SUFFIXES = ["Equipment", "Contracting", "Utilities", "Excavation", "Rentals"]
MATERIAL_GROUPS = ["TRENCHER", "DRILL", "VACUUM", "PARTS"]

Rows = dict[str, list[dict[str, str]]]


def _row(table: str, **values: str) -> dict[str, str]:
    return {col: values.get(col, "") for col in TABLES[table]}


def _money(value: float) -> str:
    return f"{value:.2f}"


def simulate(start: date, days: int, seed: int = 42) -> Iterator[tuple[date, Rows]]:
    rng = random.Random(seed)
    customers: dict[str, dict[str, str]] = {}  # KUNNR -> current KNA1 row
    prices: dict[str, float] = {}  # MATNR -> unit price
    orders: dict[str, dict] = {}  # VBELN -> {"header": VBAK row, "items": {POSNR: VBAP row}}
    next_order = 1

    for offset in range(days):
        day = start + timedelta(days=offset)
        today = day.strftime("%Y%m%d")
        out: Rows = {table: [] for table in TABLES}

        if offset == 0:
            for n in range(1, CUSTOMER_COUNT + 1):
                land = "US" if rng.random() < 0.8 else "CA"
                city, region = rng.choice(CITIES[land])
                name = (
                    'Smith, Jones & "Co"'
                    if n == 1
                    else f"{rng.choice(NAMES)} {rng.choice(SUFFIXES)}"
                )
                kunnr = f"{n:010d}"
                customers[kunnr] = _row(
                    "KNA1", MANDT=MANDT, KUNNR=kunnr, NAME1=name, ORT01=city,
                    REGIO=region, LAND1=land, ERDAT=today,
                )
                out["KNA1"].append(dict(customers[kunnr]))
            for n in range(1, MATERIAL_COUNT + 1):
                matnr = f"{n:018d}"
                group = rng.choice(MATERIAL_GROUPS)
                prices[matnr] = round(rng.uniform(10, 500), 2)
                out["MARA"].append(_row(
                    "MARA", MANDT=MANDT, MATNR=matnr, MTART="FERT", MATKL=group,
                    MEINS="EA", ERSDA=today, LAEDA=INITIAL_DATE,
                ))
                out["MAKT"].append(_row(
                    "MAKT", MANDT=MANDT, MATNR=matnr, SPRAS="E", MAKTX=f"{group.title()} {n}",
                ))

        for _ in range(rng.randint(5, 15)):
            vbeln = f"{next_order:010d}"
            next_order += 1
            kunnr = rng.choice(list(customers))
            waerk = CURRENCY[customers[kunnr]["LAND1"]]
            items = {}
            for i in range(1, rng.randint(1, 4) + 1):
                posnr = f"{i * 10:06d}"
                matnr = rng.choice(list(prices))
                qty = rng.randint(1, 20)
                items[posnr] = _row(
                    "VBAP", MANDT=MANDT, VBELN=vbeln, POSNR=posnr, MATNR=matnr,
                    KWMENG=str(qty), VRKME="EA", NETWR=_money(qty * prices[matnr]),
                    WAERK=waerk, ERDAT=today, AEDAT=INITIAL_DATE,
                )
            header = _row(
                "VBAK", MANDT=MANDT, VBELN=vbeln, AUART="OR", ERDAT=today, AUDAT=today,
                KUNNR=kunnr, WAERK=waerk, AEDAT=INITIAL_DATE,
                NETWR=_money(sum(float(i["NETWR"]) for i in items.values())),
            )
            orders[vbeln] = {"header": header, "items": items}
            out["VBAK"].append(dict(header))
            out["VBAP"].extend(dict(i) for i in items.values())

        yield day, out
