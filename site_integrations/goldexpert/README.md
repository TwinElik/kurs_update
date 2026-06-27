# Goldexpert.uz WordPress endpoint

The endpoint receives signed `brands.goldexpert` prices and inserts new rows
into the MySQL 5.7 table `goldexpert_gold_prices`.

## Upload

Create `api/` in the WordPress site root and upload:

```text
site_integrations/goldexpert/update-gold-price.php -> api/update-gold-price.php
site_integrations/goldexpert/endpoint_token.example.php -> api/endpoint_token.php
```

Replace the example secret in `endpoint_token.php` with a unique random secret
of at least 32 bytes. Do not reuse the Diamant or Skupka secret.

## VPS `.env`

```env
GOLDEXPERT_SYNC_ENABLED=1
GOLDEXPERT_ENDPOINT_URL=https://goldexpert.uz/api/update-gold-price.php
GOLDEXPERT_ENDPOINT_TOKEN=THE_SAME_RANDOM_HMAC_SECRET_AS_ON_GOLDEXPERT
```

The endpoint loads WordPress from `../wp-load.php` and creates the table
automatically. Manual SQL is available in `create_goldexpert_gold_prices.sql`.

## Test

```bash
python scripts/test_goldexpert_endpoint.py
```

Expected:

```json
{"ok":true,"source_price_id":1234567890}
```
