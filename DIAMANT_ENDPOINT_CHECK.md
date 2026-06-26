# Diamant endpoint check

Use these commands on the VPS.

## 1. Update bot code

```bash
cd ~/Documents/kurs_update
git pull
source .venv/bin/activate
pip install -r requirements.txt
python -m py_compile bot.py site_endpoint_sender.py rabbitmq_events.py
```

## 2. Check latest git commit

```bash
git log -1 --oneline
```

Expected latest commit:

```text
529d3a7 Enable Diamant endpoint sync by default
```

or newer.

## 3. Check `.env`

```bash
grep DIAMANT .env
```

Expected:

```env
ENABLE_DIAMANT_ENDPOINT_SYNC=1
DIAMANT_ENDPOINT_URL=https://diamant.uz/api/update-gold-price.php
DIAMANT_ENDPOINT_TOKEN=mUaGcwNqfXcZz0p8xsugs3VM7g2ww5K2p6rCRy6orcU
```

If missing, open:

```bash
nano .env
```

and add:

```env
ENABLE_DIAMANT_ENDPOINT_SYNC=1
DIAMANT_ENDPOINT_URL=https://diamant.uz/api/update-gold-price.php
DIAMANT_ENDPOINT_TOKEN=mUaGcwNqfXcZz0p8xsugs3VM7g2ww5K2p6rCRy6orcU
```

## 4. Check service path

```bash
systemctl cat kurs
```

`ExecStart` should point to:

```text
/home/ubuntu/Documents/kurs_update/bot.py
```

## 5. Restart bot and watch logs

```bash
sudo systemctl restart kurs
journalctl -u kurs -f
```

Then open Telegram bot, press the change-rate button, and enter a new rate that was not used today.

Expected log:

```text
Diamant endpoint sync OK
```

If it fails, the log will show one of:

```text
Diamant endpoint sync skipped: ENABLE_DIAMANT_ENDPOINT_SYNC=0
Diamant endpoint sync skipped: DIAMANT_ENDPOINT_URL or DIAMANT_ENDPOINT_TOKEN is empty
Diamant endpoint sync failed: HTTP 403
Diamant endpoint sync failed: HTTP 500
```

## 6. Direct endpoint availability check

This checks whether the PHP file exists and responds.

```bash
curl -i https://diamant.uz/api/update-gold-price.php
```

Good response:

```text
HTTP/...
...
{"ok":false,"error":"method_not_allowed"}
```

`method_not_allowed` is OK here because this test uses GET, while endpoint accepts only POST.

## 7. Direct endpoint POST test

This bypasses Telegram bot and writes a test row directly to Diamant database.

```bash
curl -i -X POST "https://diamant.uz/api/update-gold-price.php" \
  -H "Content-Type: application/json" \
  -H "X-Gold-Price-Token: mUaGcwNqfXcZz0p8xsugs3VM7g2ww5K2p6rCRy6orcU" \
  -d '{"event":"gold_price_updated","generation_id":999999,"kurs":890000,"created_at":"2026-06-26 12:00:00","brands":{"diamant":{"375_from":575000,"375_to":630000,"583_from":890000,"583_to":1500000,"585_from":890000,"585_to":1090000,"750_from":1145000,"750_to":1500000,"850_from":1300000,"850_to":1500000,"875_from":1340000,"875_to":1540000,"916_from":1400000,"916_to":1600000,"999_from":1530000,"999_to":1680000}}}'
```

Good response:

```json
{"ok":true,"source_price_id":999999}
```

If response is `403 forbidden`, token is wrong or `endpoint_token.php` was not uploaded.

If response is `500 config_not_found`, endpoint file is in the wrong folder. Correct path:

```text
/var/www/u0861209/data/www/diamant.uz/api/update-gold-price.php
```

and OpenCart config must be here:

```text
/var/www/u0861209/data/www/diamant.uz/config.php
```

## 8. Check row in phpMyAdmin

Open phpMyAdmin, select database:

```text
u0861209_ocar517
```

Run:

```sql
SELECT id, source_price_id, kurs, price_583_from, price_583_to, price_585_from, price_585_to, created_at
FROM diamant_gold_prices
ORDER BY id DESC
LIMIT 5;
```

## 9. RabbitMQ note

If RabbitMQ queue grows, that does not mean endpoint sync failed.

RabbitMQ messages grow because no site worker is consuming the queue.

For Diamant, current active path is:

```text
bot -> HTTPS endpoint -> Diamant MySQL
```

not:

```text
bot -> RabbitMQ -> site worker
```
