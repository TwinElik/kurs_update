# Skupka-zolota.uz WordPress endpoint

This endpoint receives signed `brands.skupka` prices and inserts a new row into
the MySQL 5.7 table `skupka_gold_prices`.

## Upload

Create this folder in the WordPress site root:

```text
api/
```

Upload:

```text
site_integrations/skupka/update-gold-price.php -> api/update-gold-price.php
site_integrations/skupka/endpoint_token.example.php -> api/endpoint_token.php
```

Replace the example secret in `endpoint_token.php` with a random secret of at
least 32 bytes. Use a different secret from Diamant.

The endpoint expects WordPress at `../wp-load.php`. Its public URL is:

```text
https://skupka-zolota.uz/api/update-gold-price.php
```

## VPS `.env`

```env
SKUPKA_SYNC_ENABLED=1
SKUPKA_ENDPOINT_URL=https://skupka-zolota.uz/api/update-gold-price.php
SKUPKA_ENDPOINT_TOKEN=THE_SAME_RANDOM_HMAC_SECRET_AS_ON_THE_SKUPKA_SITE
```

## Database

The endpoint creates `skupka_gold_prices` automatically. It can also be created
manually through phpMyAdmin with `create_skupka_gold_prices.sql`.

## Test

Run from the project root on the VPS:

```bash
python scripts/test_skupka_endpoint.py
```

Expected:

```json
{"ok":true,"source_price_id":1234567890}
```
