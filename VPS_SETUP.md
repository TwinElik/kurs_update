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
```

`BOT_TOKEN` must also exist in `.env`.

## 5. Initialize tables

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

## 6. Restart service

```bash
sudo systemctl restart kurs
sudo systemctl status kurs
```

Follow logs:

```bash
journalctl -u kurs -f
```

## 7. If bot is running manually

If you previously started the bot with:

```bash
python bot.py
```

stop it with `Ctrl+C`, otherwise Telegram can return polling conflict.

## 8. Quick data check

After generating a rate in the bot, check the latest Diamant row:

```bash
mysql -u kurs_user -p kurs_update -e "SELECT id, kurs, \`583_from\`, \`583_to\`, \`585_from\`, \`585_to\`, created_at FROM diamant_gold_prices ORDER BY id DESC LIMIT 1;"
```

