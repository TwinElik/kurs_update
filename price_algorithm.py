from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP


PROBES = (375, 583, 585, 750, 850, 875, 916, 999)
HIDDEN_PROBES = (900,)

BRAND_ADDITIONS = {
    "tillachi": {
        375: 40000,
        585: 190000,
        850: 190000,
        875: 190000,
        900: 190000,
        916: 190000,
        999: 140000,
    },
    "diamant": {
        375: 50000,
        585: 200000,
        850: 200000,
        875: 200000,
        900: 200000,
        916: 200000,
        999: 150000,
    },
    "skupka": {
        375: 60000,
        585: 210000,
        850: 210000,
        875: 210000,
        900: 210000,
        916: 210000,
        999: 160000,
    },
    "goldexpert": {
        375: 70000,
        585: 220000,
        850: 220000,
        875: 220000,
        900: 220000,
        916: 220000,
        999: 170000,
    },
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
    if probe in (583, 750):
        return start_price + 200000 if 1500000 - start_price < 200000 else 1500000
    additions = BRAND_ADDITIONS.get(brand, BRAND_ADDITIONS["diamant"])
    addition = additions.get(probe, BRAND_ADDITIONS["diamant"].get(probe, 200000))
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
