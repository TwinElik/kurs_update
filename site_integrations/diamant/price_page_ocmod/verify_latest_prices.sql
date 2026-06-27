SELECT
    id,
    source_price_id,
    kurs,
    price_583_from,
    price_583_to,
    price_585_from,
    price_585_to,
    price_750_from,
    price_750_to,
    price_850_from,
    price_850_to,
    price_875_from,
    price_875_to,
    price_916_from,
    price_916_to,
    price_999_from,
    price_999_to,
    created_at
FROM diamant_gold_prices
ORDER BY id DESC
LIMIT 1;
