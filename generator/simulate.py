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

CHANGE_RATE = 0.10  # per open order per day: one item's quantity changes
REJECT_RATE = 0.03  # per open order per day: one item is rejected (cancelled)
BILL_RATE = 0.40  # per open order at least 2 days old per day
CANCEL_RATE = 0.03  # per invoice: cancelled 1-5 days after billing
CUSTOMER_CHANGE_RATE = 0.02  # per customer per day: moves city
DUPLICATE_RATE = 0.01  # per emitted row: written twice
ORPHAN_RATE = 0.005  # per billing item: references an order that never existed
FIRST_INVOICE = 90_000_001

Rows = dict[str, list[dict[str, str]]]


def _row(table: str, **values: str) -> dict[str, str]:
    return {col: values.get(col, "") for col in TABLES[table]}


def _money(value: float) -> str:
    return f"{value:.2f}"


def simulate(start: date, days: int, seed: int = 42) -> Iterator[tuple[date, Rows]]:
    rng = random.Random(seed)
    customers: dict[str, dict[str, str]] = {}  # KUNNR -> current KNA1 row
    prices: dict[str, float] = {}  # MATNR -> unit price
    # VBELN -> {"header": VBAK row, "items": {POSNR: VBAP row}, "created": date, "billed": bool}
    orders: dict[str, dict] = {}
    invoices: dict[str, dict[str, str]] = {}  # VBELN -> current VBRK row
    cancel_on: dict[str, date] = {}  # VBELN -> day the invoice gets cancelled
    next_order, next_invoice = 1, FIRST_INVOICE

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
            orders[vbeln] = {"header": header, "items": items, "created": day, "billed": False}
            out["VBAK"].append(dict(header))
            out["VBAP"].extend(dict(i) for i in items.values())

        # Changes happen only to records created on an earlier day.
        for order in orders.values():
            header, items = order["header"], order["items"]
            if order["billed"] or order["created"] == day:
                continue
            changed = False
            open_items = [i for i in items.values() if not i["ABGRU"]]
            if open_items and rng.random() < CHANGE_RATE:
                item = rng.choice(open_items)
                qty = rng.randint(1, 20)
                item["KWMENG"] = str(qty)
                item["NETWR"] = _money(qty * prices[item["MATNR"]])
                changed = True
            if open_items and rng.random() < REJECT_RATE:
                rng.choice(open_items)["ABGRU"] = "02"
                changed = True
            if changed:
                header["NETWR"] = _money(
                    sum(float(i["NETWR"]) for i in items.values() if not i["ABGRU"])
                )
                header["AEDAT"] = today
                for item in items.values():
                    item["AEDAT"] = today
                out["VBAK"].append(dict(header))
                out["VBAP"].extend(dict(i) for i in items.values())

        for customer in customers.values():
            if customer["ERDAT"] != today and rng.random() < CUSTOMER_CHANGE_RATE:
                options = [c for c in CITIES[customer["LAND1"]] if c[0] != customer["ORT01"]]
                customer["ORT01"], customer["REGIO"] = rng.choice(options)
                out["KNA1"].append(dict(customer))

        for vbeln, order in orders.items():
            billable = [i for i in order["items"].values() if not i["ABGRU"]]
            if order["billed"] or not billable or (day - order["created"]).days < 2:
                continue
            if rng.random() >= BILL_RATE:
                continue
            order["billed"] = True
            invoice = f"{next_invoice:010d}"
            next_invoice += 1
            header = order["header"]
            for n, item in enumerate(billable, start=1):
                aubel = vbeln
                if rng.random() < ORPHAN_RATE:
                    aubel = f"{80_000_000 + rng.randint(1, 999_999):010d}"
                out["VBRP"].append(_row(
                    "VBRP", MANDT=MANDT, VBELN=invoice, POSNR=f"{n * 10:06d}", AUBEL=aubel,
                    AUPOS=item["POSNR"], MATNR=item["MATNR"], FKIMG=item["KWMENG"],
                    VRKME=item["VRKME"], NETWR=item["NETWR"], ERDAT=today, AEDAT=INITIAL_DATE,
                ))
            invoices[invoice] = _row(
                "VBRK", MANDT=MANDT, VBELN=invoice, FKART="F2", FKDAT=today,
                KUNRG=header["KUNNR"], WAERK=header["WAERK"], ERDAT=today, AEDAT=INITIAL_DATE,
                NETWR=_money(sum(float(i["NETWR"]) for i in billable)),
            )
            out["VBRK"].append(dict(invoices[invoice]))
            if rng.random() < CANCEL_RATE:
                cancel_on[invoice] = day + timedelta(days=rng.randint(1, 5))

        for vbeln, when in cancel_on.items():
            if when == day:
                invoice = invoices[vbeln]
                invoice["FKSTO"] = "X"
                invoice["AEDAT"] = today
                out["VBRK"].append(dict(invoice))

        for table, table_rows in out.items():
            out[table] = [
                r for row in table_rows
                for r in ([row, dict(row)] if rng.random() < DUPLICATE_RATE else [row])
            ]

        yield day, out
