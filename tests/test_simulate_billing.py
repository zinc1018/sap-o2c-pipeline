from datetime import date

from generator.simulate import simulate

ALL = list(simulate(date(2026, 1, 1), 60, 42))


def rows(table):
    return [r for _, extracts in ALL for r in extracts[table]]


def test_billing_starts_no_earlier_than_day_three():
    assert all(not extracts["VBRK"] for _, extracts in ALL[:2])
    assert rows("VBRK")


def test_billing_items_match_ordered_qty_and_skip_rejected():
    latest = {(r["VBELN"], r["POSNR"]): r for r in rows("VBAP")}
    for b in rows("VBRP"):
        item = latest.get((b["AUBEL"], b["AUPOS"]))
        if item:  # orphans have no order item
            assert item["ABGRU"] == "" and b["FKIMG"] == item["KWMENG"]


def test_invoice_numbers_and_totals():
    items = {}
    for b in rows("VBRP"):
        items.setdefault(b["VBELN"], {})[b["POSNR"]] = b
    for h in rows("VBRK"):
        assert h["VBELN"] >= "0090000001" and h["FKART"] == "F2"
        total = sum(float(i["NETWR"]) for i in items[h["VBELN"]].values())
        assert f"{total:.2f}" == h["NETWR"]


def test_changes_and_cancellations_reemit_with_aedat():
    changed = [r for r in rows("VBAK") if r["AEDAT"] != "00000000"]
    cancelled = [r for r in rows("VBRK") if r["FKSTO"] == "X"]
    assert changed and cancelled
    assert all(r["AEDAT"] != "00000000" for r in cancelled)
    assert any(r["ABGRU"] == "02" for r in rows("VBAP"))


def test_no_same_day_changes():
    for _, extracts in ALL:
        for r in extracts["VBAK"] + extracts["VBAP"]:
            assert r["AEDAT"] == "00000000" or r["AEDAT"] > r["ERDAT"]


def test_customer_changes_reemit_kna1():
    cities = {}
    for r in rows("KNA1"):
        cities.setdefault(r["KUNNR"], set()).add(r["ORT01"])
    assert any(len(c) > 1 for c in cities.values())


def test_deliberate_issues_present():
    order_ids = {r["VBELN"] for r in rows("VBAK")}
    assert any(b["AUBEL"] not in order_ids for b in rows("VBRP"))
    assert any(
        len(e[t]) != len({tuple(r.values()) for r in e[t]}) for _, e in ALL for t in e
    )


def test_cancelled_share_is_small():
    invoices = {r["VBELN"] for r in rows("VBRK")}
    cancelled = {r["VBELN"] for r in rows("VBRK") if r["FKSTO"] == "X"}
    assert 0 < len(cancelled) / len(invoices) < 0.08
