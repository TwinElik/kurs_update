# Diamant site endpoint

This folder contains the Diamant OpenCart endpoint for gold price updates.

## Files

```text
update-gold-price.php
endpoint_token.php
create_diamant_gold_prices.sql
```

## 1. Upload files

Create folder:

```text
/var/www/u0861209/data/www/diamant.uz/api/
```

Upload:

```text
update-gold-price.php
endpoint_token.php
```

Target paths:

```text
/var/www/u0861209/data/www/diamant.uz/api/update-gold-price.php
/var/www/u0861209/data/www/diamant.uz/api/endpoint_token.php
```

The endpoint reads OpenCart config from:

```text
/var/www/u0861209/data/www/diamant.uz/config.php
```

## 2. Token

The endpoint token is stored in:

```text
endpoint_token.php
```

Use the same token on the VPS:

```env
DIAMANT_SYNC_ENABLED=1
DIAMANT_ENDPOINT_URL=https://diamant.uz/api/update-gold-price.php
DIAMANT_ENDPOINT_TOKEN=mUaGcwNqfXcZz0p8xsugs3VM7g2ww5K2p6rCRy6orcU
```

## 3. Create MySQL 5.7 table

Run:

```text
create_diamant_gold_prices.sql
```

The SQL avoids column names starting with digits and does not use `ENGINE=...`.

## 4. Test endpoint

```bash
curl -X POST "https://diamant.uz/api/update-gold-price.php" \
  -H "Content-Type: application/json" \
  -H "X-Gold-Price-Token: mUaGcwNqfXcZz0p8xsugs3VM7g2ww5K2p6rCRy6orcU" \
  -d '{"event":"gold_price_updated","generation_id":999999,"kurs":890000,"created_at":"2026-06-26 12:00:00","brands":{"diamant":{"375_from":575000,"375_to":630000,"583_from":890000,"583_to":1500000,"585_from":890000,"585_to":1090000,"750_from":1145000,"750_to":1500000,"850_from":1300000,"850_to":1500000,"875_from":1340000,"875_to":1540000,"916_from":1400000,"916_to":1600000,"999_from":1530000,"999_to":1680000}}}'
```

Expected:

```json
{"ok":true,"source_price_id":999999}
```

Check row:

```sql
SELECT id, source_price_id, kurs, price_583_from, price_583_to, price_585_from, price_585_to, created_at
FROM diamant_gold_prices
ORDER BY id DESC
LIMIT 1;
```
