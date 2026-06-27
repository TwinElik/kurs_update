# Tillachi Bolla prices on skupkazolota.uz

The WordPress endpoint receives signed `brands.tillachi` prices and inserts new
rows into the MySQL 5.7 table `tillachi_gold_prices`.

## Upload

Create `api/` in the WordPress root of `skupkazolota.uz` and upload:

```text
site_integrations/tillachi/update-gold-price.php -> api/update-gold-price.php
site_integrations/tillachi/endpoint_token.example.php -> api/endpoint_token.php
```

Replace the example value with a unique random secret of at least 32 bytes.

## VPS `.env`

```env
TILLACHI_SYNC_ENABLED=1
TILLACHI_ENDPOINT_URL=https://skupkazolota.uz/api/update-gold-price.php
TILLACHI_ENDPOINT_TOKEN=THE_SAME_RANDOM_HMAC_SECRET_AS_ON_THE_TILLACHI_SITE
```

The endpoint creates `tillachi_gold_prices` automatically. Manual SQL is in
`create_tillachi_gold_prices.sql`.

## Test

```bash
python scripts/test_tillachi_endpoint.py
```

Expected:

```json
{"ok":true,"source_price_id":1234567890}
```
