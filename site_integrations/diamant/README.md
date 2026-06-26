# Diamant site worker

This folder contains scripts for the Diamant OpenCart site.

The worker runs on the Diamant hosting/server, connects to RabbitMQ on the VPS, receives gold price events, and inserts a new row into the local Diamant MySQL database.

## Files

```text
composer.json
create_diamant_gold_prices.sql
gold_price_worker.php
supervisor/diamant-gold-price-worker.conf
systemd/diamant-gold-price-worker.service
```

## 1. Copy files to Diamant

Recommended target path:

```text
/var/www/u0861209/data/www/diamant.uz/system/cron/gold_price_worker.php
```

The script expects OpenCart config here:

```text
/var/www/u0861209/data/www/diamant.uz/config.php
```

If config is elsewhere, set:

```bash
export OC_CONFIG_PATH=/full/path/to/config.php
```

## 2. Install PHP RabbitMQ library

On the Diamant server/site root:

```bash
cd /var/www/u0861209/data/www/diamant.uz
composer require php-amqplib/php-amqplib
```

If Composer is not available on the hosting, install `vendor/` locally and upload it to the site root.

## 3. Create table

Run SQL from:

```text
create_diamant_gold_prices.sql
```

The worker also tries to create the table automatically, but creating it manually first is cleaner.

## 4. Test manually

```bash
cd /var/www/u0861209/data/www/diamant.uz
RABBITMQ_HOST=YOUR_VPS_IP \
RABBITMQ_PORT=5672 \
RABBITMQ_USER=jewelry_user \
RABBITMQ_PASSWORD=my_secure_password \
RABBITMQ_QUEUE=gold_price_events \
php system/cron/gold_price_worker.php
```

The script will wait for messages. Generate a new price in the bot and check the table:

```sql
SELECT id, source_price_id, kurs, `583_from`, `583_to`, `585_from`, `585_to`, created_at
FROM diamant_gold_prices
ORDER BY id DESC
LIMIT 1;
```

## 5. Run permanently

Use Supervisor if available:

```bash
sudo cp supervisor/diamant-gold-price-worker.conf /etc/supervisor/conf.d/diamant-gold-price-worker.conf
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status diamant-gold-price-worker
```

Or systemd if available:

```bash
sudo cp systemd/diamant-gold-price-worker.service /etc/systemd/system/diamant-gold-price-worker.service
sudo systemctl daemon-reload
sudo systemctl enable diamant-gold-price-worker
sudo systemctl start diamant-gold-price-worker
sudo systemctl status diamant-gold-price-worker
```

## Important RabbitMQ behavior

If four sites consume the same queue `gold_price_events`, RabbitMQ will distribute messages between consumers.

For production with multiple sites, use one queue per site or a fanout exchange. Directly consuming `gold_price_events` is okay for the first Diamant-only test.
