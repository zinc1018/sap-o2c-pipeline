"""SAP extract tables: column order and business keys, shared by generator and loader."""

TABLES: dict[str, tuple[str, ...]] = {
    # Customer master
    "KNA1": ("MANDT", "KUNNR", "NAME1", "ORT01", "REGIO", "LAND1", "ERDAT"),
    # Material master and descriptions
    "MARA": ("MANDT", "MATNR", "MTART", "MATKL", "MEINS", "ERSDA", "LAEDA"),
    "MAKT": ("MANDT", "MATNR", "SPRAS", "MAKTX"),
    # Sales order header / item (ABGRU = reason for rejection, i.e. cancelled item)
    "VBAK": ("MANDT", "VBELN", "AUART", "ERDAT", "AUDAT", "KUNNR", "WAERK", "NETWR", "AEDAT"),
    "VBAP": (
        "MANDT", "VBELN", "POSNR", "MATNR", "KWMENG", "VRKME",
        "NETWR", "WAERK", "ABGRU", "ERDAT", "AEDAT",
    ),
    # Billing header / item (FKSTO = cancelled; AUBEL/AUPOS = sales order item billed)
    "VBRK": (
        "MANDT", "VBELN", "FKART", "FKDAT", "KUNRG", "WAERK", "NETWR", "FKSTO", "ERDAT", "AEDAT",
    ),
    "VBRP": (
        "MANDT", "VBELN", "POSNR", "AUBEL", "AUPOS", "MATNR", "FKIMG",
        "VRKME", "NETWR", "ERDAT", "AEDAT",
    ),
    # v2: delivery header / item (LFART = delivery type, VGBEL/VGPOS = sales order item shipped)
    "LIKP": ("MANDT", "VBELN", "LFART", "ERDAT", "LFDAT", "KUNNR", "AEDAT"),
    "LIPS": (
        "MANDT", "VBELN", "POSNR", "VGBEL", "VGPOS", "MATNR",
        "LFIMG", "VRKME", "ERDAT", "AEDAT",
    ),
    # v3: open and cleared customer receivables (accounting document items).
    # BSID holds items when posted; BSAD holds them once cleared (AUGDT/AUGBL).
    "BSID": (
        "MANDT", "BUKRS", "BELNR", "GJAHR", "BUZEI", "KUNNR", "BLART", "BUDAT",
        "FAEDT", "ZFBDT", "ZTERM", "WRBTR", "WAERS", "ZUONR",
    ),
    "BSAD": (
        "MANDT", "BUKRS", "BELNR", "GJAHR", "BUZEI", "KUNNR", "BLART", "BUDAT",
        "FAEDT", "ZFBDT", "ZTERM", "WRBTR", "WAERS", "ZUONR", "AUGDT", "AUGBL",
    ),
}

KEYS: dict[str, tuple[str, ...]] = {
    "KNA1": ("KUNNR",),
    "MARA": ("MATNR",),
    "MAKT": ("MATNR", "SPRAS"),
    "VBAK": ("VBELN",),
    "VBAP": ("VBELN", "POSNR"),
    "VBRK": ("VBELN",),
    "VBRP": ("VBELN", "POSNR"),
    "LIKP": ("VBELN",),
    "LIPS": ("VBELN", "POSNR"),
    "BSID": ("BUKRS", "BELNR", "GJAHR", "BUZEI"),
    "BSAD": ("BUKRS", "BELNR", "GJAHR", "BUZEI"),
}
