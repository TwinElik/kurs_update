# VPS setup for kurs bot

This guide prepares the `kurs` Telegram bot on Ubuntu VPS with MySQL-compatible storage.

## 1. Update project

```bash
cd ~/Documents/kurs_update
git pull
source .venv/bin/activate
pip install -r requirements.txt
python -m py_compile bot.py image_renderer.py price_algorithm.py sync_worker.py
```

## 2. Check MySQL service

Check MySQL:

```bash
systemctl status mysql
```

If you see `Unit mysql.service could not be found`, check MariaDB:

```bash
systemctl status mariadb
```

If both services are missing, install MariaDB:

```bash
sudo apt update
sudo apt install mariadb-server mariadb-client -y
sudo systemctl enable mariadb
sudo systemctl start mariadb
sudo systemctl status mariadb
```

MariaDB works with `pymysql` and is compatible with the SQL used by this bot.

If you specifically need MySQL package instead:

```bash
sudo apt update
sudo apt install mysql-server -y
sudo systemctl enable mysql
sudo systemctl start mysql
sudo systemctl status mysql
```

## 3. Create database and user

Open MySQL/MariaDB shell:

```bash
sudo mysql
```

Run:

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

Open `.env`:

```bash
nano .env
```

Add or update:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=kurs_user
DB_PASSWORD=CHANGE_ME_STRONG_PASSWORD
DB_NAME=kurs_update
RABBITMQ_URL=amqp://kurs_sync:CHANGE_ME_RABBIT_PASSWORD@127.0.0.1:5672/
RABBITMQ_QUEUE=kurs_site_sync
```

`BOT_TOKEN` must also exist in `.env`.

Add site database settings for every enabled brand:

```env
DIAMANT_SITE_DB_HOST=
DIAMANT_SITE_DB_PORT=3306
DIAMANT_SITE_DB_USER=
DIAMANT_SITE_DB_PASSWORD=
DIAMANT_SITE_DB_NAME=

TILLACHI_SITE_DB_HOST=
TILLACHI_SITE_DB_PORT=3306
TILLACHI_SITE_DB_USER=
TILLACHI_SITE_DB_PASSWORD=
TILLACHI_SITE_DB_NAME=

GOLDEXPERT_SITE_DB_HOST=
GOLDEXPERT_SITE_DB_PORT=3306
GOLDEXPERT_SITE_DB_USER=
GOLDEXPERT_SITE_DB_PASSWORD=
GOLDEXPERT_SITE_DB_NAME=

SKUPKA_SITE_DB_HOST=
SKUPKA_SITE_DB_PORT=3306
SKUPKA_SITE_DB_USER=
SKUPKA_SITE_DB_PASSWORD=
SKUPKA_SITE_DB_NAME=
```

If a site DB is not configured yet, sync jobs for that brand will become `failed`, but the bot will keep working.

## 5. Install RabbitMQ

```bash
sudo apt update
sudo apt install rabbitmq-server -y
sudo systemctl enable rabbitmq-server
sudo systemctl start rabbitmq-server
sudo systemctl status rabbitmq-server
```

Create RabbitMQ user:

```bash
sudo rabbitmqctl add_user kurs_sync CHANGE_ME_RABBIT_PASSWORD
sudo rabbitmqctl set_permissions -p / kurs_sync ".*" ".*" ".*"
```

Check queue list:

```bash
sudo rabbitmqctl list_queues name messages_ready messages_unacknowledged durable
```

## 6. Initialize tables

The bot creates tables on startup, but you can initialize them manually:

```bash
python - <<'PY'
import bot
bot.init_db()
print("tables initialized")
PY
```

Check tables:

```bash
mysql -u kurs_user -p kurs_update -e "SHOW TABLES;"
```

Expected tables:

```text
diamant_gold_prices
generated_images
goldexpert_gold_prices
price_generations
skupka_gold_prices
tillachi_gold_prices
site_sync_jobs
```

## 7. Install sync worker service

Copy service file:

```bash
sudo cp systemd/kurs-sync.service /etc/systemd/system/kurs-sync.service
sudo systemctl daemon-reload
sudo systemctl enable kurs-sync
sudo systemctl start kurs-sync
sudo systemctl status kurs-sync
```

Worker logs:

```bash
journalctl -u kurs-sync -f
```

## 8. Restart bot service

```bash
sudo systemctl restart kurs
sudo systemctl status kurs
```

Follow logs:

```bash
journalctl -u kurs -f
```

## 9. If bot is running manually

If you previously started the bot with:

```bash
python bot.py
```

stop it with `Ctrl+C`, otherwise Telegram can return polling conflict.

## 10. Quick data check

After generating a rate in the bot, check the latest Diamant row:

```bash
mysql -u kurs_user -p kurs_update -e "SELECT id, kurs, \`583_from\`, \`583_to\`, \`585_from\`, \`585_to\`, created_at FROM diamant_gold_prices ORDER BY id DESC LIMIT 1;"
```

Check sync jobs:

```bash
mysql -u kurs_user -p kurs_update -e "SELECT id, brand, source_price_id, target_site, status, attempts, last_error FROM site_sync_jobs ORDER BY id DESC LIMIT 10;"
```

Check queue:

```bash
sudo rabbitmqctl list_queues name messages_ready messages_unacknowledged durable
```

## 11. Target site table requirement

The worker inserts a new row into the site DB. It does not update existing rows.

Every target site table must have:

```sql
source_price_id INT UNIQUE
```

The worker creates the table when it does not exist. If the table exists without `source_price_id`, the worker tries to add the column and unique key automatically.
