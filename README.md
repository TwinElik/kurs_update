# Gold Price Photo Bot

Отдельный Telegram-бот для генерации картинки цен скупки золота.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python bot.py
```

На Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\python.exe bot.py
```

В `.env`:

```env
BOT_TOKEN=...
PHONE=+998 55 055 00 02
DEFAULT_ORG=diamant
```

## Использование

Пользователь отправляет главный курс:

```text
1200
```

Бот отвечает картинкой по шаблону Diamant и текстовой расшифровкой цен.

## JavaScript API

Файл `price_algorithm.js` содержит требуемую функцию:

```js
const { generatePriceRange } = require("./price_algorithm.js");

console.log(generatePriceRange(1200));
```

Она возвращает:

```js
{
  "583": [1200000, 1400000],
  "585": [1204116, 1404116],
  "750": [1545000, 1745000],
  "850": [1750000, 1950000],
  "875": [1805000, 2005000],
  "916": [1890000, 2090000],
  "999": [2060000, 2210000]
}
```
