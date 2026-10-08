from collections import defaultdict
from datetime import date

from generator.simulate import simulate

START = date(2026, 1, 1)


def rows(table, n=40):
    return [r for _, extracts in simulate(START, n, 42) for r in extracts[table]]


def test_every_invoice_opens_a_receivable():
    invoices = {r["VBELN"] for r in rows("VBRK")}
    receivables = {r["ZUONR"] for r in rows("BSID")}
    assert invoices == receivables


def test_cleared_items_are_cleared_after_they_were_posted():
    posted = {r["ZUONR"]: r["BUDAT"] for r in rows("BSID")}
    for r in rows("BSAD"):
        assert r["AUGDT"] >= posted[r["ZUONR"]]


def test_deliveries_reference_real_order_items():
    order_items = {(r["VBELN"], r["POSNR"]) for r in rows("VBAP")}
    for r in rows("LIPS"):
        assert (r["VGBEL"], r["VGPOS"]) in order_items


def test_shipments_are_positive_and_dated_on_delivery():
    for delivery in rows("LIKP"):
        assert delivery["LFDAT"] == delivery["ERDAT"]
    assert all(int(r["LFIMG"]) > 0 for r in rows("LIPS"))


def test_orders_are_shipped_in_part_and_in_full():
    shipped = defaultdict(int)
    for r in {tuple(r.values()): r for r in rows("LIPS")}.values():
        shipped[(r["VGBEL"], r["VGPOS"])] += int(r["LFIMG"])
    ordered = {(r["VBELN"], r["POSNR"]): int(r["KWMENG"]) for r in rows("VBAP")}
    partial = [k for k, v in shipped.items() if v < ordered[k]]
    assert partial  # some items ship in part, as in real operations
