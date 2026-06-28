# Goldexpert: цены через JSON и JavaScript

Страница WordPress/Elementor использует собственные метки:

```text
[gold_price field="proba_999_begin"]
```

ACF и `wp_postmeta` в выводе цен не участвуют.

## Схема

```text
Бот
  -> подписанный POST /api/update-gold-price.php
  -> история в goldexpert_gold_prices
  -> атомарное обновление /api/current-gold-prices.json
  -> один fetch из gold-prices.js
  -> замена всех [gold_price ...] на странице
```

Страница не обращается к MySQL. Она читает маленький статический JSON, поэтому
нагрузка минимальна. JSON обновляется только при новой синхронизации.

## 1. Загрузить файлы

Создать в корне WordPress папку `api/` и загрузить:

```text
site_integrations/goldexpert/update-gold-price.php -> api/update-gold-price.php
site_integrations/goldexpert/gold-prices.js -> api/gold-prices.js
site_integrations/goldexpert/endpoint_token.example.php -> api/endpoint_token.php
```

В `endpoint_token.php` установить отдельный случайный HMAC-секрет минимум из 32
байт. Файл с настоящим секретом нельзя добавлять в Git.

PHP-пользователь должен иметь право создавать и заменять файл
`api/current-gold-prices.json`.

## 2. Настроить VPS

```env
GOLDEXPERT_SYNC_ENABLED=1
GOLDEXPERT_ENDPOINT_URL=https://goldexpert.uz/api/update-gold-price.php
GOLDEXPERT_ENDPOINT_TOKEN=THE_SAME_RANDOM_HMAC_SECRET_AS_ON_GOLDEXPERT
```

## 3. Проверить синхронизацию

```bash
python scripts/test_goldexpert_endpoint.py
```

После успешного POST должны работать URL:

```text
https://goldexpert.uz/api/current-gold-prices.json
https://goldexpert.uz/api/gold-prices.js
```

JSON должен содержать `"ok": true` и объект `fields`.

## 4. Заменить ACF-метки в Elementor

Было:

```text
[acf field="proba_999_begin"]
```

Стало:

```text
[gold_price field="proba_999_begin"]
```

Пример блока:

```html
<div data-gold-prices-root style="visibility: hidden;">
  <h5 style="font-size: 28px;"><strong>999 PROBA (24 karat)</strong></h5>
  <p>
    <strong class="nowrap">
      Narxi: [gold_price field="proba_999_begin"] - [gold_price field="proba_999_end"] so'm
    </strong>
  </p>
</div>
```

Доступные имена:

```text
proba_375_begin / proba_375_end
proba_583_begin / proba_583_end
proba_585_begin / proba_585_end
proba_750_begin / proba_750_end
proba_850_begin / proba_850_end
proba_875_begin / proba_875_end
proba_916_begin / proba_916_end
proba_999_begin / proba_999_end
koronki_zoloto_begin / koronki_zoloto_end
```

Коронки используют диапазон 850 пробы.

## 5. Подключить JavaScript один раз

После всех ценовых блоков добавить один HTML-виджет Elementor:

```html
<script src="/api/gold-prices.js" defer></script>
```

`data-gold-prices-root` ограничивает область поиска меток. Если атрибут не
добавлен, скрипт безопасно ищет метки во всём `body`. Он изменяет только
текстовые узлы и не перезаписывает DOM Elementor.

## 6. Очистить кэш

После изменения страницы очистить:

1. кэш Elementor;
2. кэш плагина ускорения/страниц;
3. Cloudflare cache, если включён;
4. браузер через `Ctrl+F5`.

При дальнейших изменениях цены `current-gold-prices.json` обновляется
автоматически. JS использует 30-секундную версию URL, поэтому новая цена
появится максимум примерно через 30 секунд без ручного вмешательства.

## Безопасность

- Запись цен остаётся защищена HMAC и timestamp.
- JSON публичный, но содержит только публичные цены.
- JavaScript не получает реквизиты MySQL.
- Endpoint выполняет запись, браузер читает только статический JSON.
- Обновление JSON атомарное: посетитель не увидит частично записанный файл.

## Откат

1. Вернуть `[acf field="..."]` либо прежние статические числа.
2. Удалить подключение `/api/gold-prices.js` со страницы.
3. Очистить кэш страницы.

История цен и работа бота при этом не затрагиваются.
