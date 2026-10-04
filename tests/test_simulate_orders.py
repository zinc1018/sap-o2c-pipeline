from datetime import date

from generator.schema import TABLES
from generator.simulate import simulate

START = date(2026, 1, 1)


def days(n, seed=42):
    return list(simulate(START, n, seed))


def test_same_seed_same_output():
    assert days(5) == days(5)


def test_different_seed_different_output():
    assert days(2, seed=1) != days(2, seed=2)


def test_every_table_every_day_with_exact_columns():
    for _, extracts in days(3):
        assert set(extracts) == set(TABLES)
        for table, rows in extracts.items():
            assert all(list(r) == list(TABLES[table]) for r in rows)


def test_master_data_on_day_one():
    _, d1 = days(1)[0]
    assert len({r["KUNNR"] for r in d1["KNA1"]}) == 50
    assert len({r["MATNR"] for r in d1["MARA"]}) == 30
    assert len({r["MATNR"] for r in d1["MAKT"]}) == 30
    assert all(len(r["KUNNR"]) == 10 for r in d1["KNA1"])
    assert all(len(r["MATNR"]) == 18 for r in d1["MARA"])
    assert any("," in r["NAME1"] and '"' in r["NAME1"] for r in d1["KNA1"])


def test_orders_link_and_sum():
    _, d1 = days(1)[0]
    customers = {r["KUNNR"]: r for r in d1["KNA1"]}
    headers = {r["VBELN"]: r for r in d1["VBAK"]}
    items = {(r["VBELN"], r["POSNR"]): r for r in d1["VBAP"]}
    assert 5 <= len(headers) <= 15
    assert min(headers) == "0000000001"
    for vbeln, h in headers.items():
        own = [i for (v, _), i in items.items() if v == vbeln]
        assert 1 <= len(own) <= 4
        assert sorted(i["POSNR"] for i in own)[0] == "000010"
        assert h["KUNNR"] in customers
        assert h["WAERK"] == ("USD" if customers[h["KUNNR"]]["LAND1"] == "US" else "CAD")
        assert f"{sum(float(i['NETWR']) for i in own):.2f}" == h["NETWR"]
        assert h["AEDAT"] == "00000000"
        assert all(i["ABGRU"] == "" and i["WAERK"] == h["WAERK"] for i in own)
