import time

from price_algorithm import PROBES, calculate_prices


def _flat_prices_for_brand(main_rate, brand):
    prices = calculate_prices(main_rate, brand)
    result = {}
    for sample in PROBES:
        price_from, price_to = prices[str(sample)]
        result[f"{sample}_from"] = price_from
        result[f"{sample}_to"] = price_to
    return result


def build_gold_price_event(main_rate, generation):
    return {
        "event": "gold_price_updated",
        "generation_id": generation["id"],
        "price": float(main_rate),
        "kurs": int(float(main_rate) * 1000),
        "timestamp": int(time.time()),
        "created_at": generation["created_at"],
        "brands": {
            brand: _flat_prices_for_brand(main_rate, brand)
            for brand in ("diamant", "tillachi", "goldexpert", "skupka")
        },
    }
