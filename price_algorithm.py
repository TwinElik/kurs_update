import math


PROBAS = (375, 583, 585, 750, 850, 875, 916, 999)
# Existing bot modules import PROBES. Keep this alias for compatibility.
PROBES = PROBAS

BRAND_EXTRA = {
    "skupka": 70_000,
    "diamant": 75_000,
    "tillachi_bolla": 75_000,
    "goldexpert": 80_000,
}

# The deployed Tillachi endpoint still uses this legacy identifier.
BRAND_ALIASES = {"tillachi": "tillachi_bolla"}


def calculate_start_price(proba: int, main_rate: int) -> int:
    if proba == 585:
        return main_rate * 1000

    raw = (proba / 583 / 10) * main_rate
    return int(math.ceil(raw * 2) / 2 * 10000)


def calculate_prices(main_rate: int, brand: str) -> dict:
    brand = BRAND_ALIASES.get(str(brand).lower(), str(brand).lower())
    if brand not in BRAND_EXTRA:
        raise ValueError(f"Неизвестная компания: {brand}")

    main_rate = int(main_rate)
    if main_rate <= 0:
        raise ValueError("main_rate must be positive")

    extra = BRAND_EXTRA[brand]
    prices = {}

    for proba in PROBAS:
        from_price = calculate_start_price(proba, main_rate)

        if proba == 583:
            to_price = from_price + extra + 260_000
        elif proba == 585:
            to_price = from_price + 180_000
        elif proba == 750:
            to_price = 1_500_000
        else:
            to_price = from_price + extra

        prices[proba] = {"from": int(from_price), "to": int(to_price)}

    return prices


def generate_price_range(main_rate: int, brand: str = "diamant") -> dict:
    return calculate_prices(main_rate, brand)


def format_price(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def price_rows(main_rate: int, brand: str = "diamant") -> list:
    ranges = calculate_prices(main_rate, brand)
    return [
        (
            str(proba),
            f"{format_price(price_range['from'])}-{format_price(price_range['to'])} сум/гр",
        )
        for proba, price_range in ranges.items()
    ]
