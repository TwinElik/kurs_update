# VPS setup

Инструкция для запуска бота `kurs` на Ubuntu VPS с MySQL 5.7/8.0.

## 1. Обновить проект

```bash
cd ~/Documents/kurs_update
git pull
source .venv/bin/activate
pip install -r requirements.txt
python -m py_compile bot.py image_renderer.py price_algorithm.py
```

## 2. Создать базу MySQL

```bash
sudo mysql
```

Внутри MySQL:

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

## 3. Настроить `.env`

```bash
nano .env
```

Добавить или заменить:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=kurs_user
DB_PASSWORD=CHANGE_ME_STRONG_PASSWORD
DB_NAME=kurs_update
```

`BOT_TOKEN` тоже должен быть в `.env`.

## 4. Создать таблицы

Бот сам создаёт таблицы при старте, но можно проверить вручную:

```bash
python - <<'PY'
import bot
bot.init_db()
print("tables initialized")
PY
```

Проверить список таблиц:

```bash
mysql -u kurs_user -p kurs_update -e "SHOW TABLES;"
```

Должны быть:

```text
diamant_gold_prices
generated_images
goldexpert_gold_prices
price_generations
skupka_gold_prices
tillachi_gold_prices
```

## 5. Перезапустить сервис

```bash
sudo systemctl restart kurs
sudo systemctl status kurs
```

Логи:

```bash
journalctl -u kurs -f
```

## 6. Если бот запущен вручную

Если перед этим запускали:

```bash
python bot.py
```

то остановить через `Ctrl+C`, иначе Telegram может дать конфликт polling.

## 7. Быстрая проверка записи

После генерации курса в боте проверить последнюю строку Diamant:

```bash
mysql -u kurs_user -p kurs_update -e "SELECT id, kurs, \`583_from\`, \`583_to\`, \`585_from\`, \`585_to\`, created_at FROM diamant_gold_prices ORDER BY id DESC LIMIT 1;"
```

