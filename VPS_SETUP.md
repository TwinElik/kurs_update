# VPS setup for kurs bot

This guide prepares the `kurs` Telegram bot on Ubuntu VPS with MySQL-compatible storage.

## 1. Update project

```bash
cd ~/Documents/kurs_update
git pull
source .venv/bin/activate
pip install -r requirements.txt
python -m py_compile bot.py image_renderer.py price_algorithm.py
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
RABBITMQ_URL=amqp://jewelry_user:my_secure_password@localhost/
RABBITMQ_QUEUE=gold_price_events
```

`BOT_TOKEN` must also exist in `.env`.

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
sudo rabbitmqctl add_user jewelry_user my_secure_password
sudo rabbitmqctl set_permissions -p / jewelry_user ".*" ".*" ".*"
```

Optional management UI:

```bash
sudo rabbitmq-plugins enable rabbitmq_management
sudo systemctl restart rabbitmq-server
```

Management UI:

```text
http://SERVER_IP:15672
```

Check queue:

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
```

## 7. Restart service

```bash
sudo systemctl restart kurs
sudo systemctl status kurs
```

Follow logs:

```bash
journalctl -u kurs -f
```

## 8. If bot is running manually

If you previously started the bot with:

```bash
python bot.py
```

stop it with `Ctrl+C`, otherwise Telegram can return polling conflict.

## 9. Quick data check

After generating a rate in the bot, check the latest Diamant row:

```bash
mysql -u kurs_user -p kurs_update -e "SELECT id, kurs, \`583_from\`, \`583_to\`, \`585_from\`, \`585_to\`, created_at FROM diamant_gold_prices ORDER BY id DESC LIMIT 1;"
```

Check RabbitMQ queue:

```bash
sudo rabbitmqctl list_queues name messages_ready messages_unacknowledged durable
```

## 10. Site developer task

Give site developers:

```text
DSN: amqp://jewelry_user:my_secure_password@SERVER_IP:5672/
Queue name: gold_price_events
```

The bot publishes JSON messages like:

```json
{
  "event": "gold_price_updated",
  "generation_id": 123,
  "price": 890.0,
  "kurs": 890000,
  "timestamp": 1782315200,
  "created_at": "2026-06-26 10:00:00",
  "brands": {
    "diamant": {
      "583_from": 890000,
      "583_to": 1500000,
      "585_from": 890000,
      "585_to": 1090000
    }
  }
}
```

Site worker logic:

1. Listen to RabbitMQ.
2. Read `gold_price_updated` events.
3. Insert a new row into the site database.
4. Clear/update site cache if needed.
5. Send `basic_ack` only after the site database update succeeds.
6. Run the worker permanently through Supervisor/systemd.

Important RabbitMQ note:

If several sites consume the same queue `gold_price_events`, RabbitMQ distributes messages between consumers. It does not broadcast one message to every consumer.

For all sites to receive every update, site developers should use one of these approaches:

- one queue per site bound to a shared exchange;
- or one central site-sync script that consumes `gold_price_events` and then updates every site.

For a first test with one site, direct consume from `gold_price_events` is okay.
