from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP


PROBES = (375, 583, 585, 750, 850, 875, 916, 999)
HIDDEN_PROBES = (900,)

# Source: Zoloto.xlsx, 2026-07-17.
# Tillachi Bolla does not have a separate sheet in the new workbook, so it uses
# the exact same public price ranges as Diamant.
BRAND_FIXED_MAX_PRICES = {
    "skupka": {
        583: 1200000,
        585: 1000000,
        850: 1320000,
        875: 1375000,
        900: 1500000,
        916: 1420000,
        999: 1600000,
    },
    "diamant": {
        583: 1210000,
        585: 1000000,
        850: 1325000,
        875: 1380000,
        900: 1500000,
        916: 1425000,
        999: 1615000,
    },
    "tillachi": {
        583: 1210000,
        585: 1000000,
        850: 1325000,
        875: 1380000,
        900: 1500000,
        916: 1425000,
        999: 1615000,
    },
    "goldexpert": {
        583: 1220000,
        585: 1000000,
        850: 1330000,
        875: 1385000,
        900: 1500000,
        916: 1450000,
        999: 1590000,
    },
}

ROUNDUP_MAX_ADDITIONS = {
    "skupka": {375: 70000},
    "diamant": {375: 70000},
    "tillachi": {375: 70000},
    "goldexpert": {375: 70000},
}


def excel_round(value, digits=0):
    quant = Decimal("1").scaleb(-digits)
    return Decimal(value).quantize(quant, rounding=ROUND_HALF_UP)


def excel_ceiling(value, significance):
    value = Decimal(value)
    significance = Decimal(str(significance))
    return (value / significance).to_integral_value(rounding=ROUND_CEILING) * significance


def roundup_to_10000(value):
    return int(excel_ceiling(value, 10000))


def _start_price(probe, main_rate):
    rate = Decimal(str(main_rate))
    if probe == 585:
        return int((rate * Decimal(1000)).to_integral_value(rounding=ROUND_HALF_UP))
    base = (Decimal(probe) / Decimal(583) / Decimal(10)) * rate
    return int(excel_ceiling(base, Decimal("0.5")) * Decimal(10000))


def _max_price(probe, start_price, brand):
    if probe == 750:
        return start_price + 200000 if 1500000 - start_price < 200000 else 1500000
    fixed_prices = BRAND_FIXED_MAX_PRICES.get(brand, BRAND_FIXED_MAX_PRICES["diamant"])
    if probe in fixed_prices:
        return fixed_prices[probe]
    additions = ROUNDUP_MAX_ADDITIONS.get(brand, ROUNDUP_MAX_ADDITIONS["diamant"])
    addition = additions.get(probe, ROUNDUP_MAX_ADDITIONS["diamant"].get(probe, 0))
    return roundup_to_10000(start_price) + addition


def calculate_prices(main_rate, brand="diamant", include_hidden=False):
    rate = Decimal(str(main_rate))
    if rate <= 0:
        raise ValueError("main_rate must be positive")
    brand = str(brand or "diamant").lower()
    probes = PROBES + HIDDEN_PROBES if include_hidden else PROBES
    result = {}
    for probe in probes:
        start = _start_price(probe, rate)
        result[str(probe)] = (start, _max_price(probe, start, brand))
    return result


def generate_price_range(main_rate, brand="diamant"):
    return calculate_prices(main_rate, brand)


def format_price(value):
    return f"{int(value):,}".replace(",", ".")


def price_rows(main_rate, brand="diamant"):
    ranges = calculate_prices(main_rate, brand)
    return [
        (probe, f"{format_price(min_price)}-{format_price(max_price)} \u0441\u0443\u043c/\u0433\u0440")
        for probe, (min_price, max_price) in ranges.items()
    ]
