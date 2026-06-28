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
site_integrations/skupka/gold-prices.js -> api/gold-prices.js
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
{"ok":true,"source_price_id":1234567890,"public_json_updated":true}
```

After a successful synchronization the endpoint atomically updates:

```text
https://skupka-zolota.uz/api/current-gold-prices.json
```

## Elementor

Use an Elementor HTML widget. Price markers should not contain quotes, because
the WordPress text editor can replace straight quotes with typographic ones:

```html
<div data-gold-prices-root>
  Narxi: [gold_price field=proba_999_begin] - [gold_price field=proba_999_end] so'm
</div>

<script src="https://skupka-zolota.uz/api/gold-prices.js?v=1"></script>
```

Add the script only once per page. The same JSON can be fetched by the online
calculator from `/api/current-gold-prices.json`.
