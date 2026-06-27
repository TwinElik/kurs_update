# VPS site sync worker

This is the reliable VPS-side sync layer.

Current active flow:

```text
bot generates price
  -> saves price in VPS MySQL
  -> creates rows in site_sync_jobs
  -> tries HTTPS endpoint immediately
  -> sync_worker.py retries pending/failed jobs later
```

The reliable active path for REG.ru hosting is endpoint + `site_sync_jobs`.

## 1. Update VPS

```bash
cd ~/Documents/kurs_update
git pull
source .venv/bin/activate
pip install -r requirements.txt
python -m py_compile bot.py site_sync.py sync_worker.py price_events.py
```

## 2. Configure `.env`

```bash
nano .env
```

Required for Diamant:

```env
DIAMANT_SYNC_ENABLED=1
DIAMANT_ENDPOINT_URL=https://diamant.uz/api/update-gold-price.php
DIAMANT_ENDPOINT_TOKEN=THE_SAME_RANDOM_HMAC_SECRET_AS_ON_THE_SITE
SITE_SYNC_TIMEOUT_SECONDS=5
SYNC_WORKER_INTERVAL_SECONDS=60
SYNC_WORKER_BATCH_SIZE=10
MANUAL_SYNC_LIMIT=5
MANUAL_SYNC_TIMEOUT_SECONDS=15
```

Future site example:

```env
GOLDEXPERT_SYNC_ENABLED=1
GOLDEXPERT_ENDPOINT_URL=https://goldexpert.uz/api/update-gold-price.php
GOLDEXPERT_ENDPOINT_TOKEN=CHANGE_ME
```

## 3. Initialize table

The bot and worker create the table automatically, but manual init is possible:

```bash
python - <<'PY'
from site_sync import init_sync_db
init_sync_db()
print("site_sync_jobs ready")
PY
```

Check:

```bash
mysql -u kurs_user -p kurs_update -e "SHOW TABLES LIKE 'site_sync_jobs';"
```

## 4. Install systemd service

```bash
sudo cp systemd/kurs-sync.service /etc/systemd/system/kurs-sync.service
sudo systemctl daemon-reload
sudo systemctl enable kurs-sync
sudo systemctl start kurs-sync
sudo systemctl status kurs-sync
```

Watch logs:

```bash
journalctl -u kurs-sync -f
```

## 5. Restart bot

```bash
sudo systemctl restart kurs
journalctl -u kurs -f
```

When a new rate is generated, expected logs:

```text
Site sync OK: job=... brand=diamant source_price_id=...
```

If site is down:

```text
Site sync failed: job=... brand=diamant HTTP 500: ...
```

Then `kurs-sync` will retry it later.

The bot also shows the sync result in chat right after image generation:

```text
Синхронизация сайтов:
✅ Diamant: успешно
```

If a site fails, the bot shows a readable reason, for example:

```text
❌ Diamant: сервер сайта не отвечает
❌ Diamant: ошибка сервера или БД сайта
❌ Diamant: сайт отклонил HMAC-подпись
```

## 6. Bot commands

Send to Telegram bot:

```text
/sync_status
```

Shows totals by brand/status and latest jobs.

```text
/retry_failed
```

Immediately retries pending/failed sync jobs.

The main reply keyboard also has:

```text
🔁 Синхронизировать
```

It does the same retry and returns the result in chat.

Manual sync checks a small batch and has its own UI timeout:

```env
MANUAL_SYNC_LIMIT=5
MANUAL_SYNC_TIMEOUT_SECONDS=15
```

The bot answers immediately and sends the final sync result as a separate message.

## 7. SQL checks

All jobs:

```bash
mysql -u kurs_user -p kurs_update -e "SELECT id, brand, source_price_id, status, attempts, updated_at, synced_at FROM site_sync_jobs ORDER BY id DESC LIMIT 20;"
```

Failed jobs:

```bash
mysql -u kurs_user -p kurs_update -e "SELECT id, brand, source_price_id, attempts, LEFT(last_error, 200) AS error FROM site_sync_jobs WHERE status='failed' ORDER BY id DESC LIMIT 20;"
```

Reset failed to pending:

```bash
mysql -u kurs_user -p kurs_update -e "UPDATE site_sync_jobs SET status='pending' WHERE status='failed';"
```
