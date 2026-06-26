SITES = [
    {
        "brand": "diamant",
        "source_table": "diamant_gold_prices",
        "target_site": "diamant.uz",
        "target_table": "diamant_gold_prices",
        "db_env_prefix": "DIAMANT_SITE_DB",
    },
    {
        "brand": "tillachi",
        "source_table": "tillachi_gold_prices",
        "target_site": "tillachi",
        "target_table": "tillachi_gold_prices",
        "db_env_prefix": "TILLACHI_SITE_DB",
    },
    {
        "brand": "goldexpert",
        "source_table": "goldexpert_gold_prices",
        "target_site": "goldexpert.uz",
        "target_table": "goldexpert_gold_prices",
        "db_env_prefix": "GOLDEXPERT_SITE_DB",
    },
    {
        "brand": "skupka",
        "source_table": "skupka_gold_prices",
        "target_site": "skupka-zolota.uz",
        "target_table": "skupka_gold_prices",
        "db_env_prefix": "SKUPKA_SITE_DB",
    },
]


SITE_BY_BRAND = {site["brand"]: site for site in SITES}

