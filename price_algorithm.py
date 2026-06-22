from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP


PROBES = (583, 585, 750, 850, 875, 916, 999)


def excel_round(value, digits=0):
    quant = Decimal("1").scaleb(-digits)
    return Decimal(value).quantize(quant, rounding=ROUND_HALF_UP)


def excel_ceiling(value, significance):
    value = Decimal(value)
    significance = Decimal(str(significance))
    return (value / significance).to_integral_value(rounding=ROUND_CEILING) * significance


def _start_price(probe, main_rate):
    rate = Decimal(str(main_rate))
    if probe == 585:
        coefficient = excel_round(Decimal(585) / Decimal(583), 2)
        return int((coefficient * rate * Decimal(1000)).to_integral_value(rounding=ROUND_HALF_UP))
    base = (Decimal(probe) / Decimal(583) / Decimal(10)) * rate
    return int(excel_ceiling(base, Decimal("0.5")) * Decimal(10000))


def _max_price(probe, start_price):
    if probe in (583, 750):
        return start_price + 200000 if 1500000 - start_price < 200000 else 1500000
    if probe == 999:
        return start_price + 150000
    return start_price + 200000


def generate_price_range(main_rate):
    rate = Decimal(str(main_rate))
    if rate <= 0:
        raise ValueError("main_rate must be positive")
    result = {}
    for probe in PROBES:
        start = _start_price(probe, rate)
        result[str(probe)] = (start, _max_price(probe, start))
    return result


def format_price(value):
    return f"{int(value):,}".replace(",", ".")


def price_rows(main_rate):
    ranges = generate_price_range(main_rate)
    return [
        (probe, f"{format_price(min_price)}-{format_price(max_price)} \u0441\u0443\u043c/\u0433\u0440")
        for probe, (min_price, max_price) in ranges.items()
    ]
