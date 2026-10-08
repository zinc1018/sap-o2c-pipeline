from generator.schema import KEYS, TABLES


def test_v1_tables_present():
    assert {"KNA1", "MARA", "MAKT", "VBAK", "VBAP", "VBRK", "VBRP"} <= set(TABLES)


def test_v2_and_v3_tables_present():
    assert {"LIKP", "LIPS", "BSID", "BSAD"} <= set(TABLES)


def test_every_table_starts_with_client():
    assert all(cols[0] == "MANDT" for cols in TABLES.values())


def test_keys_are_columns_of_their_table():
    for table, key in KEYS.items():
        assert set(key) <= set(TABLES[table])


def test_change_date_columns():
    for table in ("VBAK", "VBAP", "VBRK", "VBRP"):
        assert "AEDAT" in TABLES[table]
    assert "LAEDA" in TABLES["MARA"]
    assert "AEDAT" not in TABLES["KNA1"]  # real KNA1 has no change date
