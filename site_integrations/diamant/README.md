# Diamant site sync

This folder contains two sync options for the Diamant OpenCart site.

## Recommended for REG.ru hosting: HTTP endpoint

Use this if the hosting does not provide Supervisor/systemd access.

Files:

```text
update-gold-price.php
create_diamant_gold_prices.sql
```

### 1. Create folder on site

Create this folder on the hosting:

```text
/var/www/u0861209/data/www/diamant.uz/api/
```

Upload:

```text
update-gold-price.php
```

Target path:

```text
/var/www/u0861209/data/www/diamant.uz/api/update-gold-price.php
```

The script automatically reads OpenCart config from:

```text
/var/www/u0861209/data/www/diamant.uz/config.php
```

### 2. Set secret token

Open `update-gold-price.php` and change:

```php
$secret = 'CHANGE_ME_SECRET_TOKEN';
```

Use the same value on the VPS in `.env`:

```env
ENABLE_DIAMANT_ENDPOINT_SYNC=1
DIAMANT_ENDPOINT_URL=https://diamant.uz/api/update-gold-price.php
DIAMANT_ENDPOINT_TOKEN=CHANGE_ME_SECRET_TOKEN
```

### 3. Create MySQL 5.7 table

Run SQL from:

```text
create_diamant_gold_prices.sql
```

This SQL intentionally does not end with `ENGINE=...`, because some hosting panels complain about that part when pasted manually.

The endpoint also tries to create the table automatically, but manual creation in phpMyAdmin is easier to debug.

### 4. Test endpoint

Replace `CHANGE_ME_SECRET_TOKEN` before running:

```bash
curl -X POST "https://diamant.uz/api/update-gold-price.php" \
  -H "Content-Type: application/json" \
  -H "X-Gold-Price-Token: CHANGE_ME_SECRET_TOKEN" \
  -d '{"event":"gold_price_updated","generation_id":999999,"kurs":890000,"created_at":"2026-06-26 12:00:00","brands":{"diamant":{"375_from":575000,"375_to":630000,"583_from":890000,"583_to":1500000,"585_from":890000,"585_to":1090000,"750_from":1145000,"750_to":1500000,"850_from":1300000,"850_to":1500000,"875_from":1340000,"875_to":1540000,"916_from":1400000,"916_to":1600000,"999_from":1530000,"999_to":1680000}}}'
```

Expected response:

```json
{"ok":true,"source_price_id":999999}
```

Check latest row:

```sql
SELECT id, source_price_id, kurs, `583_from`, `583_to`, `585_from`, `585_to`, created_at
FROM diamant_gold_prices
ORDER BY id DESC
LIMIT 1;
```

## Alternative: RabbitMQ worker

Use this only if the site/server can run a permanent PHP process.

Files:

```text
composer.json
gold_price_worker.php
supervisor/diamant-gold-price-worker.conf
systemd/diamant-gold-price-worker.service
```

This requires:

- Composer package `php-amqplib/php-amqplib`;
- access to run a permanent process through Supervisor or systemd;
- RabbitMQ port `5672` open from the site server to the VPS.

If the hosting does not provide Supervisor/systemd, do not use this method.
