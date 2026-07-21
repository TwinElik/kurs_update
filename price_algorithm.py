from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP


PROBES = (375, 583, 585, 750, 850, 875, 916, 999)
HIDDEN_PROBES = (900,)

# Source: Zoloto.xlsx, main rate 870.
#
# The workbook shows a price range, not a fixed "to" price for every future
# main rate. Store the verified spread ("to" minus "from") per brand/probe so
# both ends of the range move together when the operator enters a new rate.
# Tillachi Bolla does not have a separate sheet and follows Diamant.
BRAND_MAX_ADDITIONS = {
    "skupka": {
        375: 70000,
        583: 330000,
        585: 180000,
        750: 380000,
        850: 75000,
        875: 75000,
        900: 155000,
        916: 90000,
        999: 105000,
    },
    "diamant": {
        375: 70000,
        583: 340000,
        585: 180000,
        750: 380000,
        850: 75000,
        875: 85000,
        900: 155000,
        916: 60000,
        999: 120000,
    },
    "tillachi": {
        375: 70000,
        583: 340000,
        585: 180000,
        750: 380000,
        850: 75000,
        875: 85000,
        900: 155000,
        916: 60000,
        999: 120000,
    },
    "goldexpert": {
        375: 70000,
        583: 350000,
        585: 180000,
        750: 380000,
        850: 70000,
        875: 90000,
        900: 155000,
        916: 80000,
        999: 95000,
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
    additions = BRAND_MAX_ADDITIONS.get(brand, BRAND_MAX_ADDITIONS["diamant"])
    addition = additions.get(probe, BRAND_MAX_ADDITIONS["diamant"].get(probe, 0))
    return start_price + addition


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
