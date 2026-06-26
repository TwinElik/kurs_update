# VPS setup for kurs bot

This guide prepares the `kurs` Telegram bot on Ubuntu VPS.

The active sync architecture is:

```text
Telegram bot
  -> VPS MySQL price history
  -> VPS MySQL site_sync_jobs
  -> HTTPS endpoint on each site
  -> local MySQL of each site
```

## 1. Update project

```bash
cd ~/Documents/kurs_update
git pull
source .venv/bin/activate
pip install -r requirements.txt
python -m py_compile bot.py image_renderer.py price_algorithm.py price_events.py site_sync.py sync_worker.py
```

## 2. Check MySQL service

Check MySQL:

```bash
systemctl status mysql
```

If MySQL is missing, check MariaDB:

```bash
systemctl status mariadb
```

If both are missing:

```bash
sudo apt update
sudo apt install mariadb-server mariadb-client -y
sudo systemctl enable mariadb
sudo systemctl start mariadb
sudo systemctl status mariadb
```

MariaDB works with `pymysql` and is compatible with this bot.

## 3. Create database and user

```bash
sudo mysql
```

```sql
CREATE DATABASE IF NOT EXISTS kurs_update
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'kurs_user'@'localhost'
IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD';

GRANT ALL PRIVILEGES ON kurs_update.* TO 'kurs_user'@'localhost';

FLUSH PRIVILEGES;

EXIT;
```

## 4. Configure `.env`

```bash
nano .env
```

Required:

```env
BOT_TOKEN=put_token_here
PHONE=
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=kurs_user
DB_PASSWORD=CHANGE_ME_STRONG_PASSWORD
DB_NAME=kurs_update

DIAMANT_SYNC_ENABLED=1
DIAMANT_ENDPOINT_URL=https://diamant.uz/api/update-gold-price.php
DIAMANT_ENDPOINT_TOKEN=mUaGcwNqfXcZz0p8xsugs3VM7g2ww5K2p6rCRy6orcU

SITE_SYNC_TIMEOUT_SECONDS=5
SYNC_WORKER_INTERVAL_SECONDS=60
SYNC_WORKER_BATCH_SIZE=10
MANUAL_SYNC_LIMIT=5
MANUAL_SYNC_TIMEOUT_SECONDS=15
```

Future sites:

```env
TILLACHI_SYNC_ENABLED=0
TILLACHI_ENDPOINT_URL=
TILLACHI_ENDPOINT_TOKEN=

GOLDEXPERT_SYNC_ENABLED=0
GOLDEXPERT_ENDPOINT_URL=
GOLDEXPERT_ENDPOINT_TOKEN=

SKUPKA_SYNC_ENABLED=0
SKUPKA_ENDPOINT_URL=
SKUPKA_ENDPOINT_TOKEN=
```

## 5. Initialize tables

The bot creates tables on startup, but manual init is possible:

```bash
python - <<'PY'
import bot
from site_sync import init_sync_db
bot.init_db()
init_sync_db()
print("tables initialized")
PY
```

Check:

```bash
mysql -u kurs_user -p kurs_update -e "SHOW TABLES;"
```

Expected tables:

```text
diamant_gold_prices
generated_images
goldexpert_gold_prices
price_generations
site_sync_jobs
skupka_gold_prices
tillachi_gold_prices
```

## 6. Install bot service

If service already exists, just restart it:

```bash
sudo systemctl restart kurs
sudo systemctl status kurs
journalctl -u kurs -f
```

## 7. Install sync retry worker

```bash
sudo cp systemd/kurs-sync.service /etc/systemd/system/kurs-sync.service
sudo systemctl daemon-reload
sudo systemctl enable kurs-sync
sudo systemctl start kurs-sync
sudo systemctl status kurs-sync
```

Logs:

```bash
journalctl -u kurs-sync -f
```

## 8. Site endpoint files

For Diamant, upload:

```text
site_integrations/diamant/update-gold-price.php
site_integrations/diamant/endpoint_token.php
```

to:

```text
/var/www/u0861209/data/www/diamant.uz/api/update-gold-price.php
/var/www/u0861209/data/www/diamant.uz/api/endpoint_token.php
```

Create table on the site using:

```text
site_integrations/diamant/create_diamant_gold_prices.sql
```

## 9. Test site endpoint directly

```bash
curl -i https://diamant.uz/api/update-gold-price.php
```

Good response:

```text
{"ok":false,"error":"method_not_allowed"}
```

POST test:

```bash
curl -i -X POST "https://diamant.uz/api/update-gold-price.php" \
  -H "Content-Type: application/json" \
  -H "X-Gold-Price-Token: mUaGcwNqfXcZz0p8xsugs3VM7g2ww5K2p6rCRy6orcU" \
  -d '{"event":"gold_price_updated","generation_id":999999,"kurs":890000,"created_at":"2026-06-26 12:00:00","brands":{"diamant":{"375_from":575000,"375_to":630000,"583_from":890000,"583_to":1500000,"585_from":890000,"585_to":1090000,"750_from":1145000,"750_to":1500000,"850_from":1300000,"850_to":1500000,"875_from":1340000,"875_to":1540000,"916_from":1400000,"916_to":1600000,"999_from":1530000,"999_to":1680000}}}'
```

Expected:

```json
{"ok":true,"source_price_id":999999}
```

## 10. Check sync jobs

Bot commands:

```text
/sync_status
/retry_failed
```

The main bot keyboard also has:

```text
🔁 Синхронизировать
```

After every new generation the bot shows sync results in chat. If a site fails, it returns a readable reason like server not responding, DB/server error, missing token, or endpoint not found.

Manual sync button checks only a small batch so the bot UI does not hang:

```env
MANUAL_SYNC_LIMIT=5
MANUAL_SYNC_TIMEOUT_SECONDS=15
```

The button immediately replies that sync started in background. The final result arrives as a separate message.

SQL:

```bash
mysql -u kurs_user -p kurs_update -e "SELECT id, brand, source_price_id, status, attempts, updated_at, synced_at FROM site_sync_jobs ORDER BY id DESC LIMIT 20;"
```

Failed jobs:

```bash
mysql -u kurs_user -p kurs_update -e "SELECT id, brand, source_price_id, attempts, LEFT(last_error, 200) AS error FROM site_sync_jobs WHERE status='failed' ORDER BY id DESC LIMIT 20;"
```
