import asyncio
import hashlib
import html
import json
import logging
import os
import queue
import re
import threading
from contextlib import contextmanager
from io import BytesIO
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import pymysql
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont


load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MANAGER_BOT_TOKEN = os.getenv("MANAGER_BOT_TOKEN", "")
MANAGER_CHAT_ID = os.getenv("MANAGER_CHAT_ID", "")
MANAGER_CHAT_IDS = set()
DB_POOL_SIZE = max(1, int(os.getenv("DB_POOL_SIZE", "5")))
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", ""),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
    "connect_timeout": 5,
    "read_timeout": 10,
    "write_timeout": 10,
}
SITE_URL = os.getenv("SITE_URL", "http://localhost/diamant/").rstrip("/") + "/"
PRODUCT_SITE_URL = os.getenv("PRODUCT_SITE_URL", "https://diamant.uz/").rstrip("/") + "/"
PUBLIC_IMAGE_URL = os.getenv("PUBLIC_IMAGE_URL", "https://diamant.uz/image/").rstrip("/") + "/"
IMAGE_ROOT = Path(os.getenv("IMAGE_ROOT", "C:/xampp/htdocs/diamant/image"))
LANGUAGE_ID = int(os.getenv("LANGUAGE_ID", "1"))
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}
USER_STATES = {}
SEARCH_TOKENS = {}
SEARCH_TASKS = {}
USER_LANGS = {}
ORDER_DRAFTS = {}
MANAGER_CANCEL_DRAFTS = {}
REVIEW_DRAFTS = {}
MANAGER_NAME_DRAFTS = {}
MANAGER_CONTACT_DRAFTS = {}
MANAGER_REMARK_DRAFTS = {}
MANAGER_ACCESS_REQUEST_MESSAGES = {}
REVIEW_FALLBACK_PATH = Path(__file__).with_name("order_reviews.json")
MANAGER_ACCESS_PATH = Path(__file__).with_name("manager_access.json")
ADMIN_MANAGER_IDS = {"5216485765", "995855560"}
HTTP_SESSION = None
PAGE_SIZE = 5
TG_ORDER_STATUSES = {
    "new": "Ожидание",
    "pending": "Ожидание",
    "processing": "В обработке",
    "in_transit": "В пути",
    "completed": "Завершено",
    "cancelled": "Отменено",
    "accepted": "В обработке",
    "contacted": "В обработке",
    "done": "Завершено",
    "completed_success": "Завершено",
    "completed_failed": "Отменено",
}
TG_ORDER_LIST_STATUSES = {
    "new": "Ожидание",
    "pending": "Ожидание",
    "processing": "В обработке",
    "in_transit": "В пути",
    "completed": "Успешно",
    "cancelled": "Отменено",
    "accepted": "В обработке",
    "contacted": "В обработке",
    "done": "Успешно",
    "completed_success": "Успешно",
    "completed_failed": "Отменено",
}
FINAL_ORDER_STATUSES = {"completed", "done", "completed_success", "cancelled", "completed_failed"}
MANAGER_ORDER_FILTERS = [
    ("all", "Все", None),
    ("new", "Новые", ["new", "pending"]),
    ("processing", "В обработке", ["processing", "accepted", "contacted"]),
    ("in_transit", "В пути", ["in_transit"]),
    ("completed", "Завершены", ["completed", "done", "completed_success"]),
    ("cancelled", "Отменены", ["cancelled", "completed_failed"]),
]
MANAGER_ORDER_FILTER_MAP = {key: {"label": label, "statuses": statuses} for key, label, statuses in MANAGER_ORDER_FILTERS}
REGIONS = [
    "г. Ташкент",
    "Республика Каракалпакстан",
    "Андижанская область",
    "Бухарская область",
    "Джизакская область",
    "Кашкадарьинская область",
    "Навоийская область",
    "Наманганская область",
    "Самаркандская область",
    "Сурхандарьинская область",
    "Сырдарьинская область",
    "Ташкентская область",
    "Ферганская область",
    "Хорезмская область",
]
CART_TTL_MINUTES = 7
CART_TEXT = "🛒 Корзина"
MY_ORDERS_TEXT = "📦 Заказы"
MANAGER_ORDERS_TEXT = "📋 Заказы"
LANG_TEXTS = {
    "ru": {
        "choose_language": "Выберите язык:",
        "language_saved": "Язык выбран.",
        "start": "Привет! Это бот Diamant. Здесь вы можете приобрести и продать ювелирные украшения.",
        "main_menu": "Главное меню:",
        "buy": "💎 Купить",
        "sell": "🤝 Продать",
        "cart": "🛒 Корзина",
        "orders": "📦 Заказы",
        "contacts": "☎️ Связаться с нами",
        "language": "🌐 Язык",
        "catalog": "Каталог:",
        "catalog_placeholder": "Выберите категорию",
        "menu_placeholder": "Выберите раздел",
        "back": "⬅️ Вернуться",
        "home": "🏠 Главная",
        "search_sale": "🔎 Искать скидки",
        "sale": "Скидки:",
        "sell_placeholder": "Продать",
        "back_placeholder": "Назад",
        "nav_placeholder": "Навигация",
        "empty_cart": "Корзина пустая.",
        "your_orders": "Ваши заказы:",
        "no_orders": "У вас пока нет заказов.",
        "price": "Цена",
        "weight": "Вес",
        "sample": "Проба",
        "metal": "Металл",
        "status": "Статус",
        "production": "Производство",
        "model": "Модель",
        "in_stock": "В наличии",
        "out_of_stock": "Нет в наличии",
        "site": "Сайт ↗️",
        "in_cart": "✅ Уже в корзине",
        "remove_selection": "❌ Отменить выбор",
        "add_to_cart": "🛒 В корзину",
        "back_to_cart": "⬅️ Вернуться",
        "checkout": "Оформить",
        "cart_title": "Корзина",
        "cart_missing": "В корзине есть товары, которых уже нет в наличии.",
        "total": "Итого",
        "order": "Заказ",
        "items": "Товары",
        "item": "Товар",
        "phone": "Телефон",
        "region": "Город/область",
        "date": "Дата",
        "cancel_order": "❌ Отменить заказ",
        "back_to_items": "⬅️ Назад к товарам",
        "search": "🔎 Искать",
        "reset_filters": "❌ Сбросить фильтры",
        "no_values": "Пока нет значений",
        "filters": "Фильтры",
        "next": "Далее",
        "page_picker": "Выберите страницу:",
        "choose_category_first": "Сначала выберите категорию.",
        "search_result": "По вашему запросу {category}{filters} найдено: {total}",
        "shown": "Показано: {from_}-{to} из {total}",
        "order_items_title": "Товары заказа {order}:",
        "product_not_found": "Товар не найден",
        "order_not_found": "Заказ не найден",
        "media_not_found": "Медиа нет",
        "media_load_failed": "Не удалось загрузить медиа",
        "removed_from_cart": "Убрано из корзины",
        "checkout_contact": "Для оформления заявки отправьте, пожалуйста, контакт.",
        "checkout_started": "Оформляем заявку",
        "send_contact": "📱 Отправить контакт",
        "send_contact_placeholder": "Отправьте контакт",
        "select_region": "Выберите город или область:",
        "select_region_placeholder": "Выберите город/область",
        "no_media": "Фото/видео не найдено.",
        "enter_name": "Для оформления заявки введите ваше имя, пожалуйста.",
        "send_own_contact": "Отправьте, пожалуйста, свой контакт через кнопку ниже.",
        "send_location": "Укажите, пожалуйста, адрес доставки: отправьте геопозицию в Telegram.",
        "send_location_again": "Отправьте, пожалуйста, геопозицию Telegram, чтобы мы смогли оформить доставку.",
        "location_sent": "Геопозиция передана.",
        "check_cart": "Проверьте корзину и выберите другой товар.",
        "order_accepted": "Заявка {order} принята.",
        "manager_will_contact": "Менеджер скоро свяжется с вами.",
        "order_status_hint": "Статус заказа можно посмотреть в разделе {orders}.",
        "manager_not_notified": "Пока менеджерский бот не получил заявку, мы сохранили ее в базе.",
        "status_changed": "Статус вашего заказа {order} изменен: {status}.",
        "order_completed_thanks": "Спасибо за заказ! Будем рады видеть вас снова.",
        "review_request": "Если у вас будет минутка, оставьте, пожалуйста, отзыв о заказе.",
        "leave_review": "Оставить отзыв",
        "skip_review": "Пропустить",
        "review_later_hint": "Вы можете оставить отзыв позже в разделе «Заказы».",
        "review_prompt": "Напишите отзыв одним сообщением.",
        "review_saved": "Спасибо! Отзыв сохранен.",
        "review_exists": "Отзыв уже оставлен.",
        "review_unavailable": "Отзыв можно оставить после завершения заказа.",
        "review_for_product": "Оставить отзыв товару",
        "review": "Отзыв",
        "order_cancelled_notice": "Заказ {order} отменен. Если возникли вопросы, свяжитесь с оператором.",
        "order_cancelled_reason": "Ваш заказ {order} отменен.\nПричина: <i>{reason}</i>",
    },
    "uz": {
        "choose_language": "Tilni tanlang:",
        "language_saved": "Til tanlandi.",
        "start": "Salom! Bu Diamant boti. Bu yerda zargarlik buyumlarini xarid qilishingiz va sotishingiz mumkin.",
        "main_menu": "Asosiy menyu:",
        "buy": "💎 Xarid qilish",
        "sell": "🤝 Sotish",
        "cart": "🛒 Savat",
        "orders": "📦 Buyurtmalar",
        "contacts": "☎️ Biz bilan bog'lanish",
        "language": "🌐 Til",
        "catalog": "Katalog:",
        "catalog_placeholder": "Kategoriyani tanlang",
        "menu_placeholder": "Bo'limni tanlang",
        "back": "⬅️ Ortga",
        "home": "🏠 Asosiy",
        "search_sale": "🔎 Chegirmalarni qidirish",
        "sale": "Chegirmalar:",
        "sell_placeholder": "Sotish",
        "back_placeholder": "Ortga",
        "nav_placeholder": "Navigatsiya",
        "empty_cart": "Savat bo'sh.",
        "your_orders": "Buyurtmalaringiz:",
        "no_orders": "Sizda hozircha buyurtmalar yo'q.",
        "price": "Narx",
        "weight": "Vazn",
        "sample": "Proba",
        "metal": "Metall",
        "status": "Holati",
        "production": "Ishlab chiqarish",
        "model": "Model",
        "in_stock": "Mavjud",
        "out_of_stock": "Mavjud emas",
        "site": "Sayt ↗️",
        "in_cart": "✅ Savatda",
        "remove_selection": "❌ Tanlovni bekor qilish",
        "add_to_cart": "🛒 Savatga",
        "back_to_cart": "⬅️ Ortga",
        "checkout": "Rasmiylashtirish",
        "cart_title": "Savat",
        "cart_missing": "Savatda hozir mavjud bo'lmagan mahsulotlar bor.",
        "total": "Jami",
        "order": "Buyurtma",
        "items": "Mahsulotlar",
        "item": "Mahsulot",
        "phone": "Telefon",
        "region": "Shahar/viloyat",
        "date": "Sana",
        "cancel_order": "❌ Buyurtmani bekor qilish",
        "back_to_items": "⬅️ Mahsulotlarga qaytish",
        "search": "🔎 Qidirish",
        "reset_filters": "❌ Filtrlarni tozalash",
        "no_values": "Hozircha qiymatlar yo'q",
        "filters": "Filtrlar",
        "next": "Keyingi",
        "page_picker": "Sahifani tanlang:",
        "choose_category_first": "Avval kategoriyani tanlang.",
        "search_result": "So'rovingiz bo'yicha {category}{filters} topildi: {total}",
        "shown": "Ko'rsatildi: {from_}-{to} / {total}",
        "order_items_title": "{order}-buyurtma mahsulotlari:",
        "product_not_found": "Mahsulot topilmadi",
        "order_not_found": "Buyurtma topilmadi",
        "media_not_found": "Media yo'q",
        "media_load_failed": "Medianini yuklab bo'lmadi",
        "removed_from_cart": "Savatdan olindi",
        "checkout_contact": "Buyurtmani rasmiylashtirish uchun kontaktingizni yuboring.",
        "checkout_started": "Buyurtma rasmiylashtirilmoqda",
        "send_contact": "📱 Kontakt yuborish",
        "send_contact_placeholder": "Kontakt yuboring",
        "select_region": "Shahar yoki viloyatni tanlang:",
        "select_region_placeholder": "Shahar/viloyatni tanlang",
        "no_media": "Foto/video topilmadi.",
        "enter_name": "Buyurtmani rasmiylashtirish uchun ismingizni kiriting.",
        "send_own_contact": "Iltimos, quyidagi tugma orqali o'z kontaktingizni yuboring.",
        "send_location": "Yetkazib berish manzilini ko'rsating: Telegram orqali geolokatsiya yuboring.",
        "send_location_again": "Yetkazib berishni rasmiylashtirish uchun Telegram geolokatsiyasini yuboring.",
        "location_sent": "Geolokatsiya yuborildi.",
        "check_cart": "Savatni tekshirib, boshqa mahsulot tanlang.",
        "order_accepted": "{order}-raqamli buyurtma qabul qilindi.",
        "manager_will_contact": "Menejer tez orada siz bilan bog'lanadi.",
        "order_status_hint": "Buyurtma holatini {orders} bo'limida ko'rishingiz mumkin.",
        "manager_not_notified": "Menejer boti hozircha xabarni olmadi, buyurtma bazada saqlandi.",
        "status_changed": "{order}-buyurtma holati o'zgardi: {status}.",
        "order_completed_thanks": "Buyurtmangiz uchun rahmat! Sizni yana kutib qolamiz.",
        "review_request": "Vaqtingiz bo'lsa, buyurtma haqida fikr qoldiring.",
        "leave_review": "Fikr qoldirish",
        "skip_review": "O'tkazib yuborish",
        "review_later_hint": "Fikrni keyinroq «Buyurtmalar» bo'limida qoldirishingiz mumkin.",
        "review_prompt": "Fikringizni bitta xabarda yozing.",
        "review_saved": "Rahmat! Fikringiz saqlandi.",
        "review_exists": "Fikr allaqachon qoldirilgan.",
        "review_unavailable": "Fikrni buyurtma yakunlangandan keyin qoldirish mumkin.",
        "review_for_product": "Tovarga fikr qoldirish",
        "review": "Fikr",
        "order_cancelled_notice": "{order}-buyurtma bekor qilindi. Savollar bo'lsa, operator bilan bog'laning.",
        "order_cancelled_reason": "{order}-buyurtma bekor qilindi.\nSabab: <i>{reason}</i>",
    },
}
ORDER_STATUS_I18N = {
    "ru": TG_ORDER_STATUSES,
    "uz": {
        "new": "Kutilmoqda",
        "pending": "Kutilmoqda",
        "processing": "Jarayonda",
        "in_transit": "Yo'lda",
        "completed": "Yakunlandi",
        "cancelled": "Bekor qilindi",
        "accepted": "Jarayonda",
        "contacted": "Jarayonda",
        "done": "Yakunlandi",
        "completed_success": "Yakunlandi",
        "completed_failed": "Bekor qilindi",
    },
}
CATEGORY_LABELS_I18N = {
    "ru": {
        "sale": "🏷️ Скидки",
        "watch": "⌚ Часы",
        "ring": "💍 Кольца",
        "earring": "✨ Серьги",
        "chain": "🔗 Цепочки",
        "bracelet": "📿 Браслеты",
        "pendant": "💎 Подвески",
        "necklace": "📿 Колье",
        "set": "🎁 Комплекты",
        "case": "📦 Футляры",
    },
    "uz": {
        "sale": "🏷️ Chegirmalar",
        "watch": "⌚ Soatlar",
        "ring": "💍 Uzuklar",
        "earring": "✨ Sirg'alar",
        "chain": "🔗 Zanjirlar",
        "bracelet": "📿 Bilaguzuklar",
        "pendant": "💎 Kulonlar",
        "necklace": "📿 Marjonlar",
        "set": "🎁 To'plamlar",
        "case": "📦 Qutilar",
    },
}
BUTTON_CATEGORY_LABELS = {
    "sale": "🏷️ Скидки",
    "watch": "⌚ Часы",
    "ring": "💍 Кольца",
    "earring": "✨ Серьги",
    "chain": "🔗 Цепочки",
    "bracelet": "📿 Браслеты",
    "pendant": "💎 Подвески",
    "necklace": "📿 Колье",
    "set": "🎁 Комплекты",
    "case": "📦 Футляры",
}
SELL_PRICE_BUTTONS = [
    ("583 проба", "930 000 - 1 500 000 сум/гр"),
    ("585 проба", "930 000 - 1 050 000 сум/гр"),
    ("750 проба", "1 190 000 - 1 500 000 сум/гр"),
    ("850 проба", "1 350 000 - 1 450 000 сум/гр"),
    ("875 проба", "1 390 000 - 1 500 000 сум/гр"),
    ("916 проба", "1 460 000 - 1 600 000 сум/гр"),
    ("Золотые коронки", "1 310 000 - 1 450 000 сум/гр"),
    ("999 проба", "1 590 000 - 1 700 000 сум/гр"),
]
SELL_PRICE_IMAGE_TITLE = "Цены на золото"
SELL_PRICE_IMAGE_PHONE = "+998 55 055 00 02"
SELL_PRICE_RENDER_VERSION = 2
SELL_PRICE_LOGO_PATH = Path(__file__).with_name("assets") / "diamantsk.png"
SELL_PRICE_CACHE_DIR = Path(__file__).with_name("cache")
SELL_PRICE_GENERATED_ROOT = os.getenv("SELL_PRICE_GENERATED_ROOT", "").strip()
SELL_PRICE_IMAGE_TEXTS = {
    "ru": {
        "title": "ЦЕНА ЗА 1 ГРАММ ЗОЛОТА",
        "sample": "ПРОБА",
        "crowns": "КОРОНКИ",
        "currency": "СУМ",
        "caption": "Актуальные цены на скупку золота.",
    },
    "uz": {
        "title": "1 GRAMM OLTIN NARXI",
        "sample": "PROBA",
        "crowns": "TILLA KORONKA",
        "currency": "SO'M",
        "caption": "Oltinni sotish uchun amaldagi narxlar.",
    },
}
FONT_REGULAR_PATH = Path(__file__).with_name("assets") / "NotoSans-Regular.ttf"
FONT_BOLD_PATH = Path(__file__).with_name("assets") / "NotoSans-Bold.ttf"
FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("C:/Windows/Fonts/segoeuib.ttf"),
]
USER_LANGS_PATH = Path(__file__).with_name("user_langs.json")

CATEGORY_CONFIG = {
    "sale": {"title": "Скидки", "category_id": 253, "filters": [], "sale": True},
    "watch": {"title": "Часы", "category_id": 266, "filters": ["brand", "mechanism", "gender", "dial"]},
    "ring": {"title": "Кольца", "category_id": 59, "filters": ["gender", "size", "sample", "metal"]},
    "earring": {"title": "Серьги", "category_id": 107, "filters": ["gender", "sample", "metal"]},
    "chain": {"title": "Цепочки", "category_id": 229, "filters": ["gender", "length", "sample", "metal"]},
    "bracelet": {"title": "Браслеты", "category_id": 69, "filters": ["gender", "size", "sample", "metal"]},
    "pendant": {"title": "Подвески", "category_id": 175, "filters": ["gender", "sample", "stone"]},
    "necklace": {"title": "Колье", "category_id": 230, "filters": ["gender", "sample", "metal"]},
    "set": {"title": "Комплекты", "category_id": 111, "filters": ["gender", "size", "sample", "metal", "stone"]},
    "case": {"title": "Футляры", "category_id": 223, "filters": []},
}

CATEGORY_EMOJI = {
    "sale": "🏷️",
    "watch": "🌟",
    "ring": "🌟",
    "earring": "🌟",
    "chain": "🔗",
    "bracelet": "🌟",
    "pendant": "🌟",
    "necklace": "📿",
    "set": "🌟",
    "case": "🌟",
}
CUSTOM_CATEGORY_EMOJI_ID = {
    "ring": os.getenv("RING_CUSTOM_EMOJI_ID", "5240102693757819176"),
    "watch": "5240362998840728302",
    "case": "5237813858441143252",
    "earring": "5240291766808124689",
    "bracelet": "5240369127759060905",
    "pendant": "5240390615480441431",
    "set": "5240106000882637326",
}
CUSTOM_COUNTRY_FLAG_EMOJI_ID = {
    "узбекистан": "5244542530300712759",
    "азербайджан": "5244945479837455484",
    "украина": "5244569640134286094",
    "армения": "5245004604357252686",
    "китай": "5247122310996989758",
    "италия": "5246878081976670048",
    "оаэ": "5246965106604022374",
}
PRODUCT_TOP_STARS_HTML = (
    '<tg-emoji emoji-id="5237827147069955120">🌟</tg-emoji>'
    '<tg-emoji emoji-id="5237827147069955120">🌟</tg-emoji>'
    '<tg-emoji emoji-id="5237827147069955120">🌟</tg-emoji>'
    '<tg-emoji emoji-id="5247118784828842357">🌟</tg-emoji>'
    '<tg-emoji emoji-id="5247234529902500703">🌟</tg-emoji>'
    '<tg-emoji emoji-id="5247218475314747190">🌟</tg-emoji>'
    '<tg-emoji emoji-id="5247072051289693699">🌟</tg-emoji>'
    '<tg-emoji emoji-id="5237827147069955120">🌟</tg-emoji>'
    '<tg-emoji emoji-id="5237827147069955120">🌟</tg-emoji>'
    '<tg-emoji emoji-id="5237827147069955120">🌟</tg-emoji>'
)
IN_STOCK_EMOJI_HTML = '<tg-emoji emoji-id="5244781390611912987">✅</tg-emoji>'
OUT_OF_STOCK_EMOJI_HTML = '<tg-emoji emoji-id="5246907545452320852">❌</tg-emoji>'

SALE_CATEGORY_KEYS = ["ring", "earring", "chain", "bracelet", "pendant", "necklace", "set"]
CATEGORY_TITLE_TO_KEY = {config["title"]: key for key, config in CATEGORY_CONFIG.items()}
BUY_TEXTS = {"💎 Купить", "Купить", "Каталог", "💎 Xarid qilish", "Xarid qilish", "Katalog"}
SELL_TEXTS = {"🤝 Продать", "Продать", "🤝 Sotish", "Sotish"}
CONTACT_TEXTS = {"☎️ Связаться с нами", "Связаться с нами", "📲 Контакты", "Контакты", "Связь", "☎️ Biz bilan bog'lanish", "Biz bilan bog'lanish", "Aloqa"}
CART_TEXTS = {CART_TEXT, "🛒 Savat", "Savat"}
ORDER_TEXTS = {MY_ORDERS_TEXT, "📦 Buyurtmalar", "Buyurtmalar"}
LANGUAGE_TEXTS = {"🌐 Язык", "Язык", "🌐 Til", "Til"}
HOME_TEXTS = {"🏠 Главная", "Главная", "🏠 Asosiy", "Asosiy"}
BACK_TEXTS = {"⬅️ Вернуться", "Вернуться", "⬅️ Ortga", "Ortga"}
SALE_TEXTS = {"🏷️ Скидки", "Скидки", "🏷️ Chegirmalar", "Chegirmalar"}
SALE_SEARCH_TEXTS = {"🔎 Искать скидки", "Искать скидки", "🔎 Chegirmalarni qidirish", "Chegirmalarni qidirish"}
CATEGORY_TEXT_TO_KEY = {}
for _lang, _labels in CATEGORY_LABELS_I18N.items():
    for _key, _label in _labels.items():
        CATEGORY_TEXT_TO_KEY[_label] = _key
        CATEGORY_TEXT_TO_KEY[_label.split(" ", 1)[-1]] = _key

FILTER_CONFIG = {
    "brand": {"title": "Бренд", "type": "manufacturer"},
    "mechanism": {"title": "Тип механизма", "type": "manual", "values": [("mech", "Механические"), ("auto", "Автоматические")]},
    "gender": {"title": "Кому", "type": "filter_group", "group": "Пол"},
    "dial": {"title": "Циферблат (мм)", "type": "manual", "values": [("36", "36"), ("40", "40"), ("44", "44")]},
    "size": {"title": "Размер", "type": "filter_group", "group": "Размер"},
    "sample": {"title": "Проба", "type": "filter_group", "group": "Проба"},
    "metal": {"title": "Металл", "type": "manual", "values": [("gold", "Золото"), ("silver", "Серебро")]},
    "length": {"title": "Длина", "type": "manual", "values": []},
    "stone": {"title": "Вставка", "type": "filter_group", "group": "Вставка"},
}
FILTER_TITLE_I18N = {
    "ru": {
        "brand": "Бренд",
        "mechanism": "Тип механизма",
        "gender": "Кому",
        "dial": "Циферблат (мм)",
        "size": "Размер изделия",
        "sample": "Проба",
        "metal": "Металл",
        "length": "Длина",
        "stone": "Вставка",
    },
    "uz": {
        "brand": "Brend",
        "mechanism": "Mexanizm turi",
        "gender": "Kim uchun",
        "dial": "Siferblat (mm)",
        "size": "Buyum o'lchami",
        "sample": "Proba",
        "metal": "Metall",
        "length": "Uzunlik",
        "stone": "Tosh",
    },
}
FILTER_VALUE_I18N = {
    "uz": {
        "Золото": "Tilla",
        "Серебро": "Kumush",
        "Механические": "Mexanik",
        "Автоматические": "Avtomatik",
        "Мужские": "Erkaklar",
        "Женские": "Ayollar",
        "Детские": "Bolalar",
        "Детям": "Bolalar",
        "Унисекс": "Uniseks",
        "Юнисекс": "Uniseks",
    }
}
FILTER_TITLE_TO_KEY = {}
for _key, _config in FILTER_CONFIG.items():
    FILTER_TITLE_TO_KEY[_config["title"]] = _key
for _labels in FILTER_TITLE_I18N.values():
    for _key, _title in _labels.items():
        FILTER_TITLE_TO_KEY[_title] = _key


def is_placeholder_or_cache(image):
    normalized = (image or "").replace("\\", "/").lower()
    return (
        not normalized
        or "no_image" in normalized
        or normalized.startswith("cache/")
        or normalized.startswith("image/cache/")
    )


def original_image_path(image):
    image = (image or "").replace("\\", "/").lstrip("/")
    if image.startswith("image/"):
        image = image[len("image/") :]

    if image.startswith("cache/catalog/"):
        image = "catalog/" + image[len("cache/catalog/") :]
        stem = Path(image).stem
        suffix = Path(image).suffix
        parent = str(Path(image).parent).replace("\\", "/")
        parts = stem.rsplit("-", 1)
        if len(parts) == 2 and "x" in parts[1] and parts[1].replace("x", "").isdigit():
            image = f"{parent}/{parts[0]}{suffix}"

    return image


class MySQLConnectionPool:
    def __init__(self, config, size=5):
        self._config = dict(config)
        self._size = max(1, int(size))
        self._connections = queue.LifoQueue(maxsize=self._size)
        self._lock = threading.Lock()
        self._created = 0
        self._closed = False

    def _create_connection(self):
        try:
            return pymysql.connect(**self._config)
        except Exception:
            with self._lock:
                self._created = max(0, self._created - 1)
            raise

    def acquire(self):
        try:
            connection = self._connections.get_nowait()
        except queue.Empty:
            connection = None

        if connection is None:
            with self._lock:
                if self._closed:
                    raise RuntimeError("MySQL connection pool is closed")
                if self._created < self._size:
                    self._created += 1
                    create_connection = True
                else:
                    create_connection = False

            if create_connection:
                connection = self._create_connection()
            else:
                connection = self._connections.get()

        with self._lock:
            closed = self._closed
        if closed:
            self.discard(connection)
            raise RuntimeError("MySQL connection pool is closed")

        try:
            connection.ping(reconnect=True)
            return connection
        except Exception:
            self.discard(connection)
            raise

    def release(self, connection):
        with self._lock:
            closed = self._closed
        if closed:
            self.discard(connection)
            return
        try:
            self._connections.put_nowait(connection)
        except queue.Full:
            self.discard(connection)

    def discard(self, connection):
        try:
            connection.close()
        except Exception:
            pass
        with self._lock:
            self._created = max(0, self._created - 1)

    @contextmanager
    def connection(self):
        connection = self.acquire()
        broken = False
        try:
            yield connection
        except (pymysql.err.InterfaceError, pymysql.err.OperationalError):
            broken = True
            raise
        finally:
            if broken:
                self.discard(connection)
            else:
                self.release(connection)

    def close(self):
        with self._lock:
            self._closed = True
        while True:
            try:
                connection = self._connections.get_nowait()
            except queue.Empty:
                break
            self.discard(connection)


DB_POOL = MySQLConnectionPool(DB_CONFIG, DB_POOL_SIZE)


def db_query(sql, params=None):
    try:
        with DB_POOL.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or ())
                return cursor.fetchall()
    except Exception:
        logger.exception("MySQL query failed")
        raise


def db_execute(sql, params=None):
    try:
        with DB_POOL.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or ())
                return cursor.lastrowid
    except Exception:
        logger.exception("MySQL execute failed")
        raise


def db_rowcount(sql, params=None):
    try:
        with DB_POOL.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or ())
                return cursor.rowcount
    except Exception:
        logger.exception("MySQL row-count query failed")
        raise


def ensure_tg_orders_table():
    try:
        db_query("SELECT 1 FROM tg_orders LIMIT 1")
        columns = {
            row["Field"]
            for row in db_query("SHOW COLUMNS FROM tg_orders")
        }
        if "delivery_lat" not in columns:
            db_execute("ALTER TABLE tg_orders ADD COLUMN delivery_lat DECIMAL(10, 8) NULL AFTER region")
        if "delivery_lng" not in columns:
            db_execute("ALTER TABLE tg_orders ADD COLUMN delivery_lng DECIMAL(11, 8) NULL AFTER delivery_lat")
        if "customer_name" not in columns:
            db_execute("ALTER TABLE tg_orders ADD COLUMN customer_name VARCHAR(255) NOT NULL DEFAULT '' AFTER last_name")
        if "client_review" not in columns:
            db_execute("ALTER TABLE tg_orders ADD COLUMN client_review TEXT NULL AFTER manager_username")
        if "client_review_at" not in columns:
            db_execute("ALTER TABLE tg_orders ADD COLUMN client_review_at DATETIME NULL AFTER client_review")
    except Exception:
        pass


def ensure_tg_cart_table():
    try:
        db_query("SELECT 1 FROM tg_cart_items LIMIT 1")
    except Exception:
        pass


def ensure_tg_order_items_table():
    try:
        db_query("SELECT 1 FROM tg_order_items LIMIT 1")
    except Exception:
        pass


def ensure_tg_order_reviews_table():
    try:
        db_execute(
            """
            CREATE TABLE IF NOT EXISTS tg_order_reviews (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_code VARCHAR(64) NOT NULL,
                product_id INT NOT NULL,
                client_tg_id BIGINT NOT NULL,
                review_text TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                UNIQUE KEY uniq_order_product_review (order_code, product_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    except Exception:
        pass


def ensure_manager_access_claim_columns():
    try:
        columns = {row["Field"] for row in db_query("SHOW COLUMNS FROM tg_manager_access")}
        if "serviced_by" not in columns:
            db_execute("ALTER TABLE tg_manager_access ADD COLUMN serviced_by BIGINT NULL AFTER requested_at")
        if "serviced_name" not in columns:
            db_execute("ALTER TABLE tg_manager_access ADD COLUMN serviced_name VARCHAR(255) NULL AFTER serviced_by")
        if "serviced_at" not in columns:
            db_execute("ALTER TABLE tg_manager_access ADD COLUMN serviced_at DATETIME NULL AFTER serviced_name")
    except Exception:
        pass


def walk_json_strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_json_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json_strings(child)
    elif isinstance(value, str):
        yield value


def normalize_sell_title(raw_title):
    title = re.sub(r"<[^>]+>", " ", raw_title or "")
    title = " ".join(html.unescape(title).split())
    sample_match = re.search(r"(\d+)\s*ПРОБА", title, re.IGNORECASE)
    if sample_match:
        return f"{sample_match.group(1)} проба"
    if "КОРОНК" in title.upper():
        return "Золотые коронки"
    return title.capitalize()


def extract_sell_prices_from_html(raw_html):
    raw_html = (raw_html or "").replace("[~nl~]", "\n")
    prices = []
    for block in re.findall(r'<a[^>]*class="[^"]*prices-item[^"]*"[\s\S]*?</a>', raw_html):
        title_match = re.search(r'<div class="prices-item-title">([\s\S]*?)</div>', block)
        price_match = re.search(r'<div class="prices-item-price">([\s\S]*?)</div>', block)
        if not title_match or not price_match:
            continue
        title = normalize_sell_title(title_match.group(1))
        price = " ".join(re.sub(r"<[^>]+>", " ", price_match.group(1)).split())
        if title and price:
            prices.append((title, price))
    return prices


def get_sell_price_buttons():
    try:
        rows = db_query(
            """
            SELECT module_data
            FROM ocoe_journal3_module
            WHERE module_name = 'Landing Gold'
              AND module_data LIKE %s
            ORDER BY module_id DESC
            LIMIT 1
            """,
            ("%prices-item%",),
        )
        if rows:
            data = json.loads(rows[0]["module_data"])
            for text in walk_json_strings(data):
                if "prices-item" not in text:
                    continue
                prices = extract_sell_prices_from_html(text)
                if prices:
                    return prices
    except Exception:
        pass
    return SELL_PRICE_BUTTONS


def load_font(size, bold=False):
    bundled_font = FONT_BOLD_PATH if bold else FONT_REGULAR_PATH
    if bundled_font.exists():
        return ImageFont.truetype(str(bundled_font), size=size)
    names = ["arialbd.ttf", "segoeuib.ttf"] if bold else ["arial.ttf", "segoeui.ttf"]
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    for path in FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def fit_text(draw, text, font, max_width):
    text = str(text)
    if draw.textlength(text, font=font) <= max_width:
        return text
    ellipsis = "..."
    while text and draw.textlength(text + ellipsis, font=font) > max_width:
        text = text[:-1]
    return text + ellipsis if text else ellipsis


def format_sell_price_for_image(price, lang="ru"):
    price = str(price or "").replace("сум/гр", "").replace("сум", "").strip()
    price = re.sub(r"\s*[-–—]\s*", "-", price)

    def format_number(match):
        digits = match.group(0).replace(" ", "")
        if len(digits) <= 3:
            return digits
        groups = []
        while digits:
            groups.append(digits[-3:])
            digits = digits[:-3]
        return ".".join(reversed(groups))

    currency = SELL_PRICE_IMAGE_TEXTS.get(lang, SELL_PRICE_IMAGE_TEXTS["ru"])["currency"]
    return re.sub(r"\d[\d\s]*\d|\d", format_number, price) + " " + currency


def sell_prices_hash(prices, lang="ru"):
    texts = SELL_PRICE_IMAGE_TEXTS.get(lang, SELL_PRICE_IMAGE_TEXTS["ru"])
    font_signature = []
    for path in (FONT_REGULAR_PATH, FONT_BOLD_PATH):
        font_signature.append((path.name, path.stat().st_size if path.exists() else 0))
    payload = json.dumps(
        {
            "prices": prices or [],
            "fonts": font_signature,
            "phone": SELL_PRICE_IMAGE_PHONE,
            "render_version": SELL_PRICE_RENDER_VERSION,
            "lang": lang,
            "texts": texts,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_cached_sell_price_image(prices, lang="ru"):
    lang = lang if lang in SELL_PRICE_IMAGE_TEXTS else "ru"
    prices = prices or SELL_PRICE_BUTTONS
    cache_path = SELL_PRICE_CACHE_DIR / f"sell_prices_{lang}.png"
    meta_path = SELL_PRICE_CACHE_DIR / f"sell_prices_{lang}.json"
    current_hash = sell_prices_hash(prices, lang)
    if cache_path.exists() and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("prices_hash") == current_hash:
                return cache_path.read_bytes()
        except Exception:
            pass

    image = build_sell_price_image(prices, lang)
    SELL_PRICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(image)
    meta_path.write_text(
        json.dumps(
            {
                "prices_hash": current_hash,
                "lang": lang,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "prices": prices,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return image


def find_latest_generated_diamant_sell_price_image():
    bot_dir = Path(__file__).resolve().parent
    generated_root = Path(SELL_PRICE_GENERATED_ROOT).expanduser() if SELL_PRICE_GENERATED_ROOT else (
        bot_dir.parent / "kurs_update" / "cache" / "generated"
    )
    try:
        generated_root = generated_root.resolve()
    except OSError:
        return None
    if not generated_root.is_dir():
        return None

    try:
        subdirs = [path for path in generated_root.iterdir() if path.is_dir()]
    except OSError as exc:
        logger.warning("Cannot read generated sell price directory %s: %s", generated_root, exc)
        return None

    for folder in sorted(subdirs, key=lambda path: path.stat().st_mtime_ns, reverse=True):
        try:
            matches = sorted(
                [
                    path for path in folder.iterdir()
                    if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
                    and path.name.lower().startswith("diamant")
                    and path.stat().st_size > 0
                ],
                key=lambda path: path.stat().st_mtime_ns,
                reverse=True,
            )
        except OSError:
            continue
        if matches:
            return matches[0]
    return None


def build_sell_price_image(prices, lang="ru"):
    lang = lang if lang in SELL_PRICE_IMAGE_TEXTS else "ru"
    texts = SELL_PRICE_IMAGE_TEXTS[lang]
    prices = [
        (sample, price)
        for sample, price in (prices or SELL_PRICE_BUTTONS)
        if "КОРОН" not in str(sample or "").upper()
    ]
    width = 904
    height = 1280
    red = "#d52b24"
    dark = "#050505"
    white = "#ffffff"

    image = Image.new("RGB", (width, height), white)
    draw = ImageDraw.Draw(image)

    frame_x = 70
    top_line = 70
    bottom_line = height - 72
    draw.line((frame_x, 0, frame_x, height), fill=red, width=5)
    draw.line((width - frame_x, 0, width - frame_x, height), fill=red, width=5)
    draw.line((0, top_line, width, top_line), fill=red, width=5)
    draw.line((0, bottom_line, width, bottom_line), fill=red, width=5)

    if SELL_PRICE_LOGO_PATH.exists():
        logo = Image.open(SELL_PRICE_LOGO_PATH).convert("RGBA")
        logo_w = 640
        logo_h = int(logo.height * (logo_w / logo.width))
        logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
        image.paste(logo, ((width - logo_w) // 2, 108), logo)

    date_font = load_font(34, bold=True)
    title_font = load_font(36, bold=True)
    sample_font = load_font(36, bold=True)
    price_font = load_font(32, bold=True)
    phone_font = load_font(46, bold=True)

    date_text = datetime.now().strftime("%d.%m.%Y")
    date_w = draw.textlength(date_text, font=date_font)
    draw.text(((width - date_w) / 2, 260), date_text, font=date_font, fill=dark)

    title = texts["title"]
    title_w = draw.textlength(title, font=title_font)
    draw.text(((width - title_w) / 2, 312), title, font=title_font, fill=dark)

    left_x = 94
    right_x = 424
    y = 415
    row_h = 72
    for sample, price in prices:
        sample_text = str(sample or "").upper()
        sample_number = re.search(r"\d+", sample_text)
        if sample_number:
            sample_text = f"{sample_number.group(0)} {texts['sample']}"
        price_text = format_sell_price_for_image(price, lang)
        sample_text = fit_text(draw, sample_text, sample_font, 300)
        price_text = fit_text(draw, price_text, price_font, width - right_x - 90)
        draw.text((left_x, y), sample_text, font=sample_font, fill=dark)
        draw.text((right_x, y + 3), price_text, font=price_font, fill=dark)
        y += row_h

    phone_text = SELL_PRICE_IMAGE_PHONE
    phone_w = draw.textlength(phone_text, font=phone_font)
    draw.text(((width - phone_w) / 2, height - 150), phone_text, font=phone_font, fill=dark)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output.getvalue()


async def send_sell_prices_image(message: Message):
    lang = user_lang(message.from_user.id)
    texts = SELL_PRICE_IMAGE_TEXTS.get(lang, SELL_PRICE_IMAGE_TEXTS["ru"])
    generated_image = find_latest_generated_diamant_sell_price_image()
    if generated_image:
        photo = FSInputFile(generated_image, filename=generated_image.name)
    else:
        prices = get_sell_price_buttons()
        image = get_cached_sell_price_image(prices, lang)
        photo = BufferedInputFile(image, filename=f"diamant_sell_prices_{lang}.png")
    await message.answer_photo(
        photo,
        caption=texts["caption"],
        reply_markup=sell_keyboard(message.from_user.id),
    )


def user_lang(user_id):
    return USER_LANGS.get(int(user_id or 0), "ru")


def load_user_langs():
    if not USER_LANGS_PATH.exists():
        return
    try:
        data = json.loads(USER_LANGS_PATH.read_text(encoding="utf-8"))
        USER_LANGS.update({int(user_id): lang for user_id, lang in data.items() if lang in LANG_TEXTS})
    except Exception:
        pass


def save_user_langs():
    try:
        USER_LANGS_PATH.write_text(
            json.dumps({str(user_id): lang for user_id, lang in USER_LANGS.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def normalize_phone(value):
    return re.sub(r"\D+", "", str(value or ""))


def manager_chat_targets_from_env():
    targets = set()
    for raw_id in re.split(r"[,\s]+", MANAGER_CHAT_ID or ""):
        raw_id = raw_id.strip()
        if raw_id:
            targets.add(raw_id)
    return sorted(targets)


def manager_access_data():
    try:
        users = {}
        pending = {}
        for row in db_query(
            """
            SELECT chat_id, role, username, first_name, last_name, display_name, phone, status,
                   requested_at, serviced_by, serviced_name, serviced_at
            FROM tg_manager_access
            """
        ):
            record = {
                "role": row.get("role") or "viewer",
                "username": row.get("username") or "",
                "first_name": row.get("first_name") or "",
                "last_name": row.get("last_name") or "",
                "display_name": row.get("display_name") or "",
                "phone": row.get("phone") or "",
                "requested_at": str(row.get("requested_at") or ""),
                "serviced_by": str(row.get("serviced_by") or ""),
                "serviced_name": row.get("serviced_name") or "",
                "serviced_at": str(row.get("serviced_at") or ""),
            }
            if row.get("status") == "active":
                users[str(row["chat_id"])] = record
            elif row.get("status") == "pending":
                pending[str(row["chat_id"])] = record
        logs = [
            {
                "created_at": str(row.get("created_at") or ""),
                "action": row.get("action") or "",
                "actor_id": str(row.get("actor_id") or ""),
                "target_id": str(row.get("target_id") or ""),
                "details": row.get("details") or "",
            }
            for row in db_query(
                """
                SELECT created_at, action, actor_id, target_id, details
                FROM tg_manager_logs
                ORDER BY id DESC
                LIMIT 300
                """
            )
        ]
        remarks = [
            {
                "created_at": str(row.get("created_at") or ""),
                "actor_id": str(row.get("actor_id") or ""),
                "target_id": str(row.get("target_id") or ""),
                "text": row.get("remark_text") or "",
            }
            for row in db_query(
                """
                SELECT created_at, actor_id, target_id, remark_text
                FROM tg_manager_remarks
                ORDER BY id DESC
                LIMIT 300
                """
            )
        ]
        return {"users": users, "pending": pending, "logs": list(reversed(logs)), "remarks": list(reversed(remarks))}
    except Exception:
        pass
    try:
        if MANAGER_ACCESS_PATH.exists():
            data = json.loads(MANAGER_ACCESS_PATH.read_text(encoding="utf-8"))
        else:
            data = {}
    except Exception:
        data = {}
    data.setdefault("users", {})
    data.setdefault("pending", {})
    data.setdefault("logs", [])
    data.setdefault("remarks", [])
    return data


def save_manager_access_data(data):
    try:
        db_execute("DELETE FROM tg_manager_access")
        for chat_id, record in data.get("users", {}).items():
            db_execute(
                """
                INSERT INTO tg_manager_access
                SET chat_id = %s,
                    role = %s,
                    username = %s,
                    first_name = %s,
                    last_name = %s,
                    display_name = %s,
                    phone = %s,
                    status = 'active',
                    requested_at = %s,
                    serviced_by = NULL,
                    serviced_name = NULL,
                    serviced_at = NULL,
                    approved_by = NULL,
                    approved_at = NOW(),
                    updated_at = NOW()
                """,
                (
                    int(chat_id),
                    record.get("role") or "viewer",
                    record.get("username") or "",
                    record.get("first_name") or "",
                    record.get("last_name") or "",
                    record.get("display_name") or "",
                    record.get("phone") or "",
                    record.get("requested_at") or None,
                ),
            )
        for chat_id, record in data.get("pending", {}).items():
            db_execute(
                """
                INSERT INTO tg_manager_access
                SET chat_id = %s,
                    role = %s,
                    username = %s,
                    first_name = %s,
                    last_name = %s,
                    display_name = %s,
                    phone = %s,
                    status = 'pending',
                    requested_at = %s,
                    serviced_by = %s,
                    serviced_name = %s,
                    serviced_at = %s,
                    approved_by = NULL,
                    approved_at = NULL,
                    updated_at = NOW()
                """,
                (
                    int(chat_id),
                    record.get("role") or "viewer",
                    record.get("username") or "",
                    record.get("first_name") or "",
                    record.get("last_name") or "",
                    record.get("display_name") or "",
                    record.get("phone") or "",
                    record.get("requested_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    int(record["serviced_by"]) if str(record.get("serviced_by") or "").isdigit() else None,
                    record.get("serviced_name") or None,
                    record.get("serviced_at") or None,
                ),
            )
        db_execute("DELETE FROM tg_manager_logs")
        for log in data.get("logs", [])[-300:]:
            db_execute(
                """
                INSERT INTO tg_manager_logs (created_at, action, actor_id, target_id, details)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    log.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    log.get("action") or "",
                    int(log["actor_id"]) if str(log.get("actor_id") or "").isdigit() else None,
                    str(log.get("target_id") or ""),
                    log.get("details") or "",
                ),
            )
        db_execute("DELETE FROM tg_manager_remarks")
        for remark in data.get("remarks", [])[-300:]:
            db_execute(
                """
                INSERT INTO tg_manager_remarks (created_at, actor_id, target_id, remark_text)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    remark.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    int(remark.get("actor_id") or 0),
                    int(remark.get("target_id") or 0),
                    remark.get("text") or "",
                ),
            )
        try:
            MANAGER_ACCESS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return True
    except Exception:
        pass
    try:
        MANAGER_ACCESS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def seed_env_managers(data):
    changed = False
    for chat_id in ADMIN_MANAGER_IDS:
        record = data["users"].setdefault(str(chat_id), {})
        if record.get("role") != "admin":
            record["role"] = "admin"
            changed = True
    for chat_id in manager_chat_targets_from_env():
        record = data["users"].setdefault(str(chat_id), {})
        if not record.get("role"):
            record["role"] = "manager"
            changed = True
    if changed:
        save_manager_access_data(data)
    return data


def manager_role(chat_id):
    data = seed_env_managers(manager_access_data())
    return data.get("users", {}).get(str(chat_id), {}).get("role")


def manager_has_access(chat_id):
    return manager_role(chat_id) in {"viewer", "manager", "admin"}


def manager_can_manage(chat_id):
    return manager_role(chat_id) in {"manager", "admin"}


def manager_is_admin(chat_id):
    return manager_role(chat_id) == "admin"


def set_manager_role(chat_id, role, user=None):
    data = seed_env_managers(manager_access_data())
    chat_id = str(chat_id)
    pending_record = data.get("pending", {}).get(chat_id, {})
    record = data["users"].setdefault(chat_id, {})
    if chat_id in ADMIN_MANAGER_IDS:
        role = "admin"
    record["role"] = role
    for key in ("username", "first_name", "last_name", "display_name", "phone", "requested_at"):
        if pending_record.get(key) and not record.get(key):
            record[key] = pending_record.get(key)
    if user:
        record["username"] = user.username or record.get("username") or ""
        record["first_name"] = user.first_name or record.get("first_name") or ""
        record["last_name"] = user.last_name or record.get("last_name") or ""
    data.get("pending", {}).pop(chat_id, None)
    save_manager_access_data(data)


def register_manager_pending(user):
    data = seed_env_managers(manager_access_data())
    chat_id = str(user.id)
    if data.get("users", {}).get(chat_id, {}).get("role"):
        return False
    data["pending"][chat_id] = {
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "display_name": manager_user_label(user),
        "phone": "",
        "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_manager_access_data(data)
    return True


def append_manager_log(action, actor_id=None, target_id=None, details=None):
    data = seed_env_managers(manager_access_data())
    data.setdefault("logs", []).append(
        {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "actor_id": str(actor_id or ""),
            "target_id": str(target_id or ""),
            "details": details or "",
        }
    )
    data["logs"] = data["logs"][-300:]
    save_manager_access_data(data)


def append_manager_remark(actor_id, target_id, text):
    data = seed_env_managers(manager_access_data())
    remark = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "actor_id": str(actor_id),
        "target_id": str(target_id),
        "text": text,
    }
    data.setdefault("remarks", []).append(remark)
    data["remarks"] = data["remarks"][-300:]
    data.setdefault("logs", []).append(
        {
            "created_at": remark["created_at"],
            "action": "remark",
            "actor_id": str(actor_id),
            "target_id": str(target_id),
            "details": text,
        }
    )
    data["logs"] = data["logs"][-300:]
    save_manager_access_data(data)
    return remark


def manager_access_display_name(chat_id, data=None):
    chat_id = str(chat_id or "")
    if not chat_id:
        return "-"
    data = data or seed_env_managers(manager_access_data())
    record = data.get("users", {}).get(chat_id) or data.get("pending", {}).get(chat_id) or {}
    name = record.get("display_name") or " ".join(part for part in [record.get("first_name"), record.get("last_name")] if part)
    username = record.get("username") or ""
    if name and username:
        return f"{name} (@{username})"
    if name:
        return name
    if username:
        return f"@{username}"
    return chat_id


def manager_log_target_label(value, data=None):
    value = str(value or "")
    if not value:
        return "-"
    if value.startswith("tgOrder"):
        return f"Заказ {display_order_code(value)}"
    if value.isdigit():
        return manager_access_display_name(value, data)
    return value


def manager_logs_text(limit=20):
    data = seed_env_managers(manager_access_data())
    logs = data.get("logs", [])[-limit:]
    if not logs:
        return "<b>Логи</b>\nПока пусто."
    lines = ["<b>Логи</b>"]
    for log in reversed(logs):
        actor = html.escape(manager_access_display_name(log.get("actor_id"), data))
        target = html.escape(manager_log_target_label(log.get("target_id"), data))
        action = html.escape(log.get("action") or "")
        details = html.escape(str(log.get("details") or ""))
        lines.append(f"{log.get('created_at')} | {action} | кто: {actor} | кому: {target}")
        if details:
            lines.append(f"  <i>{details}</i>")
    return "\n".join(lines)


def manager_admin_chat_ids():
    data = seed_env_managers(manager_access_data())
    return [
        chat_id
        for chat_id, record in data.get("users", {}).items()
        if record.get("role") == "admin"
    ]


def manager_access_claim(chat_id, admin_user):
    admin_id = int(admin_user.id)
    admin_name = manager_user_label(admin_user)
    updated = db_rowcount(
        """
        UPDATE tg_manager_access
        SET serviced_by = %s,
            serviced_name = %s,
            serviced_at = NOW(),
            updated_at = NOW()
        WHERE chat_id = %s
          AND status = 'pending'
          AND (serviced_by IS NULL OR serviced_by = %s)
        """,
        (admin_id, admin_name, int(chat_id), admin_id),
    )
    if updated:
        append_manager_log("access_service_started", actor_id=admin_id, target_id=chat_id)
    data = seed_env_managers(manager_access_data())
    return data.get("pending", {}).get(str(chat_id))


def manager_access_keyboard(chat_id, viewer_id=None):
    data = seed_env_managers(manager_access_data())
    pending = data.get("pending", {}).get(str(chat_id), {})
    serviced_by = str(pending.get("serviced_by") or "")
    serviced_name = pending.get("serviced_name") or manager_access_display_name(serviced_by, data)
    if not serviced_by:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Обслужить", callback_data=f"accessclaim:{chat_id}")]
            ]
        )
    if viewer_id is not None and serviced_by == str(viewer_id):
        return manager_access_actions_keyboard(chat_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Уже обслуживает: {serviced_name}"[:64], callback_data="noop")]
        ]
    )


def manager_access_actions_keyboard(chat_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Просмотр", callback_data=f"access:{chat_id}:viewer"),
                InlineKeyboardButton(text="Менеджер", callback_data=f"access:{chat_id}:manager"),
            ],
            [InlineKeyboardButton(text="Отказ", callback_data=f"access:{chat_id}:deny")],
        ]
    )


def manager_user_label(user):
    username = f"@{user.username}" if user.username else "без username"
    name = " ".join(part for part in [user.first_name, user.last_name] if part)
    return f"{name or 'Без имени'} ({username})"


def manager_access_list_text():
    data = seed_env_managers(manager_access_data())
    users = data.get("users", {})
    pending = data.get("pending", {})
    lines = ["<b>Доступы менеджерского бота</b>"]
    if pending:
        lines.append("")
        lines.append("<b>Ожидают решения:</b>")
        for chat_id, record in pending.items():
            username = f"@{record.get('username')}" if record.get("username") else "без username"
            name = record.get("display_name") or " ".join(part for part in [record.get("first_name"), record.get("last_name")] if part)
            phone = record.get("phone") or ""
            lines.append(f"{html.escape(name or 'Без имени')} ({html.escape(username)}) — <code>{html.escape(phone)}</code>")
    if users:
        lines.append("")
        lines.append("<b>Пользователи:</b>")
        for chat_id, record in users.items():
            username = f"@{record.get('username')}" if record.get("username") else "без username"
            name = record.get("display_name") or " ".join(part for part in [record.get("first_name"), record.get("last_name")] if part)
            role = record.get("role") or "none"
            phone = record.get("phone") or ""
            phone_text = f" — <code>{html.escape(phone)}</code>" if phone else ""
            lines.append(f"{html.escape(name or chat_id)} ({html.escape(username)}) — <b>{html.escape(role)}</b>{phone_text}")
    return "\n".join(lines)


def manager_access_list_keyboard():
    data = seed_env_managers(manager_access_data())
    rows = []
    for chat_id, record in data.get("pending", {}).items():
        username = f"@{record.get('username')}" if record.get("username") else str(chat_id)
        name = record.get("display_name") or username
        rows.append([InlineKeyboardButton(text=f"Заявка: {name}"[:64], callback_data=f"accessedit:{chat_id}")])
    for chat_id, record in data.get("users", {}).items():
        username = f"@{record.get('username')}" if record.get("username") else str(chat_id)
        role = record.get("role") or "none"
        name = record.get("display_name") or username
        rows.append([InlineKeyboardButton(text=f"{name} — {role}"[:64], callback_data=f"accessedit:{chat_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Заказы", callback_data="olist:all:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manager_access_edit_keyboard(chat_id):
    rows = [
        [
            InlineKeyboardButton(text="Только просмотр", callback_data=f"accessset:{chat_id}:viewer"),
            InlineKeyboardButton(text="Менеджер", callback_data=f"accessset:{chat_id}:manager"),
        ],
        [InlineKeyboardButton(text="Написать замечание", callback_data=f"remark:{chat_id}")],
    ]
    if str(chat_id) not in ADMIN_MANAGER_IDS:
        rows.append([InlineKeyboardButton(text="Убрать доступ", callback_data=f"accessset:{chat_id}:deny")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="accesslist")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manager_access_home_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пользователи и заявки", callback_data="accesslist")],
            [InlineKeyboardButton(text="Логи", callback_data="accesslogs")],
            [InlineKeyboardButton(text="⬅️ Заказы", callback_data="olist:all:0")],
        ]
    )


def tr(user_id, key):
    lang = user_lang(user_id)
    return LANG_TEXTS.get(lang, LANG_TEXTS["ru"]).get(key, LANG_TEXTS["ru"].get(key, key))


def category_button_label(user_id, key):
    lang = user_lang(user_id)
    return CATEGORY_LABELS_I18N.get(lang, CATEGORY_LABELS_I18N["ru"]).get(key, BUTTON_CATEGORY_LABELS[key])


def category_plain_title(user_id, key):
    label = category_button_label(user_id, key)
    return label.split(" ", 1)[-1] if " " in label else label


def filter_title(user_id, key):
    lang = user_lang(user_id)
    return FILTER_TITLE_I18N.get(lang, FILTER_TITLE_I18N["ru"]).get(key, FILTER_CONFIG[key]["title"])


def translate_filter_value(user_id, value):
    text = html.unescape(str(value or "")).strip()
    lang = user_lang(user_id)
    if lang == "uz":
        replacements = FILTER_VALUE_I18N.get("uz", {})
        for ru, uz in replacements.items():
            if text == ru:
                return uz
            if text.startswith(f"{ru} "):
                return text.replace(ru, uz, 1)
    return text


def display_filter_label_for_user(user_id, filter_key, value_id):
    return translate_filter_value(user_id, get_filter_label(filter_key, value_id))


def language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz"),
            ]
        ]
    )


def build_reply_keyboard(rows):
    builder = ReplyKeyboardBuilder()
    for row in rows:
        builder.row(*row)
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def main_menu(user_id=None):
    return build_reply_keyboard([
        [KeyboardButton(text=tr(user_id, "buy")), KeyboardButton(text=tr(user_id, "sell"))],
        [KeyboardButton(text=tr(user_id, "cart")), KeyboardButton(text=tr(user_id, "orders"))],
        [KeyboardButton(text=tr(user_id, "contacts"))],
        [KeyboardButton(text=tr(user_id, "language"))],
    ])


def catalog_keyboard(user_id=None):
    return build_reply_keyboard([
        [KeyboardButton(text=tr(user_id, "back"))],
        [KeyboardButton(text=category_button_label(user_id, "sale")), KeyboardButton(text=category_button_label(user_id, "ring"))],
        [KeyboardButton(text=category_button_label(user_id, "watch")), KeyboardButton(text=category_button_label(user_id, "earring"))],
        [KeyboardButton(text=category_button_label(user_id, "chain")), KeyboardButton(text=category_button_label(user_id, "bracelet"))],
        [KeyboardButton(text=category_button_label(user_id, "case")), KeyboardButton(text=category_button_label(user_id, "pendant"))],
        [KeyboardButton(text=category_button_label(user_id, "necklace")), KeyboardButton(text=category_button_label(user_id, "set"))],
        [KeyboardButton(text=tr(user_id, "home"))],
    ])


def sale_keyboard(user_id=None):
    rows = [[KeyboardButton(text=tr(user_id, "back"))]]
    current_row = []
    for key in SALE_CATEGORY_KEYS:
        current_row.append(KeyboardButton(text=category_button_label(user_id, key)))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([KeyboardButton(text=tr(user_id, "search_sale"))])
    rows.append([KeyboardButton(text=tr(user_id, "home"))])
    return build_reply_keyboard(rows)


def sell_keyboard(user_id=None):
    return build_reply_keyboard([
        [KeyboardButton(text=tr(user_id, "back"))],
        [KeyboardButton(text=tr(user_id, "contacts"))],
        [KeyboardButton(text=tr(user_id, "home"))],
    ])


def back_only_keyboard(user_id=None):
    return build_reply_keyboard([
        [KeyboardButton(text=tr(user_id, "back"))],
        [KeyboardButton(text=tr(user_id, "home"))],
    ])


def manager_main_keyboard(user_id=None):
    rows = [[KeyboardButton(text=MANAGER_ORDERS_TEXT)]]
    if user_id and manager_is_admin(user_id):
        rows.append([KeyboardButton(text="🔐 Доступы")])
    return build_reply_keyboard(rows)
def contacts_text():
    return (
        "<b>Diamant</b>\n\n"
        '<tg-emoji emoji-id="5244867092389336658">🌟</tg-emoji> '
        '<a href="https://t.me/diamant_uzb">Telegram</a>\n'
        '<tg-emoji emoji-id="5247187023269240776">🌟</tg-emoji> '
        '<a href="https://www.instagram.com/diamant.uzb">Instagram</a>\n'
        '<tg-emoji emoji-id="5246820873012286628">🌐</tg-emoji> '
        '<a href="https://diamant.uz/">diamant.uz</a>\n'
        '<tg-emoji emoji-id="5244837435640158432">📞</tg-emoji> '
        '<a href="tel:+998550550440">+998550550440</a>\n'
	'<tg-emoji emoji-id="5244837435640158432">📞</tg-emoji> '
        '<a href="tel:+998550550002">+998550550002</a>'
    )

def category_filter_keyboard(user_id):
    state = USER_STATES.get(user_id, {})
    category_key = state.get("category_key")
    category = CATEGORY_CONFIG[category_key]
    back_target = "sale" if state.get("previous_view") == "sale" or state.get("sale") else "catalog"
    rows = [[InlineKeyboardButton(text=tr(user_id, "back"), callback_data=back_target)]]
    current_row = []
    for filter_key in category["filters"]:
        title = filter_title(user_id, filter_key)
        current_row.append(InlineKeyboardButton(text=title, callback_data=f"fopen:{filter_key}"))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([InlineKeyboardButton(text=tr(user_id, "search"), callback_data="do_search")])
    rows.append([InlineKeyboardButton(text=tr(user_id, "reset_filters"), callback_data="reset_filters")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def filter_values_keyboard(user_id, filter_key):
    selected = USER_STATES.get(user_id, {}).get("filters", {}).get(filter_key, set())
    rows = [[InlineKeyboardButton(text=tr(user_id, "back"), callback_data="fback")]]
    values = get_filter_values(filter_key, selected_metals=get_selected_metals(user_id))
    if not values:
        rows.append([InlineKeyboardButton(text=tr(user_id, "no_values"), callback_data="noop")])
    current_row = []
    for value_id, label in values:
        checked = "✅ " if str(value_id) in selected else ""
        current_row.append(InlineKeyboardButton(text=f"{checked}{translate_filter_value(user_id, label)}", callback_data=f"fval:{filter_key}:{value_id}"))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([InlineKeyboardButton(text=tr(user_id, "search"), callback_data="do_search")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def search_nav_keyboard(user_id, category_key, offset, has_next):
    state = USER_STATES.get(user_id, {})
    back_target = "sale" if state.get("previous_view") == "sale" or state.get("sale") else "catalog"
    rows = []
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text=tr(user_id, "back"), callback_data=f"search:{category_key}:{max(offset - 5, 0)}"))
    if has_next:
        nav.append(InlineKeyboardButton(text=tr(user_id, "next"), callback_data=f"search:{category_key}:{offset + 5}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text=tr(user_id, "filters"), callback_data="fback")])
    rows.append([InlineKeyboardButton(text=tr(user_id, "back"), callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def search_results_keyboard(user_id, total, offset):
    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    current_page = min(offset // PAGE_SIZE + 1, total_pages)
    return build_reply_keyboard(
        [
            [KeyboardButton(text=tr(user_id, "back"))],
            [
                KeyboardButton(text="<"),
                KeyboardButton(text=f"{current_page}/{total_pages}"),
                KeyboardButton(text=">"),
            ],
            [KeyboardButton(text=tr(user_id, "home"))],
        ],
    )


def page_picker_keyboard(user_id, category_key, total, current_page, block_start=1, block_size=40):
    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    block_start = max(1, min(int(block_start or 1), total_pages))
    block_end = min(block_start + block_size - 1, total_pages)
    rows = []
    row = []
    for page in range(block_start, block_end + 1):
        text = f"• {page}" if page == current_page else str(page)
        row.append(InlineKeyboardButton(text=text, callback_data=f"page:{category_key}:{page}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav = []
    if block_start > 1:
        prev_start = max(1, block_start - block_size)
        nav.append(InlineKeyboardButton(text="«", callback_data=f"pages:{category_key}:{prev_start}"))
    nav.append(InlineKeyboardButton(text=f"{block_start}-{block_end} / {total_pages}", callback_data="noop"))
    if block_end < total_pages:
        nav.append(InlineKeyboardButton(text="»", callback_data=f"pages:{category_key}:{block_end + 1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton(text=tr(user_id, "back"), callback_data=f"search:{category_key}:{(current_page - 1) * PAGE_SIZE}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_keyboard(categories):
    rows = []
    for category in categories:
        rows.append(
            [
                InlineKeyboardButton(
                    text=category["name"],
                    callback_data=f"cat:{category['category_id']}:0",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Назад", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def products_keyboard(products, category_id=None, offset=0):
    rows = []
    for product in products:
        rows.append(
            [
                InlineKeyboardButton(
                    text=product["name"][:60],
                    callback_data=f"prod:{product['product_id']}",
                )
            ]
        )

    nav = []
    if category_id is not None and products:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Показать 5 карточками",
                    callback_data=f"catcards:{category_id}:{offset}",
                )
            ]
        )
    if category_id is not None and offset > 0:
        nav.append(InlineKeyboardButton(text="Назад", callback_data=f"cat:{category_id}:{max(offset - 5, 0)}"))
    if category_id is not None and len(products) == 5:
        nav.append(InlineKeyboardButton(text="Ещё", callback_data=f"cat:{category_id}:{offset + 5}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="Категории", callback_data="cats")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cards_nav_keyboard(kind, offset, has_next, category_id=None):
    rows = []
    nav = []
    if offset > 0:
        if kind == "new":
            nav.append(InlineKeyboardButton(text="Назад", callback_data=f"newcards:{max(offset - 5, 0)}"))
        else:
            nav.append(InlineKeyboardButton(text="Назад", callback_data=f"catcards:{category_id}:{max(offset - 5, 0)}"))
    if has_next:
        if kind == "new":
            nav.append(InlineKeyboardButton(text="Далее", callback_data=f"newcards:{offset + 5}"))
        else:
            nav.append(InlineKeyboardButton(text="Далее", callback_data=f"catcards:{category_id}:{offset + 5}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="Категории", callback_data="cats")])
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_keyboard(product_id, media_count=1, media_index=0, in_cart=False, back_to_cart=False, user_id=None):
    total = max(int(media_count or 1), 1)
    index = max(min(int(media_index or 0), total - 1), 0)
    prev_index = (index - 1) % total
    next_index = (index + 1) % total
    rows = [
            [
                InlineKeyboardButton(text="<", callback_data=f"media:{product_id}:{prev_index}"),
                InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="noop"),
                InlineKeyboardButton(text=">", callback_data=f"media:{product_id}:{next_index}"),
            ],
    ]
    site_button = InlineKeyboardButton(text=tr(user_id, "site"), url=product_site_link(product_id).replace("&amp;", "&"))
    if in_cart:
        rows.append([site_button])
        rows.append([
            InlineKeyboardButton(text=tr(user_id, "in_cart"), callback_data="cart_view"),
            InlineKeyboardButton(text=tr(user_id, "remove_selection"), callback_data=f"cart_remove:{product_id}"),
        ])
        if back_to_cart:
            rows.append([InlineKeyboardButton(text=tr(user_id, "back_to_cart"), callback_data="cart_view")])
    else:
        rows.append([site_button])
        rows.append([InlineKeyboardButton(text=tr(user_id, "add_to_cart"), callback_data=f"cart_add:{product_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def keyboard_media_index(reply_markup, media_count=1):
    total = max(int(media_count or 1), 1)
    if not reply_markup:
        return 0
    for row in reply_markup.inline_keyboard:
        for button in row:
            text = button.text or ""
            if "/" not in text:
                continue
            current, _, count = text.partition("/")
            if current.strip().isdigit() and count.strip().isdigit():
                return max(min(int(current.strip()) - 1, total - 1), 0)
    return 0


def is_product_card_keyboard(reply_markup, product_id):
    if not reply_markup:
        return False
    media_prefix = f"media:{product_id}:"
    for row in reply_markup.inline_keyboard:
        for button in row:
            if (button.callback_data or "").startswith(media_prefix):
                return True
    return False


def order_keyboard(product_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Смотреть на сайте ↗️", url=product_site_link(product_id).replace("&amp;", "&")),
            ],
            [InlineKeyboardButton(text="🛒 В корзину", callback_data=f"cart_add:{product_id}")],
        ]
    )


def contact_request_keyboard(user_id=None):
    return build_reply_keyboard(
        [
            [KeyboardButton(text=tr(user_id, "send_contact"), request_contact=True)],
            [KeyboardButton(text=tr(user_id, "back")), KeyboardButton(text=tr(user_id, "home"))],
        ]
    )


def region_keyboard(user_id=None):
    rows = []
    for index in range(0, len(REGIONS), 2):
        rows.append([KeyboardButton(text=region) for region in REGIONS[index : index + 2]])
    rows.append([KeyboardButton(text=tr(user_id, "back")), KeyboardButton(text=tr(user_id, "home"))])
    return build_reply_keyboard(rows)


def manager_status_keyboard(order_code):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 В обработке", callback_data=f"ostatus:{order_code}:processing"),
                InlineKeyboardButton(text="🚚 В пути", callback_data=f"ostatus:{order_code}:in_transit"),
            ],
            [
                InlineKeyboardButton(text="✅ Завершено", callback_data=f"ostatus:{order_code}:completed"),
                InlineKeyboardButton(text="❌ Отменено", callback_data=f"ostatus:{order_code}:cancelled"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"oview_nogeo:{order_code}")],
        ]
    )


def manager_order_keyboard(order_code, status=None, manager_user_id=None):
    order = get_tg_order(order_code)
    row = []
    can_manage = manager_user_id is None or manager_can_manage(manager_user_id)
    if can_manage and status not in FINAL_ORDER_STATUSES:
        row.append(InlineKeyboardButton(text="Изменить статус", callback_data=f"mstatus:{order_code}"))
    row.append(InlineKeyboardButton(text="Товары", callback_data=f"mitems:{order_code}"))
    rows = [row]
    if order and order.get("delivery_lat") is not None and order.get("delivery_lng") is not None:
        rows.append([InlineKeyboardButton(text="📍 Локация", callback_data=f"oloc:{order_code}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manager_status_confirm_keyboard(order_code, status):
    label = TG_ORDER_STATUSES.get(status, status)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Подтвердить: {label}", callback_data=f"oconfirm:{order_code}:{status}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"mstatus:{order_code}")],
        ]
    )


def manager_order_items_keyboard(order_code):
    items = get_tg_order_items(order_code)
    if not items:
        order = get_tg_order(order_code)
        items = [
            {
                "product_id": order["product_id"],
                "product_name": order["product_name"],
                "product_price": order["product_price"],
                "product_url": order.get("product_url") or product_site_link(order["product_id"]).replace("&amp;", "&"),
            }
        ] if order else []
    rows = []
    for item in items:
        name = html.unescape(item.get("product_name") or "")
        short_name = name if len(name) <= 20 else name[:18] + ".."
        label = f"{short_name} — {format_price_amount(item['product_price'])}"
        rows.append([InlineKeyboardButton(text=label[:64], callback_data=f"mprod:{order_code}:{item['product_id']}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"oview_nogeo:{order_code}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manager_product_keyboard(order_code, product_id, media_count=1, media_index=0):
    total = max(int(media_count or 1), 1)
    index = max(min(int(media_index or 0), total - 1), 0)
    prev_index = (index - 1) % total
    next_index = (index + 1) % total
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="<", callback_data=f"mmedia:{order_code}:{product_id}:{prev_index}"),
                InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="noop"),
                InlineKeyboardButton(text=">", callback_data=f"mmedia:{order_code}:{product_id}:{next_index}"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад к товарам", callback_data=f"mitems:{order_code}")],
        ]
    )


def client_order_items_keyboard(order_code, user_id=None):
    items = get_tg_order_items(order_code)
    if not items:
        order = get_tg_order(order_code)
        items = [
            {
                "product_id": order["product_id"],
                "product_name": order["product_name"],
                "product_price": order["product_price"],
            }
        ] if order else []
    rows = []
    for item in items:
        name = html.unescape(item.get("product_name") or "")
        short_name = name if len(name) <= 20 else name[:18] + ".."
        label = f"{short_name} — {format_price(item['product_price'])}"
        rows.append([InlineKeyboardButton(text=label[:64], callback_data=f"myprod:{order_code}:{item['product_id']}")])
    rows.append([InlineKeyboardButton(text=tr(user_id, "back"), callback_data=f"myorder:{order_code}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def client_order_product_keyboard(order_code, product_id, media_count=1, media_index=0, user_id=None):
    total = max(int(media_count or 1), 1)
    index = max(min(int(media_index or 0), total - 1), 0)
    prev_index = (index - 1) % total
    next_index = (index + 1) % total
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="<", callback_data=f"mymedia:{order_code}:{product_id}:{prev_index}"),
                InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="noop"),
                InlineKeyboardButton(text=">", callback_data=f"mymedia:{order_code}:{product_id}:{next_index}"),
            ],
            [InlineKeyboardButton(text=tr(user_id, "back_to_items"), callback_data=f"myitems:{order_code}")],
        ]
    )


def client_order_keyboard(order_code, status, user_id=None):
    rows = [[InlineKeyboardButton(text=tr(user_id, "items"), callback_data=f"myitems:{order_code}")]]
    if status in {"completed", "done", "completed_success"} and not order_has_client_review(order_code):
        rows.append([InlineKeyboardButton(text=tr(user_id, "leave_review"), callback_data=f"reviewstart:{order_code}")])
    if status not in FINAL_ORDER_STATUSES:
        rows.append([InlineKeyboardButton(text=tr(user_id, "cancel_order"), callback_data=f"mycancel:{order_code}")])
    rows.append([InlineKeyboardButton(text=tr(user_id, "back"), callback_data="myorders:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_keyboard(items, user_id=None):
    rows = []
    for item in items:
        name = html.unescape(item["name"])
        short_name = name if len(name) <= 20 else name[:18] + ".."
        label = f"{short_name} — {format_price(item['price'])}"
        rows.append([InlineKeyboardButton(text=label[:64], callback_data=f"cart_prod:{item['product_id']}")])
    if items:
        rows.append([InlineKeyboardButton(text=tr(user_id, "checkout"), callback_data="cart_checkout")])
        rows.append([InlineKeyboardButton(text=tr(user_id, "back"), callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def review_request_keyboard(order_code, user_id=None):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr(user_id, "leave_review"), callback_data=f"reviewstart:{order_code}")],
            [InlineKeyboardButton(text=tr(user_id, "skip_review"), callback_data=f"reviewskip:{order_code}")],
        ]
    )


def manager_orders_keyboard(page=0, status_filter="all", page_size=8):
    offset = page * page_size
    status_filter = status_filter if status_filter in MANAGER_ORDER_FILTER_MAP else "all"
    statuses = MANAGER_ORDER_FILTER_MAP[status_filter]["statuses"]
    where_sql = ""
    params = []
    if statuses:
        placeholders = ",".join(["%s"] * len(statuses))
        where_sql = f"WHERE status IN ({placeholders})"
        params.extend(statuses)
    params.extend([page_size + 1, offset])
    rows = db_query(
        f"""
        SELECT order_code, customer_name, first_name, last_name, product_price, status
        FROM tg_orders
        {where_sql}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )
    buttons = []
    filter_row = []
    for key, label, _statuses in MANAGER_ORDER_FILTERS:
        text = f"• {label}" if key == status_filter else label
        filter_row.append(InlineKeyboardButton(text=text, callback_data=f"olist:{key}:0"))
        if len(filter_row) == 3:
            buttons.append(filter_row)
            filter_row = []
    if filter_row:
        buttons.append(filter_row)
    for order in rows[:page_size]:
        name = order_customer_name(order) or "Без имени"
        status = TG_ORDER_LIST_STATUSES.get(order.get("status"), order.get("status") or "")
        text = f"{display_order_code(order['order_code'])} | {name} | {format_price_amount(order['product_price'])} | {status}"
        buttons.append([InlineKeyboardButton(text=text[:64], callback_data=f"oview:{order['order_code']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="<", callback_data=f"olist:{status_filter}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}", callback_data="noop"))
    if len(rows) > page_size:
        nav.append(InlineKeyboardButton(text=">", callback_data=f"olist:{status_filter}:{page + 1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons), len(rows[:page_size])


def client_orders_keyboard(user_id, page=0, page_size=8):
    offset = page * page_size
    rows = db_query(
        """
        SELECT order_code, product_name, product_price, status
        FROM tg_orders
        WHERE client_tg_id = %s
        ORDER BY id DESC
        LIMIT %s OFFSET %s
        """,
        (int(user_id), page_size + 1, offset),
    )
    buttons = []
    for order in rows[:page_size]:
        status = ORDER_STATUS_I18N.get(user_lang(user_id), ORDER_STATUS_I18N["ru"]).get(order.get("status"), order.get("status") or "")
        text = f"{display_order_code(order['order_code'])} | {status} | {format_price(order['product_price'])}"
        buttons.append([InlineKeyboardButton(text=text[:64], callback_data=f"myorder:{order['order_code']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="<", callback_data=f"myorders:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}", callback_data="noop"))
    if len(rows) > page_size:
        nav.append(InlineKeyboardButton(text=">", callback_data=f"myorders:{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text=tr(user_id, "back"), callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons), len(rows[:page_size])


def format_price(value):
    price = Decimal(str(value or 0))
    return f"{int(price):,}".replace(",", " ") + " сум"


def format_price_amount(value):
    price = Decimal(str(value or 0))
    return f"{int(price):,}".replace(",", " ")


def display_order_code(order_code):
    text = str(order_code or "")
    match = re.search(r"(\d+)$", text)
    return match.group(1) if match else text


def clean_description(value, limit=500):
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = " ".join(text.split())
    return html.escape(text[:limit])


def display_filter_name(filter_key, raw_name):
    name = html.unescape(str(raw_name)).strip()
    if filter_key == "sample":
        for token in ("Золото", "Серебро"):
            name = name.replace(token, "")
        name = name.strip()
    return name


def sample_metal_key(raw_name):
    name = html.unescape(str(raw_name or "")).strip().lower()
    if "золото" in name or "золот" in name:
        return "gold"
    if "серебро" in name or "сереб" in name:
        return "silver"
    return ""


def display_sample_filter_name(raw_name, selected_metals=None):
    selected_metals = set(selected_metals or [])
    metal_key = sample_metal_key(raw_name)
    short_name = display_filter_name("sample", raw_name)
    if len(selected_metals) == 1 and metal_key in selected_metals:
        return short_name
    if metal_key == "gold":
        return f"Золото {short_name}"
    if metal_key == "silver":
        return f"Серебро {short_name}"
    return short_name


def get_selected_metals(user_id):
    return set(USER_STATES.get(user_id, {}).get("filters", {}).get("metal", set()))


def get_filter_values(filter_key, selected_metals=None):
    config = FILTER_CONFIG[filter_key]
    if config["type"] == "manual":
        return config.get("values", [])

    if config["type"] == "manufacturer":
        rows = db_query(
            """
            SELECT m.manufacturer_id, m.name
            FROM ocoe_manufacturer m
            JOIN ocoe_product p ON p.manufacturer_id = m.manufacturer_id
            JOIN ocoe_product_to_category p2c ON p2c.product_id = p.product_id
            LEFT JOIN ocoe_category child ON child.category_id = p2c.category_id
            WHERE p.status = 1
              AND (p2c.category_id = 266 OR child.parent_id = 266)
            GROUP BY m.manufacturer_id, m.name
            ORDER BY m.name
            """
        )
        return [(str(row["manufacturer_id"]), row["name"]) for row in rows]

    rows = db_query(
        """
        SELECT f.filter_id, fd.name
        FROM ocoe_filter_group_description fgd
        JOIN ocoe_filter f ON f.filter_group_id = fgd.filter_group_id
        JOIN ocoe_filter_description fd ON fd.filter_id = f.filter_id
        WHERE fgd.language_id = %s
          AND fd.language_id = %s
          AND fgd.name = %s
        ORDER BY f.sort_order, fd.name
        """,
        (LANGUAGE_ID, LANGUAGE_ID, config["group"]),
    )
    values = []
    selected_metals = set(selected_metals or [])
    for row in rows:
        raw_name = row["name"]
        if filter_key == "sample":
            metal_key = sample_metal_key(raw_name)
            if selected_metals and metal_key and metal_key not in selected_metals:
                continue
            label = display_sample_filter_name(raw_name, selected_metals)
        else:
            label = display_filter_name(filter_key, raw_name)
        values.append((str(row["filter_id"]), label))
    return values


def get_filter_label(filter_key, value_id):
    for current_id, label in get_filter_values(filter_key):
        if str(current_id) == str(value_id):
            return label
    return str(value_id)


def cleanup_incompatible_sample_filters(state):
    filters = state.get("filters", {})
    selected_metals = set(filters.get("metal", set()))
    selected_samples = filters.get("sample")
    if not selected_metals or not selected_samples:
        return
    allowed_sample_ids = {value_id for value_id, _ in get_filter_values("sample", selected_metals=selected_metals)}
    filters["sample"] = {value_id for value_id in selected_samples if value_id in allowed_sample_ids}


def get_product_filter_map(product_id):
    rows = db_query(
        """
        SELECT fgd.name AS group_name, fd.name AS filter_name
        FROM ocoe_product_filter pf
        JOIN ocoe_filter f ON f.filter_id = pf.filter_id
        JOIN ocoe_filter_description fd ON fd.filter_id = pf.filter_id
        JOIN ocoe_filter_group_description fgd ON fgd.filter_group_id = f.filter_group_id
        WHERE pf.product_id = %s
          AND fd.language_id = %s
          AND fgd.language_id = %s
        ORDER BY fgd.name, fd.name
        """,
        (product_id, LANGUAGE_ID, LANGUAGE_ID),
    )
    result = {}
    for row in rows:
        result.setdefault(row["group_name"], []).append(row["filter_name"])
    return result


def first_filter_value(filter_map, group_name):
    values = filter_map.get(group_name) or []
    return values[0].strip() if values else ""


def infer_metal(product, filter_map):
    metal = first_filter_value(filter_map, "Тип металла")
    if metal:
        return metal.strip()
    name = html.unescape(product.get("name") or "").lower()
    if name.startswith("золот"):
        return "Золото"
    if name.startswith("сереб"):
        return "Серебро"
    return ""


def country_flag_html(country):
    normalized = html.unescape(country or "").strip().lower()
    flags = {
        "узбекистан": "🇺🇿",
        "азербайджан": "🇦🇿",
        "украина": "🇺🇦",
        "армения": "🇦🇲",
        "италия": "🇮🇹",
        "турция": "🇹🇷",
        "россия": "🇷🇺",
        "китай": "🇨🇳",
        "швейцария": "🇨🇭",
        "япония": "🇯🇵",
        "сша": "🇺🇸",
        "оаэ": "🇦🇪",
        "индия": "🇮🇳",
    }
    flag = flags.get(normalized, "")
    custom_emoji_id = CUSTOM_COUNTRY_FLAG_EMOJI_ID.get(normalized)
    if custom_emoji_id and flag:
        return f'<tg-emoji emoji-id="{html.escape(custom_emoji_id)}">{html.escape(flag)}</tg-emoji>'
    return html.escape(flag)


def product_site_link(product_id):
    rows = db_query(
        """
        SELECT keyword
        FROM ocoe_seo_url
        WHERE query = %s
          AND language_id = %s
        ORDER BY store_id = 0 DESC, seo_url_id DESC
        LIMIT 1
        """,
        (f"product_id={int(product_id)}", LANGUAGE_ID),
    )
    if rows and rows[0].get("keyword"):
        keyword = quote(rows[0]["keyword"].strip("/"), safe="/")
        return f"{PRODUCT_SITE_URL}{keyword}"
    return f"{PRODUCT_SITE_URL}index.php?route=product/product&amp;product_id={int(product_id)}"


def user_has_active_reserve(user_id, product_id):
    if not user_id:
        return False
    rows = db_query(
        """
        SELECT 1
        FROM tg_cart_items
        WHERE user_id = %s
          AND product_id = %s
          AND status = 'active'
          AND reserved_quantity > 0
        LIMIT 1
        """,
        (user_id, product_id),
    )
    return bool(rows)


def user_has_cart_item(user_id, product_id):
    if not user_id:
        return False
    rows = db_query(
        """
        SELECT 1
        FROM tg_cart_items
        WHERE user_id = %s
          AND product_id = %s
          AND status = 'active'
        LIMIT 1
        """,
        (user_id, product_id),
    )
    return bool(rows)


def detail_text(product, user_id=None):
    name = html.escape(html.unescape(product["name"]))
    model = html.escape(product.get("model") or "")
    weight = Decimal(str(product.get("weight") or 0))
    quantity = int(product.get("quantity") or 0)
    filter_map = get_product_filter_map(product["product_id"])
    sample = display_filter_name("sample", first_filter_value(filter_map, "Проба"))
    metal = infer_metal(product, filter_map)
    country = first_filter_value(filter_map, "Страна")
    flag = country_flag_html(country)

    lines = [
        PRODUCT_TOP_STARS_HTML,
        f"<b>{name}</b>",
        f"<b>{tr(user_id, 'price')}:</b> <b>{format_price(product['price'])}</b>",
    ]
    if weight > 0:
        unit = "g" if user_lang(user_id) == "uz" else "г"
        lines.append(f"<b>{tr(user_id, 'weight')}:</b> {weight.normalize()} {unit}")
    if sample:
        lines.append(f"<b>{tr(user_id, 'sample')}:</b> {html.escape(sample)}")
    if metal:
        metal_text = {"Золото": "Tilla", "Серебро": "Kumush"}.get(metal, metal) if user_lang(user_id) == "uz" else metal
        lines.append(f"<b>{tr(user_id, 'metal')}:</b> {html.escape(metal_text)}")
    in_stock_for_user = quantity > 0 or user_has_active_reserve(user_id, product["product_id"])
    stock_text = f"{IN_STOCK_EMOJI_HTML} {tr(user_id, 'in_stock')}" if in_stock_for_user else f"{OUT_OF_STOCK_EMOJI_HTML} {tr(user_id, 'out_of_stock')}"
    lines.append(f"<b>{tr(user_id, 'status')}:</b> {stock_text}")
    if flag:
        lines.append(f"<b>{tr(user_id, 'production')}:</b> {flag}")
    if model:
        lines.append(f"<b>{tr(user_id, 'model')}:</b> <code>{model}</code>")
    return "\n".join(lines)


def selected_filters_text(user_id):
    state = USER_STATES.get(user_id, {})
    pieces = []
    for filter_key, values in state.get("filters", {}).items():
        if not values:
            continue
        title = filter_title(user_id, filter_key)
        labels = [display_filter_label_for_user(user_id, filter_key, value_id) for value_id in sorted(values)]
        pieces.append(f"{title}={', '.join(labels)}")
    return ", ".join(pieces)


def category_emoji_html(category_key):
    emoji = CATEGORY_EMOJI.get(category_key, "•")
    custom_emoji_id = CUSTOM_CATEGORY_EMOJI_ID.get(category_key)
    if custom_emoji_id:
        return f'<tg-emoji emoji-id="{html.escape(custom_emoji_id)}">{html.escape(emoji)}</tg-emoji>'
    return html.escape(emoji)


def filter_status_text(user_id):
    state = USER_STATES.get(user_id, {})
    category_key = state.get("category_key")
    if not category_key:
        return tr(user_id, "catalog").rstrip(":")
    if category_key == "sale":
        return f"{category_emoji_html('sale')} {html.escape(category_plain_title(user_id, 'sale'))}"
    category = html.escape(category_plain_title(user_id, category_key))
    title = f"{category_emoji_html(category_key)} {category}"
    if state.get("sale"):
        title = f"{category_emoji_html('sale')} {html.escape(category_plain_title(user_id, 'sale'))} / {title}"
    parts = []
    for filter_key in CATEGORY_CONFIG[category_key]["filters"]:
        values = state.get("filters", {}).get(filter_key, set())
        if not values:
            continue
        title_text = html.escape(filter_title(user_id, filter_key))
        labels = [html.escape(display_filter_label_for_user(user_id, filter_key, value_id)) for value_id in sorted(values)]
        parts.append(f"{title_text}={', '.join(labels)}")
    if parts:
        return f"{title} ({', '.join(parts)})"
    return title


async def update_filter_status(message: Message):
    state = USER_STATES.get(message.from_user.id, {})
    text = filter_status_text(message.from_user.id)
    message_id = state.get("filter_status_message_id")
    if message_id:
        try:
            await bot.edit_message_text(text, chat_id=message.chat.id, message_id=message_id, parse_mode=ParseMode.HTML)
            return
        except Exception:
            pass
    sent = await message.answer(text, parse_mode=ParseMode.HTML)
    state["filter_status_message_id"] = sent.message_id


async def safe_delete_message(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


async def delete_filter_status(message: Message, state):
    message_id = state.get("filter_status_message_id")
    if not message_id:
        return
    try:
        await bot.delete_message(message.chat.id, message_id)
    except Exception:
        pass
    state.pop("filter_status_message_id", None)


async def delete_state_messages(message: Message, state, *keys):
    for key in keys:
        message_id = state.get(key)
        if not message_id:
            continue
        try:
            await bot.delete_message(message.chat.id, message_id)
        except Exception:
            pass
        state.pop(key, None)


async def delete_navigation_messages(message: Message, state):
    await delete_state_messages(message, state, "filter_status_message_id", "search_status_message_id")


async def hide_reply_keyboard(message: Message):
    try:
        sent = await message.answer("\u2063", reply_markup=ReplyKeyboardRemove())
    except Exception:
        return
    try:
        await sent.delete()
    except Exception:
        pass


async def send_filter_status(message: Message, reply_markup):
    state = USER_STATES.get(message.from_user.id, {})
    await delete_filter_status(message, state)
    await hide_reply_keyboard(message)
    sent = await message.answer(filter_status_text(message.from_user.id), parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    state["filter_status_message_id"] = sent.message_id


def select_category_state(user_id, category_key, sale_mode=False):
    USER_STATES[user_id] = {
        "category_key": category_key,
        "sale": sale_mode,
        "filters": {},
        "view": "category_filters",
        "previous_view": "sale" if sale_mode else "catalog",
    }
    category = CATEGORY_CONFIG[category_key]
    title = f"{'Скидки / ' if sale_mode else ''}{category['title']}"
    return title


async def show_sale_menu(message: Message):
    USER_STATES[message.from_user.id] = {"section": "sale", "view": "sale", "filters": {}}
    await message.answer(tr(message.from_user.id, "sale"), reply_markup=sale_keyboard(message.from_user.id))


def get_categories():
    return db_query(
        """
        SELECT c.category_id, cd.name
        FROM ocoe_category c
        JOIN ocoe_category_description cd ON cd.category_id = c.category_id
        WHERE c.status = 1
          AND c.parent_id = 0
          AND cd.language_id = %s
        ORDER BY c.sort_order, cd.name
        """,
        (LANGUAGE_ID,),
    )


def get_products_for_category(category_id, offset=0):
    return db_query(
        """
        SELECT DISTINCT p.product_id, pd.name, p.price
        FROM ocoe_product p
        JOIN ocoe_product_description pd ON pd.product_id = p.product_id
        JOIN ocoe_product_to_category p2c ON p2c.product_id = p.product_id
        LEFT JOIN ocoe_category child ON child.category_id = p2c.category_id
        WHERE p.status = 1
          AND pd.language_id = %s
          AND (p2c.category_id = %s OR child.parent_id = %s)
        ORDER BY p.date_added DESC, p.product_id DESC
        LIMIT 5 OFFSET %s
        """,
        (LANGUAGE_ID, category_id, category_id, offset),
    )


def get_new_products():
    return db_query(
        """
        SELECT p.product_id, pd.name, p.price
        FROM ocoe_product p
        JOIN ocoe_product_description pd ON pd.product_id = p.product_id
        WHERE p.status = 1
          AND pd.language_id = %s
        ORDER BY p.date_added DESC, p.product_id DESC
        LIMIT 5
        """,
        (LANGUAGE_ID,),
    )


def get_new_products_page(offset=0):
    return db_query(
        """
        SELECT p.product_id, pd.name, p.price
        FROM ocoe_product p
        JOIN ocoe_product_description pd ON pd.product_id = p.product_id
        WHERE p.status = 1
          AND pd.language_id = %s
        ORDER BY p.date_added DESC, p.product_id DESC
        LIMIT 6 OFFSET %s
        """,
        (LANGUAGE_ID, offset),
    )


def build_filtered_query(user_id, category_key, offset=0, count_only=False):
    state = USER_STATES.get(user_id, {})
    category = CATEGORY_CONFIG[category_key]
    filters = state.get("filters", {})
    sale = state.get("sale") or category.get("sale")
    global_sale = category_key == "sale"

    select = "COUNT(DISTINCT p.product_id) AS total" if count_only else "DISTINCT p.product_id, pd.name, p.price"
    sql = [
        f"SELECT {select}",
        "FROM ocoe_product p",
        "JOIN ocoe_product_description pd ON pd.product_id = p.product_id",
    ]
    params = [LANGUAGE_ID]
    where = [
        "p.status = 1",
        "pd.language_id = %s",
    ]
    if not global_sale:
        sql.extend(
            [
                "JOIN ocoe_product_to_category p2c ON p2c.product_id = p.product_id",
                "LEFT JOIN ocoe_category child ON child.category_id = p2c.category_id",
            ]
        )
        where.append("(p2c.category_id = %s OR child.parent_id = %s)")
        params.extend([category["category_id"], category["category_id"]])
    if sale:
        where.append(
            """EXISTS (
                SELECT 1
                FROM ocoe_product_special ps
                WHERE ps.product_id = p.product_id
                  AND (ps.date_start = '0000-00-00' OR ps.date_start <= CURDATE())
                  AND (ps.date_end = '0000-00-00' OR ps.date_end >= CURDATE())
            )"""
        )

    for filter_key, values in filters.items():
        if not values:
            continue
        config = FILTER_CONFIG[filter_key]
        if config["type"] == "filter_group":
            placeholders = ",".join(["%s"] * len(values))
            where.append(
                f"""EXISTS (
                    SELECT 1 FROM ocoe_product_filter pf
                    WHERE pf.product_id = p.product_id
                      AND pf.filter_id IN ({placeholders})
                )"""
            )
            params.extend(list(values))
        elif filter_key == "brand":
            placeholders = ",".join(["%s"] * len(values))
            where.append(f"p.manufacturer_id IN ({placeholders})")
            params.extend(list(values))
        elif filter_key == "metal":
            metal_parts = []
            for value in values:
                if value == "gold":
                    metal_parts.append("pd.name LIKE %s")
                    params.append("Золот%")
                elif value == "silver":
                    metal_parts.append("pd.name LIKE %s")
                    params.append("Сереб%")
            if metal_parts:
                where.append("(" + " OR ".join(metal_parts) + ")")
        elif filter_key == "mechanism":
            mechanism_parts = []
            for value in values:
                if value == "auto":
                    mechanism_parts.append("(pd.name LIKE %s OR pd.description LIKE %s)")
                    params.extend(["%автомат%", "%автомат%"])
                elif value == "mech":
                    mechanism_parts.append("(pd.name LIKE %s OR pd.description LIKE %s)")
                    params.extend(["%механ%", "%механ%"])
            if mechanism_parts:
                where.append("(" + " OR ".join(mechanism_parts) + ")")
        elif filter_key == "dial":
            dial_parts = []
            for value in values:
                dial_parts.append("(pd.name LIKE %s OR pd.description LIKE %s)")
                params.extend([f"%{value}%", f"%{value}%"])
            if dial_parts:
                where.append("(" + " OR ".join(dial_parts) + ")")

    sql.append("WHERE " + " AND ".join(where))
    if not count_only:
        sql.append("ORDER BY (p.quantity > 0) DESC, p.date_added DESC, p.product_id DESC")
        sql.append("LIMIT 6 OFFSET %s")
        params.append(offset)

    return "\n".join(sql), params


def get_filtered_count(user_id, category_key):
    sql, params = build_filtered_query(user_id, category_key, count_only=True)
    rows = db_query(sql, params)
    return int(rows[0]["total"]) if rows else 0


def get_filtered_products(user_id, category_key, offset=0):
    sql, params = build_filtered_query(user_id, category_key, offset=offset, count_only=False)
    return db_query(sql, params)


def expire_cart_items():
    expired = db_query(
        """
        SELECT id, product_id, reserved_quantity
        FROM tg_cart_items
        WHERE status = 'active'
          AND reserved_quantity > 0
          AND expires_at <= NOW()
        """
    )
    for item in expired:
        db_execute(
            "UPDATE ocoe_product SET quantity = quantity + %s WHERE product_id = %s",
            (int(item["reserved_quantity"]), int(item["product_id"])),
        )
        db_execute(
            """
            UPDATE tg_cart_items
            SET reserved_quantity = 0,
                released_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (item["id"],),
        )


async def cart_expirer_loop():
    while True:
        try:
            expire_cart_items()
        except Exception:
            pass
        await asyncio.sleep(30)


def add_to_cart(user_id, product_id):
    expire_cart_items()
    product = get_product(product_id)
    if not product:
        return False, "Товар не найден."
    existing = db_query(
        """
        SELECT reserved_quantity
        FROM tg_cart_items
        WHERE user_id = %s
          AND product_id = %s
          AND status = 'active'
        LIMIT 1
        """,
        (user_id, product_id),
    )
    if existing:
        if int(existing[0].get("reserved_quantity") or 0) > 0:
            return True, "Товар уже в корзине."
        return True, "Товар уже лежит в корзине. Наличие проверим при оформлении."

    if int(product.get("quantity") or 0) <= 0:
        return False, "Товара уже нет в наличии."

    updated = db_rowcount(
        """
        UPDATE ocoe_product
        SET quantity = quantity - 1
        WHERE product_id = %s
          AND quantity > 0
        """,
        (product_id,),
    )
    if updated <= 0:
        return False, "Товара уже нет в наличии."

    db_execute(
        """
        INSERT INTO tg_cart_items (user_id, product_id, status, reserved_quantity, created_at, updated_at, expires_at)
        VALUES (%s, %s, 'active', 1, NOW(), NOW(), DATE_ADD(NOW(), INTERVAL %s MINUTE))
        ON DUPLICATE KEY UPDATE
            status = 'active',
            reserved_quantity = 1,
            updated_at = NOW(),
            released_at = NULL,
            expires_at = DATE_ADD(NOW(), INTERVAL %s MINUTE)
        """,
        (user_id, product_id, CART_TTL_MINUTES, CART_TTL_MINUTES),
    )
    return True, "Товар добавлен в корзину."


def remove_from_cart(user_id, product_id):
    expire_cart_items()
    rows = db_query(
        """
        SELECT reserved_quantity
        FROM tg_cart_items
        WHERE user_id = %s AND product_id = %s AND status = 'active'
        LIMIT 1
        """,
        (user_id, product_id),
    )
    if rows and int(rows[0].get("reserved_quantity") or 0) > 0:
        db_execute(
            "UPDATE ocoe_product SET quantity = quantity + %s WHERE product_id = %s",
            (int(rows[0]["reserved_quantity"]), product_id),
        )
    db_execute(
        """
        UPDATE tg_cart_items
        SET status = 'removed',
            reserved_quantity = 0,
            released_at = NOW(),
            updated_at = NOW()
        WHERE user_id = %s AND product_id = %s AND status = 'active'
        """,
        (user_id, product_id),
    )


def reserve_cart_item_for_order(user_id, product_id):
    expire_cart_items()
    rows = db_query(
        """
        SELECT id, reserved_quantity
        FROM tg_cart_items
        WHERE user_id = %s
          AND product_id = %s
          AND status = 'active'
        LIMIT 1
        """,
        (user_id, product_id),
    )
    if not rows:
        return False, "Товара нет в вашей корзине."
    if int(rows[0].get("reserved_quantity") or 0) > 0:
        return True, ""
    updated = db_rowcount(
        """
        UPDATE ocoe_product
        SET quantity = quantity - 1
        WHERE product_id = %s
          AND quantity > 0
        """,
        (product_id,),
    )
    if updated <= 0:
        return False, "В вашей корзине есть товар, которого уже нет в наличии."
    db_execute(
        """
        UPDATE tg_cart_items
        SET reserved_quantity = 1,
            updated_at = NOW(),
            released_at = NULL,
            expires_at = DATE_ADD(NOW(), INTERVAL %s MINUTE)
        WHERE id = %s
        """,
        (CART_TTL_MINUTES, rows[0]["id"]),
    )
    return True, ""


def mark_cart_item_ordered(user_id, product_id, order_code):
    db_execute(
        """
        UPDATE tg_cart_items
        SET status = 'ordered',
            reserved_quantity = 0,
            order_code = %s,
            updated_at = NOW()
        WHERE user_id = %s
          AND product_id = %s
          AND status = 'active'
        """,
        (order_code, user_id, product_id),
    )


def mark_cart_items_ordered(user_id, product_ids, order_code):
    for product_id in product_ids:
        mark_cart_item_ordered(user_id, product_id, order_code)


def get_cart_items(user_id):
    expire_cart_items()
    return db_query(
        """
        SELECT
            tci.product_id,
            tci.expires_at,
            pd.name,
            p.model,
            p.price,
            p.quantity,
            tci.reserved_quantity,
            tci.expires_at
        FROM tg_cart_items tci
        JOIN ocoe_product p ON p.product_id = tci.product_id
        JOIN ocoe_product_description pd ON pd.product_id = p.product_id AND pd.language_id = %s
        WHERE tci.user_id = %s
          AND tci.status = 'active'
        ORDER BY tci.updated_at DESC
        """,
        (LANGUAGE_ID, user_id),
    )


def first_available_cart_item(user_id):
    items = get_cart_items(user_id)
    for item in items:
        if int(item.get("quantity") or 0) > 0 or int(item.get("reserved_quantity") or 0) > 0:
            return item
    return None


def available_cart_items(user_id):
    items = get_cart_items(user_id)
    return [
        item
        for item in items
        if int(item.get("quantity") or 0) > 0 or int(item.get("reserved_quantity") or 0) > 0
    ]


def cart_text(items, user_id=None):
    if not items:
        return tr(user_id, "empty_cart")
    lines = [f"<b>{tr(user_id, 'cart_title')}</b>"]
    total = Decimal("0")
    for item in items:
        available = int(item.get("quantity") or 0) > 0 or int(item.get("reserved_quantity") or 0) > 0
        if available:
            total += Decimal(str(item.get("price") or 0))
    missing = [item for item in items if int(item.get("quantity") or 0) <= 0 and int(item.get("reserved_quantity") or 0) <= 0]
    if missing:
        lines.append(f"{OUT_OF_STOCK_EMOJI_HTML} {tr(user_id, 'cart_missing')}")
    lines.append(f"<b>{tr(user_id, 'total')}:</b> {format_price(total)}")
    return "\n".join(lines)


def get_product(product_id):
    rows = db_query(
        """
        SELECT
            p.product_id,
            pd.name,
            pd.description,
            p.price,
            p.image,
            p.weight,
            (
                SELECT pi.image
                FROM ocoe_product_image pi
                WHERE pi.product_id = p.product_id
                  AND LOWER(SUBSTRING_INDEX(pi.image, '.', -1)) IN ('jpg', 'jpeg', 'png', 'webp')
                ORDER BY pi.sort_order, pi.product_image_id
                LIMIT 1
            ) AS fallback_image,
            p.model,
            p.quantity
        FROM ocoe_product p
        JOIN ocoe_product_description pd ON pd.product_id = p.product_id
        WHERE p.product_id = %s
          AND p.status = 1
          AND pd.language_id = %s
        LIMIT 1
        """,
        (product_id, LANGUAGE_ID),
    )
    return rows[0] if rows else None


def local_media_path(product):
    candidates = [
        original_image_path(product.get("image") or ""),
        original_image_path(product.get("fallback_image") or ""),
    ]
    expanded_candidates = []
    for image in candidates:
        if is_placeholder_or_cache(image):
            continue
        expanded_candidates.append(image)
        stem = Path(image).stem
        suffix = Path(image).suffix
        parent = str(Path(image).parent).replace("\\", "/")
        if stem and suffix:
            base_stems = [stem]
            if stem[-1:].isalpha():
                base_stems.append(stem[:-1])
            for base_stem in base_stems:
                for alt_suffix in (".jpg", ".jpeg", ".png", ".webp", ".mp4"):
                    expanded_candidates.append(f"{parent}/{base_stem}{alt_suffix}")
                if not base_stem.endswith("s"):
                    expanded_candidates.append(f"{parent}/{base_stem}s.mp4")

    seen = set()
    unique_candidates = []
    for image in expanded_candidates:
        if image not in seen:
            seen.add(image)
            unique_candidates.append(image)

    for image in unique_candidates:
        local_image = IMAGE_ROOT / image
        if local_image.exists() and local_image.suffix.lower() in PHOTO_EXTENSIONS:
            return local_image, "photo"

    for image in unique_candidates:
        local_video = IMAGE_ROOT / image
        if local_video.exists() and local_video.suffix.lower() in VIDEO_EXTENSIONS:
            return local_video, "video"

    return None, None


def public_media_url(product):
    candidates = [
        original_image_path(product.get("fallback_image") or ""),
        original_image_path(product.get("image") or ""),
    ]
    for image in candidates:
        if is_placeholder_or_cache(image):
            continue
        suffix = Path(image).suffix.lower()
        if suffix not in PHOTO_EXTENSIONS and suffix not in VIDEO_EXTENSIONS:
            continue
        encoded = quote(image.replace("\\", "/"), safe="/")
        media_type = "photo" if suffix in PHOTO_EXTENSIONS else "video"
        return PUBLIC_IMAGE_URL + encoded, media_type
    return None, None


def public_media_urls_for_product(product_id):
    product = get_product(product_id)
    if not product:
        return []
    media = []
    for image in [product.get("fallback_image") or "", product.get("image") or ""]:
        path = original_image_path(image)
        if is_placeholder_or_cache(path):
            continue
        suffix = Path(path).suffix.lower()
        if suffix in PHOTO_EXTENSIONS or suffix in VIDEO_EXTENSIONS:
            media_type = "photo" if suffix in PHOTO_EXTENSIONS else "video"
            media.append((PUBLIC_IMAGE_URL + quote(path.replace("\\", "/"), safe="/"), media_type))

    rows = db_query(
        """
        SELECT image
        FROM ocoe_product_image
        WHERE product_id = %s
        ORDER BY sort_order, product_image_id
        """,
        (product_id,),
    )
    for row in rows:
        path = original_image_path(row["image"])
        if is_placeholder_or_cache(path):
            continue
        suffix = Path(path).suffix.lower()
        if suffix in PHOTO_EXTENSIONS or suffix in VIDEO_EXTENSIONS:
            media_type = "photo" if suffix in PHOTO_EXTENSIONS else "video"
            media.append((PUBLIC_IMAGE_URL + quote(path.replace("\\", "/"), safe="/"), media_type))

    unique = []
    seen = set()
    for url, media_type in media:
        if url in seen:
            continue
        seen.add(url)
        unique.append((url, media_type))
    return sorted(unique, key=lambda item: 1 if item[1] == "video" else 0)


async def get_http_session():
    global HTTP_SESSION
    if HTTP_SESSION is None or HTTP_SESSION.closed:
        headers = {"User-Agent": "Mozilla/5.0"}
        timeout = aiohttp.ClientTimeout(total=25)
        connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
        HTTP_SESSION = aiohttp.ClientSession(timeout=timeout, headers=headers, connector=connector)
    return HTTP_SESSION


async def download_public_media(url):
    session = await get_http_session()
    async with session.get(url) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        data = await response.read()
    filename = Path(url.split("?", 1)[0]).name or "product.jpg"
    return data, filename, content_type


async def show_text(callback: CallbackQuery, text, reply_markup=None, parse_mode=None):
    if isinstance(reply_markup, ReplyKeyboardMarkup):
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        if not callback.message.text:
            await callback.message.delete()
        return
    if callback.message.text:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        await callback.message.delete()


def product_text(product, has_media=True, user_id=None):
    text = [detail_text(product, user_id=user_id)]
    if not has_media:
        text.append(tr(user_id, "no_media"))
    return "\n".join(text)


async def send_product(callback: CallbackQuery, product_id: int, in_cart=False, back_to_cart=False):
    product = get_product(product_id)
    if not product:
        await show_text(callback, tr(callback.from_user.id, "product_not_found"), reply_markup=main_menu(callback.from_user.id))
        return

    media_items = public_media_urls_for_product(product_id)
    public_media, public_media_type = media_items[0] if media_items else public_media_url(product)
    caption = product_text(product, has_media=public_media is not None, user_id=callback.from_user.id)
    in_cart = in_cart or user_has_cart_item(callback.from_user.id, product_id)
    markup = product_keyboard(product_id, len(media_items) or 1, 0, in_cart=in_cart, back_to_cart=back_to_cart, user_id=callback.from_user.id)

    if public_media_type == "photo":
        try:
            data, filename, content_type = await download_public_media(public_media)
            if not content_type.startswith("image/"):
                raise ValueError(f"Unexpected content type: {content_type}")
            await callback.message.answer_photo(
                photo=BufferedInputFile(data, filename=filename),
                caption=caption[:1024],
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
            await callback.message.delete()
        except Exception:
            await show_text(callback, caption, parse_mode=ParseMode.HTML, reply_markup=markup)
    elif public_media_type == "video":
        try:
            data, filename, content_type = await download_public_media(public_media)
            if not content_type.startswith("video/"):
                raise ValueError(f"Unexpected content type: {content_type}")
            await callback.message.answer_video(
                video=BufferedInputFile(data, filename=filename),
                caption=caption[:1024],
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
            await callback.message.delete()
        except Exception:
            await show_text(callback, caption, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await show_text(callback, caption, parse_mode=ParseMode.HTML, reply_markup=markup)


async def send_product_card(message: Message, product_id: int, user_id=None):
    product = get_product(product_id)
    if not product:
        return

    media_items = public_media_urls_for_product(product_id)
    public_media, public_media_type = media_items[0] if media_items else (None, None)
    user_id = user_id or message.chat.id
    caption = product_text(product, has_media=public_media is not None, user_id=user_id)
    inline_markup = product_keyboard(product_id, len(media_items) or 1, 0, user_id=user_id)
    
    # Получаем состояние пользователя для определения правильной ReplyKeyboard
    state = USER_STATES.get(user_id, {})
    view = state.get("view")
    if view == "search_results":
        total = state.get("search_total", 0)
        offset = state.get("search_offset", 0)
        reply_kb = search_results_keyboard(user_id, total, offset)
    else:
        reply_kb = main_menu(user_id)

    if public_media_type == "photo":
        try:
            data, filename, content_type = await download_public_media(public_media)
            if not content_type.startswith("image/"):
                raise ValueError(f"Unexpected content type: {content_type}")
            await message.answer_photo(
                photo=BufferedInputFile(data, filename=filename),
                caption=caption[:1024],
                parse_mode=ParseMode.HTML,
                reply_markup=inline_markup,
            )
            return
        except Exception:
            pass

    if public_media_type == "video":
        try:
            data, filename, content_type = await download_public_media(public_media)
            if not content_type.startswith("video/"):
                raise ValueError(f"Unexpected content type: {content_type}")
            await message.answer_video(
                video=BufferedInputFile(data, filename=filename),
                caption=caption[:1024],
                parse_mode=ParseMode.HTML,
                reply_markup=inline_markup,
            )
            return
        except Exception:
            pass

    await message.answer(caption, parse_mode=ParseMode.HTML, reply_markup=inline_markup)


async def send_media_url(message: Message, url, media_type, caption=None, reply_markup=None):
    try:
        data, filename, content_type = await download_public_media(url)
        if media_type == "photo" and content_type.startswith("image/"):
            await message.answer_photo(
                photo=BufferedInputFile(data, filename=filename),
                caption=caption,
                parse_mode=ParseMode.HTML if caption else None,
                reply_markup=reply_markup,
            )
            return True
        if media_type == "video" and content_type.startswith("video/"):
            await message.answer_video(
                video=BufferedInputFile(data, filename=filename),
                caption=caption,
                parse_mode=ParseMode.HTML if caption else None,
                reply_markup=reply_markup,
            )
            return True
    except Exception:
        return False
    return False


async def download_media_item(url, media_type):
    data, filename, content_type = await download_public_media(url)
    if media_type == "photo" and content_type.startswith("image/"):
        return InputMediaPhoto(media=BufferedInputFile(data, filename=filename))
    if media_type == "video" and content_type.startswith("video/"):
        return InputMediaVideo(media=BufferedInputFile(data, filename=filename))
    return None


async def build_product_input_media(product, url, media_type, user_id=None):
    data, filename, content_type = await download_public_media(url)
    caption = product_text(product, has_media=True, user_id=user_id)[:1024]
    if media_type == "photo" and content_type.startswith("image/"):
        return InputMediaPhoto(
            media=BufferedInputFile(data, filename=filename),
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
    if media_type == "video" and content_type.startswith("video/"):
        return InputMediaVideo(
            media=BufferedInputFile(data, filename=filename),
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
    return None


async def build_manager_product_input_media(product, url, media_type):
    data, filename, content_type = await download_public_media(url)
    caption = product_text(product, has_media=True, user_id=None)[:1024]
    if media_type == "photo" and content_type.startswith("image/"):
        return InputMediaPhoto(
            media=BufferedInputFile(data, filename=filename),
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
    if media_type == "video" and content_type.startswith("video/"):
        return InputMediaVideo(
            media=BufferedInputFile(data, filename=filename),
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
    return None


async def send_manager_product_card(callback: CallbackQuery, order_code: str, product_id: int):
    product = get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    media_items = public_media_urls_for_product(product_id)
    public_media, public_media_type = media_items[0] if media_items else public_media_url(product)
    caption = product_text(product, has_media=public_media is not None, user_id=None)
    markup = manager_product_keyboard(order_code, product_id, len(media_items) or 1, 0)

    if public_media_type == "photo":
        try:
            data, filename, content_type = await download_public_media(public_media)
            if not content_type.startswith("image/"):
                raise ValueError(f"Unexpected content type: {content_type}")
            await callback.message.answer_photo(
                photo=BufferedInputFile(data, filename=filename),
                caption=caption[:1024],
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        except Exception:
            await callback.message.answer(caption, parse_mode=ParseMode.HTML, reply_markup=markup)
    elif public_media_type == "video":
        try:
            data, filename, content_type = await download_public_media(public_media)
            if not content_type.startswith("video/"):
                raise ValueError(f"Unexpected content type: {content_type}")
            await callback.message.answer_video(
                video=BufferedInputFile(data, filename=filename),
                caption=caption[:1024],
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        except Exception:
            await callback.message.answer(caption, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await callback.message.answer(caption, parse_mode=ParseMode.HTML, reply_markup=markup)
    await callback.answer()


async def send_client_order_product_card(callback: CallbackQuery, order_code: str, product_id: int):
    product = get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    media_items = public_media_urls_for_product(product_id)
    public_media, public_media_type = media_items[0] if media_items else public_media_url(product)
    caption = product_text(product, has_media=public_media is not None, user_id=callback.from_user.id)
    markup = client_order_product_keyboard(order_code, product_id, len(media_items) or 1, 0, callback.from_user.id)

    if public_media_type == "photo":
        try:
            data, filename, content_type = await download_public_media(public_media)
            if not content_type.startswith("image/"):
                raise ValueError(f"Unexpected content type: {content_type}")
            await callback.message.answer_photo(
                photo=BufferedInputFile(data, filename=filename),
                caption=caption[:1024],
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        except Exception:
            await callback.message.answer(caption, parse_mode=ParseMode.HTML, reply_markup=markup)
    elif public_media_type == "video":
        try:
            data, filename, content_type = await download_public_media(public_media)
            if not content_type.startswith("video/"):
                raise ValueError(f"Unexpected content type: {content_type}")
            await callback.message.answer_video(
                video=BufferedInputFile(data, filename=filename),
                caption=caption[:1024],
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        except Exception:
            await callback.message.answer(caption, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await callback.message.answer(caption, parse_mode=ParseMode.HTML, reply_markup=markup)
    await callback.answer()


def manager_chat_targets():
    data = seed_env_managers(manager_access_data())
    targets = []
    for chat_id, record in data.get("users", {}).items():
        if record.get("role") in {"manager", "admin"}:
            targets.append(chat_id)
    return sorted(set(targets))


async def refresh_manager_chat_ids():
    if not manager_bot:
        return []
    return manager_chat_targets()


async def notify_manager_access_request(user):
    if not manager_bot:
        return False
    admins = manager_admin_chat_ids()
    if not admins:
        return False
    data = manager_access_data()
    pending = data.get("pending", {}).get(str(user.id), {})
    display_name = pending.get("display_name") or manager_user_label(user)
    text = (
        "Новая заявка на доступ к менеджерскому боту:\n"
        f"{html.escape(display_name)}\n"
        f"Telegram: {html.escape(manager_user_label(user))}\n"
        f"Телефон: <code>{html.escape(pending.get('phone') or '')}</code>"
    )
    sent = False
    MANAGER_ACCESS_REQUEST_MESSAGES[str(user.id)] = {}
    for admin_id in admins:
        try:
            message = await manager_bot.send_message(
                admin_id,
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=manager_access_keyboard(user.id, admin_id),
            )
            MANAGER_ACCESS_REQUEST_MESSAGES[str(user.id)][str(admin_id)] = message.message_id
            sent = True
        except Exception:
            pass
    return sent


async def request_manager_access(message: Message):
    data = manager_access_data()
    pending = data.get("pending", {}).get(str(message.from_user.id))
    if not pending or not pending.get("display_name"):
        await request_manager_name(message)
        return
    if not pending.get("phone"):
        await request_manager_contact(message)
        return
    await notify_manager_access_request(message.from_user)
    await message.answer("Заявка уже ожидает решения администратора.")


async def request_manager_name(message: Message):
    MANAGER_NAME_DRAFTS[message.from_user.id] = True
    await message.answer(
        "Введите ваше имя и фамилию одним сообщением.",
        reply_markup=ReplyKeyboardRemove(),
    )


async def request_manager_contact(message: Message):
    MANAGER_CONTACT_DRAFTS[message.from_user.id] = True
    await message.answer(
        "Теперь отправьте свой контакт, чтобы администратор мог с вами связаться.",
        reply_markup=build_reply_keyboard([[KeyboardButton(text="📱 Отправить контакт", request_contact=True)]]),
    )


def next_tg_order_code():
    rows = db_query("SELECT MAX(id) AS max_id FROM tg_orders")
    next_id = int((rows[0].get("max_id") if rows else 0) or 0) + 1
    return f"tgOrder{next_id:04d}"


def order_summary_name(items):
    names = [html.unescape(str(item.get("name") or "")).strip() for item in items]
    if len(names) == 1:
        return names[0][:255]
    summary = f"{len(names)} товара: " + ", ".join(names)
    return summary[:252] + "..." if len(summary) > 255 else summary


def order_customer_name(order):
    name = order.get("customer_name") or f"{order.get('first_name') or ''} {order.get('last_name') or ''}".strip()
    return name.strip()


def client_language_label(user_id):
    lang = user_lang(user_id)
    if lang == "uz":
        return "O'zbekcha"
    if lang == "ru":
        return "Русский"
    return str(lang or "unknown")


def client_cancel_reason_hint(user_id):
    lang = user_lang(user_id)
    if lang == "uz":
        return "Клиент использует узбекский язык. Причину отмены желательно написать на узбекском."
    return "Клиент использует русский язык. Причину отмены желательно написать на русском."


def create_tg_order_item(order_code, item, now):
    db_execute(
        """
        INSERT INTO tg_order_items
        SET order_code = %s,
            product_id = %s,
            product_name = %s,
            product_model = %s,
            product_price = %s,
            product_url = %s,
            created_at = %s
        """,
        (
            order_code,
            int(item["product_id"]),
            html.unescape(str(item.get("name") or "")),
            str(item.get("model") or ""),
            Decimal(str(item.get("price") or 0)),
            product_site_link(item["product_id"]).replace("&amp;", "&"),
            now,
        ),
    )


def get_tg_order_items(order_code):
    return db_query(
        """
        SELECT product_id, product_name, product_model, product_price, product_url
        FROM tg_order_items
        WHERE order_code = %s
        ORDER BY id
        """,
        (order_code,),
    )


def get_order_reviews(order_code):
    order = get_tg_order(order_code)
    if order and order.get("client_review"):
        return [
            {
                "review_text": order.get("client_review") or "",
                "created_at": order.get("client_review_at") or "",
            }
        ]
    return []


def get_order_review(order_code, product_id):
    reviews = get_order_reviews(order_code)
    return reviews[0] if reviews else None


def save_order_review(order_code, product_id, user_id, review_text):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        db_execute(
            """
            UPDATE tg_orders
            SET client_review = %s,
                client_review_at = %s,
                updated_at = %s
            WHERE order_code = %s
              AND client_tg_id = %s
            """,
            (review_text, now, now, order_code, int(user_id)),
        )
        return True
    except Exception:
        return save_fallback_order_review(order_code, product_id, user_id, review_text)


def order_has_client_review(order_code):
    order = get_tg_order(order_code)
    return bool(order and order.get("client_review"))


def load_fallback_reviews():
    try:
        if not REVIEW_FALLBACK_PATH.exists():
            return {}
        return json.loads(REVIEW_FALLBACK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_fallback_reviews(data):
    try:
        REVIEW_FALLBACK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def fallback_order_reviews(order_code):
    data = load_fallback_reviews()
    prefix = f"{order_code}:"
    rows = []
    for key, review in data.items():
        if not key.startswith(prefix):
            continue
        rows.append(
            {
                "product_id": int(review.get("product_id") or 0),
                "review_text": review.get("review_text") or "",
                "created_at": review.get("created_at") or "",
            }
        )
    return rows


def save_fallback_order_review(order_code, product_id, user_id, review_text):
    data = load_fallback_reviews()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data[f"{order_code}:{int(product_id)}"] = {
        "order_code": order_code,
        "product_id": int(product_id),
        "client_tg_id": int(user_id),
        "review_text": review_text,
        "created_at": data.get(f"{order_code}:{int(product_id)}", {}).get("created_at") or now,
        "updated_at": now,
    }
    return save_fallback_reviews(data)


def first_reviewable_product_id(order_code):
    order = get_tg_order(order_code)
    if not order or order.get("client_review"):
        return None
    return int(order["product_id"])


def order_review_product_label(order_code, product_id):
    items = get_tg_order_items(order_code)
    for item in items:
        if int(item["product_id"]) == int(product_id):
            return html.unescape(item.get("product_name") or "")
    order = get_tg_order(order_code)
    if order and int(order["product_id"]) == int(product_id):
        return html.unescape(order.get("product_name") or "")
    return str(product_id)


def order_has_product(order_code, product_id):
    items = get_tg_order_items(order_code)
    if items:
        return any(int(item["product_id"]) == int(product_id) for item in items)
    order = get_tg_order(order_code)
    return bool(order and int(order["product_id"]) == int(product_id))


def restore_order_stock(order):
    items = get_tg_order_items(order["order_code"]) if order else []
    if items:
        for item in items:
            db_execute(
                "UPDATE ocoe_product SET quantity = quantity + 1 WHERE product_id = %s",
                (int(item["product_id"]),),
            )
        return
    if order:
        db_execute(
            "UPDATE ocoe_product SET quantity = quantity + 1 WHERE product_id = %s",
            (int(order["product_id"]),),
        )


def create_tg_order(draft):
    user = draft["user"]
    items = get_cart_items(user.id)
    if not items:
        return None, "Корзина пустая."
    missing = [
        item
        for item in items
        if int(item.get("quantity") or 0) <= 0 and int(item.get("reserved_quantity") or 0) <= 0
    ]
    if missing:
        return None, "В вашей корзине есть товары, которых уже нет в наличии."
    for item in items:
        ok, error = reserve_cart_item_for_order(user.id, item["product_id"])
        if not ok:
            return None, error
    order_code = next_tg_order_code()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    first_item = items[0]
    product_ids = [int(item["product_id"]) for item in items]
    total = sum(Decimal(str(item.get("price") or 0)) for item in items)
    latitude = draft.get("delivery_lat")
    longitude = draft.get("delivery_lng")
    db_execute(
        """
        INSERT INTO tg_orders
        SET order_code = %s,
            product_id = %s,
            product_name = %s,
            product_model = %s,
            product_price = %s,
            product_url = %s,
            client_tg_id = %s,
            client_username = %s,
            first_name = %s,
            last_name = %s,
            customer_name = %s,
            phone = %s,
            region = %s,
            delivery_lat = %s,
            delivery_lng = %s,
            status = 'new',
            created_at = %s,
            updated_at = %s
        """,
        (
            order_code,
            int(first_item["product_id"]),
            order_summary_name(items),
            str(first_item.get("model") or ""),
            total,
            product_site_link(first_item["product_id"]).replace("&amp;", "&"),
            int(user.id),
            user.username or "",
            draft.get("first_name") or "",
            draft.get("last_name") or "",
            draft.get("customer_name") or "",
            draft.get("phone") or "",
            draft.get("region") or "",
            latitude,
            longitude,
            now,
            now,
        ),
    )
    for item in items:
        create_tg_order_item(order_code, item, now)
    mark_cart_items_ordered(user.id, product_ids, order_code)
    return order_code, None


def localized_order_error(user_id, error):
    if not error:
        return ""
    if "Корзина пустая" in error:
        return tr(user_id, "empty_cart")
    if "корзин" in error.lower() and "налич" in error.lower():
        return tr(user_id, "cart_missing")
    if "Товар не найден" in error:
        return tr(user_id, "product_not_found")
    if "Заказ не найден" in error:
        return tr(user_id, "order_not_found")
    return error


def get_tg_order(order_code):
    rows = db_query("SELECT * FROM tg_orders WHERE order_code = %s LIMIT 1", (order_code,))
    return rows[0] if rows else None


def get_client_tg_order(order_code, user_id):
    rows = db_query(
        "SELECT * FROM tg_orders WHERE order_code = %s AND client_tg_id = %s LIMIT 1",
        (order_code, int(user_id)),
    )
    return rows[0] if rows else None


def update_tg_order_status(order_code, status, manager):
    order = get_tg_order(order_code)
    old_status = order.get("status") if order else None
    cancel_statuses = {"completed_failed", "cancelled"}
    restorable_statuses = {"new", "pending", "processing", "in_transit", "accepted", "contacted"}
    if order and status in cancel_statuses and old_status in restorable_statuses:
        restore_order_stock(order)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute(
        """
        UPDATE tg_orders
        SET status = %s,
            manager_tg_id = %s,
            manager_username = %s,
            updated_at = %s
        WHERE order_code = %s
        """,
        (status, int(manager.id), manager.username or "", now, order_code),
    )


def cancel_client_order(order_code, user_id):
    order = get_client_tg_order(order_code, user_id)
    if not order:
        return False, "Заказ не найден.", None
    status = order.get("status") or "new"
    if status == "in_transit":
        return False, "К сожалению, отменить заказ уже невозможно: он передан в доставку. Если возникли вопросы, свяжитесь, пожалуйста, с оператором.", order
    if status in {"completed", "done", "completed_success"}:
        return False, "К сожалению, этот заказ уже завершен. Если возникли вопросы, свяжитесь, пожалуйста, с оператором.", order
    if status in {"cancelled", "completed_failed"}:
        return False, "Этот заказ уже отменен.", order
    if status in {"new", "pending", "processing", "accepted", "contacted"}:
        restore_order_stock(order)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute("UPDATE tg_orders SET status = 'cancelled', updated_at = %s WHERE order_code = %s", (now, order_code))
    return True, "Заказ отменен.", get_client_tg_order(order_code, user_id)


def client_order_text(order):
    user_id = order.get("client_tg_id")
    items = get_tg_order_items(order["order_code"])
    reviews = get_order_reviews(order["order_code"])
    status = ORDER_STATUS_I18N.get(user_lang(user_id), ORDER_STATUS_I18N["ru"]).get(order.get("status"), order.get("status") or "Ожидание")
    lines = [
        f"<b>{tr(user_id, 'order')} {html.escape(display_order_code(order['order_code']))}</b>",
        f"<b>{tr(user_id, 'status')}:</b> {html.escape(status)}",
        "",
        f"<b>{tr(user_id, 'total')}:</b> {format_price(order['product_price'])}",
    ]
    if items:
        lines.append(f"<b>{tr(user_id, 'items')}:</b>")
        for index, item in enumerate(items, 1):
            name = html.escape(html.unescape(item["product_name"]))
            model = html.escape(str(item.get("product_model") or ""))
            link = item.get("product_url") or product_site_link(item["product_id"]).replace("&amp;", "&")
            line = f"{index}. <a href=\"{html.escape(link)}\">{name}</a> — {format_price(item['product_price'])}"
            if model:
                line += f" / <code>{model}</code>"
            lines.append(line)
    else:
        name = html.escape(html.unescape(order["product_name"]))
        model = html.escape(str(order.get("product_model") or ""))
        link = order.get("product_url") or product_site_link(order["product_id"]).replace("&amp;", "&")
        lines.append(f"<b>{tr(user_id, 'item')}:</b> <a href=\"{html.escape(link)}\">{name}</a>")
        if model:
            lines.append(f"<b>{tr(user_id, 'model')}:</b> <code>{model}</code>")
    if reviews:
        lines.append("")
        lines.append(f"<b>{tr(user_id, 'review')}:</b>")
        for review in reviews:
            lines.append(f"<i>{html.escape(review.get('review_text') or '')}</i>")
    lines.extend(
        [
            f"<b>{tr(user_id, 'phone')}:</b> {html.escape(order.get('phone') or '')}",
            f"<b>{'Имя' if user_lang(user_id) == 'ru' else 'Ism'}:</b> {html.escape(order_customer_name(order))}",
            f"<b>{tr(user_id, 'region')}:</b> {html.escape(order.get('region') or '')}",
            f"<b>{tr(user_id, 'date')}:</b> {order['created_at']}",
        ]
    )
    return "\n".join(lines)


def manager_order_text(order):
    username = f"@{order['client_username']}" if order.get("client_username") else "без username"
    items = get_tg_order_items(order["order_code"])
    reviews = get_order_reviews(order["order_code"])
    status = TG_ORDER_STATUSES.get(order.get("status"), order.get("status") or "Новый")
    lines = [
        f"<b>Новая заявка {html.escape(display_order_code(order['order_code']))}</b>",
        '<b>Источник:</b> <tg-emoji emoji-id="5244867092389336658">🌟</tg-emoji> Telegram',
        f"<b>Статус:</b> {html.escape(status)}",
        "",
        f"<b>Итого:</b> {format_price_amount(order['product_price'])}",
    ]
    if items:
        lines.append("<b>Товары:</b>")
        for index, item in enumerate(items, 1):
            name = html.escape(html.unescape(item["product_name"]))
            model = html.escape(str(item.get("product_model") or ""))
            link = item.get("product_url") or product_site_link(item["product_id"]).replace("&amp;", "&")
            line = f"{index}. <a href=\"{html.escape(link)}\">{name}</a> — {format_price_amount(item['product_price'])}"
            if model:
                line += f" / <code>{model}</code>"
            lines.append(line)
    else:
        name = html.escape(html.unescape(order["product_name"]))
        model = html.escape(str(order.get("product_model") or ""))
        link = order.get("product_url") or product_site_link(order["product_id"]).replace("&amp;", "&")
        lines.append(f"<b>Товар:</b> <a href=\"{html.escape(link)}\">{name}</a>")
        if model:
            lines.append(f"<b>Модель:</b> <code>{model}</code>")
    lines.extend(
        [
            "",
            "<b>Клиент:</b>",
            html.escape(order_customer_name(order)),
            f"Язык клиента: <b>{html.escape(client_language_label(order.get('client_tg_id')))}</b>",
            f"{html.escape(username)}",
            f"Телефон: {html.escape(order.get('phone') or '')}",
            f"Город/область: {html.escape(order.get('region') or '')}",
            f"Дата: {order['created_at']}",
        ]
    )
    if reviews:
        lines.extend(["", "<b>Отзывы клиента:</b>"])
        for review in reviews:
            lines.append(f"<i>{html.escape(review.get('review_text') or '')}</i>")
    return "\n".join(line for line in lines if line != "")


async def send_order_location(bot_instance, chat_id, order):
    if not bot_instance or order.get("delivery_lat") is None or order.get("delivery_lng") is None:
        return False
    try:
        await bot_instance.send_location(
            chat_id,
            latitude=float(order["delivery_lat"]),
            longitude=float(order["delivery_lng"]),
        )
        return True
    except Exception:
        return False


async def show_manager_order(callback: CallbackQuery, order_code, send_location=False):
    if not manager_has_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    order = get_tg_order(order_code)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    text = manager_order_text(order)
    markup = manager_order_keyboard(order_code, order.get("status"), callback.from_user.id)
    if callback.message.text or callback.message.caption:
        if callback.message.caption:
            await callback.message.edit_caption(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        else:
            await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    await callback.answer()


def client_status_text(order, status, reason=None):
    user_id = order.get("client_tg_id")
    status_label = ORDER_STATUS_I18N.get(user_lang(user_id), ORDER_STATUS_I18N["ru"]).get(status, TG_ORDER_STATUSES.get(status, status))
    order_id = html.escape(display_order_code(order["order_code"]))
    if status in {"completed", "done", "completed_success"}:
        return (
            tr(user_id, "status_changed").format(order=order_id, status=html.escape(status_label))
            + "\n\n"
            + tr(user_id, "order_completed_thanks")
            + "\n"
            + tr(user_id, "review_request")
        )
    if status in {"cancelled", "completed_failed"}:
        if reason:
            return tr(user_id, "order_cancelled_reason").format(order=order_id, reason=html.escape(reason))
        return tr(user_id, "order_cancelled_notice").format(order=order_id)
    return tr(user_id, "status_changed").format(order=order_id, status=html.escape(status_label))


async def notify_client_status_change(order, status, reason=None):
    if not order or not order.get("client_tg_id"):
        return False
    try:
        user_id = int(order["client_tg_id"])
        markup = review_request_keyboard(order["order_code"], user_id) if status in {"completed", "done", "completed_success"} else main_menu(user_id)
        await bot.send_message(
            user_id,
            client_status_text(order, status, reason=reason),
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
        return True
    except Exception:
        return False


async def notify_managers(order_code):
    if not manager_bot:
        return False

    targets = await refresh_manager_chat_ids()
    if not targets:
        return False

    order = get_tg_order(order_code)
    if not order:
        return False

    text = manager_order_text(order)
    try:
        sent_any = False
        for chat_id in targets:
            await manager_bot.send_message(chat_id, text, parse_mode=ParseMode.HTML, reply_markup=manager_order_keyboard(order_code, order.get("status")))
            sent_any = True
        return sent_any
    except Exception:
        return False


async def send_cards_page(callback: CallbackQuery, products, offset, kind, category_id=None):
    page_products = products[:5]
    has_next = len(products) > 5
    if not page_products:
        await show_text(callback, "Товары не найдены.", reply_markup=main_menu(callback.from_user.id))
        await callback.answer()
        return

    # Отправляем карточки товаров
    await asyncio.gather(
        *(send_product_card(callback.message, product["product_id"], callback.from_user.id) for product in page_products)
    )

    # Отправляем навигацию с сохранением ReplyKeyboard
    await callback.message.answer(
        "Показал 5 товаров. Можно открыть следующий набор.",
        reply_markup=cards_nav_keyboard(kind, offset, has_next, category_id),
    )
    await callback.answer()


bot = Bot(BOT_TOKEN)
dp = Dispatcher()
manager_bot = Bot(MANAGER_BOT_TOKEN) if MANAGER_BOT_TOKEN else None


def cancel_search(user_id):
    SEARCH_TOKENS[user_id] = SEARCH_TOKENS.get(user_id, 0) + 1
    for task in SEARCH_TASKS.pop(user_id, []):
        if not task.done():
            task.cancel()


async def send_search_results(message: Message, user_id, category_key, offset=0):
    search_token = SEARCH_TOKENS.get(user_id, 0) + 1
    SEARCH_TOKENS[user_id] = search_token
    total = get_filtered_count(user_id, category_key)
    products = get_filtered_products(user_id, category_key, offset)
    category_title = category_plain_title(user_id, category_key)
    filter_text = selected_filters_text(user_id)
    shown_from = 0 if total == 0 else offset + 1
    shown_to = min(offset + PAGE_SIZE, total)
    filters_suffix = f" ({filter_text})" if filter_text else ""
    text = tr(user_id, "search_result").format(category=category_title, filters=filters_suffix, total=total)
    text += "\n" + tr(user_id, "shown").format(from_=shown_from, to=shown_to, total=total)

    state = USER_STATES.setdefault(user_id, {})
    state["view"] = "search_results"
    state["category_key"] = category_key
    state["search_offset"] = offset
    state["search_total"] = total

    old_message_id = state.get("search_status_message_id")
    if old_message_id:
        try:
            await bot.delete_message(message.chat.id, old_message_id)
        except Exception:
            pass
    
    # Отправляем статус с ReplyKeyboard
    reply_kb = search_results_keyboard(user_id, total, offset)
    sent = await message.answer(text, reply_markup=reply_kb)
    state["search_status_message_id"] = sent.message_id

    async def send_current_product(product_id):
        current_state = USER_STATES.get(user_id, {})
        if SEARCH_TOKENS.get(user_id) != search_token or current_state.get("view") != "search_results":
            return
        await send_product_card(message, product_id, user_id)

    current_state = USER_STATES.get(user_id, {})
    if SEARCH_TOKENS.get(user_id) == search_token and current_state.get("view") == "search_results":
        tasks = [asyncio.create_task(send_current_product(product["product_id"])) for product in products[:PAGE_SIZE]]
        SEARCH_TASKS[user_id] = tasks
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            if SEARCH_TASKS.get(user_id) == tasks:
                SEARCH_TASKS.pop(user_id, None)


@dp.message(CommandStart())
async def start(message: Message, bot: Bot):
    if MANAGER_BOT_TOKEN and getattr(bot, "token", "") == MANAGER_BOT_TOKEN:
        if manager_has_access(message.from_user.id):
            await message.answer(
                "Менеджерский бот Diamant.",
                reply_markup=manager_main_keyboard(message.from_user.id),
            )
            return
        await message.answer(
            "У вас пока нет доступа.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await request_manager_name(message)
        return
    if message.from_user.id not in USER_LANGS:
        await message.answer(LANG_TEXTS["ru"]["choose_language"], reply_markup=language_keyboard())
        return
    await message.answer(
        tr(message.from_user.id, "start"),
        reply_markup=main_menu(message.from_user.id),
    )


@dp.callback_query(F.data.startswith("lang:"))
async def language_callback(callback: CallbackQuery):
    lang = callback.data.split(":", 1)[1]
    if lang not in LANG_TEXTS:
        await callback.answer("Unknown language", show_alert=True)
        return
    USER_LANGS[callback.from_user.id] = lang
    save_user_langs()
    USER_STATES[callback.from_user.id] = {"section": "home", "view": "home", "filters": {}}
    await callback.message.answer(
        f"{tr(callback.from_user.id, 'language_saved')}\n{tr(callback.from_user.id, 'start')}",
        reply_markup=main_menu(callback.from_user.id),
    )
    await callback.answer()


@dp.message(F.text.in_(LANGUAGE_TEXTS))
async def language_message(message: Message):
    await message.answer(tr(message.from_user.id, "choose_language"), reply_markup=language_keyboard())


@dp.message(F.text.in_(BUY_TEXTS))
async def catalog_message(message: Message):
    cancel_search(message.from_user.id)
    old_state = USER_STATES.get(message.from_user.id, {})
    await delete_navigation_messages(message, old_state)
    USER_STATES[message.from_user.id] = {"section": "catalog", "view": "catalog", "filters": {}}
    await message.answer(tr(message.from_user.id, "catalog"), reply_markup=catalog_keyboard(message.from_user.id))


@dp.message(F.text.in_(SELL_TEXTS))
async def sell_message(message: Message):
    cancel_search(message.from_user.id)
    old_state = USER_STATES.get(message.from_user.id, {})
    await delete_navigation_messages(message, old_state)
    USER_STATES[message.from_user.id] = {"section": "sell", "view": "sell", "filters": {}}
    await send_sell_prices_image(message)


@dp.message(F.text.in_(CONTACT_TEXTS))
async def contacts_message(message: Message):
    cancel_search(message.from_user.id)
    old_state = USER_STATES.get(message.from_user.id, {})
    await delete_navigation_messages(message, old_state)
    USER_STATES[message.from_user.id] = {"section": "home", "view": "contacts", "filters": {}}
    await message.answer(contacts_text(), parse_mode=ParseMode.HTML, reply_markup=main_menu(message.from_user.id))


@dp.message(F.text.in_(CART_TEXTS))
async def cart_message(message: Message):
    items = get_cart_items(message.from_user.id)
    await message.answer(cart_text(items, message.from_user.id), parse_mode=ParseMode.HTML, reply_markup=cart_keyboard(items, message.from_user.id) or main_menu(message.from_user.id))


@dp.message(F.text.in_(ORDER_TEXTS))
async def my_orders_message(message: Message):
    markup, count = client_orders_keyboard(message.from_user.id, 0)
    await message.answer(tr(message.from_user.id, "your_orders") if count else tr(message.from_user.id, "no_orders"), reply_markup=markup if count else main_menu(message.from_user.id))


@dp.message(F.text == MANAGER_ORDERS_TEXT)
async def manager_orders_message(message: Message, bot: Bot):
    if not (MANAGER_BOT_TOKEN and getattr(bot, "token", "") == MANAGER_BOT_TOKEN):
        return
    if not manager_has_access(message.from_user.id):
        MANAGER_NAME_DRAFTS.pop(message.from_user.id, None)
        MANAGER_CONTACT_DRAFTS.pop(message.from_user.id, None)
        await message.answer(
            "У вас нет доступа. Для повторной регистрации отправьте /start.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    markup, count = manager_orders_keyboard(0)
    await message.answer("Заказы:" if count else "Заказов пока нет.", reply_markup=markup)


@dp.message(F.text == "🔐 Доступы")
async def manager_access_message(message: Message, bot: Bot):
    if not (MANAGER_BOT_TOKEN and getattr(bot, "token", "") == MANAGER_BOT_TOKEN):
        return
    if not manager_is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer("<b>Админ-панель доступов</b>", parse_mode=ParseMode.HTML, reply_markup=manager_access_home_keyboard())


@dp.message(
    F.text,
    lambda message: message.from_user and message.from_user.id in MANAGER_NAME_DRAFTS,
)
async def manager_name_message(message: Message, bot: Bot):
    if not (MANAGER_BOT_TOKEN and getattr(bot, "token", "") == MANAGER_BOT_TOKEN):
        return
    name = " ".join((message.text or "").split())
    if len(name) < 2:
        await message.answer("Введите имя чуть понятнее.")
        return
    MANAGER_NAME_DRAFTS.pop(message.from_user.id, None)
    data = seed_env_managers(manager_access_data())
    chat_id = str(message.from_user.id)
    data["pending"][chat_id] = {
        "username": message.from_user.username or "",
        "first_name": message.from_user.first_name or "",
        "last_name": message.from_user.last_name or "",
        "display_name": name,
        "phone": "",
        "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_manager_access_data(data)
    append_manager_log("access_name_entered", actor_id=message.from_user.id, target_id=message.from_user.id, details=name)
    await request_manager_contact(message)


@dp.message(
    F.text,
    lambda message: message.from_user and message.from_user.id in MANAGER_REMARK_DRAFTS,
)
async def manager_remark_message(message: Message, bot: Bot):
    if not (MANAGER_BOT_TOKEN and getattr(bot, "token", "") == MANAGER_BOT_TOKEN):
        return
    if not manager_is_admin(message.from_user.id):
        MANAGER_REMARK_DRAFTS.pop(message.from_user.id, None)
        await message.answer("Нет доступа.")
        return
    draft = MANAGER_REMARK_DRAFTS.pop(message.from_user.id, None)
    text = " ".join((message.text or "").split())
    if not draft or not text:
        await message.answer("Замечание пустое.")
        return
    target_id = draft["target_id"]
    append_manager_remark(message.from_user.id, target_id, text)
    try:
        await manager_bot.send_message(target_id, f"Замечание от администратора:\n{text}")
    except Exception:
        pass
    await message.answer("Замечание сохранено.", reply_markup=manager_main_keyboard(message.from_user.id))


@dp.message(
    F.text,
    lambda message: message.from_user and REVIEW_DRAFTS.get(message.from_user.id)
    and message.text not in HOME_TEXTS
    and message.text not in BACK_TEXTS,
)
async def review_text_message(message: Message):
    draft = REVIEW_DRAFTS.get(message.from_user.id)
    if not draft:
        return
    text = " ".join((message.text or "").split())
    if not text:
        await message.answer(tr(message.from_user.id, "review_prompt"), reply_markup=main_menu(message.from_user.id))
        return
    order = get_client_tg_order(draft["order_code"], message.from_user.id)
    if not order:
        REVIEW_DRAFTS.pop(message.from_user.id, None)
        await message.answer(tr(message.from_user.id, "order_not_found"), reply_markup=main_menu(message.from_user.id))
        return
    if (order.get("status") or "") not in {"completed", "done", "completed_success"}:
        REVIEW_DRAFTS.pop(message.from_user.id, None)
        await message.answer(tr(message.from_user.id, "review_unavailable"), reply_markup=main_menu(message.from_user.id))
        return
    if order.get("client_review"):
        REVIEW_DRAFTS.pop(message.from_user.id, None)
        await message.answer(tr(message.from_user.id, "review_exists"), reply_markup=main_menu(message.from_user.id))
        return
    saved = save_order_review(draft["order_code"], order.get("product_id") or 0, message.from_user.id, text)
    REVIEW_DRAFTS.pop(message.from_user.id, None)
    if saved:
        await message.answer(tr(message.from_user.id, "review_saved"), reply_markup=main_menu(message.from_user.id))
    else:
        await message.answer("Пока не удалось сохранить отзыв. Заказ работает, попробуйте позже.", reply_markup=main_menu(message.from_user.id))


@dp.message(F.text, lambda message: message.from_user and message.from_user.id in MANAGER_CANCEL_DRAFTS)
async def manager_cancel_reason_message(message: Message, bot: Bot):
    if not (MANAGER_BOT_TOKEN and getattr(bot, "token", "") == MANAGER_BOT_TOKEN):
        return
    if not manager_can_manage(message.from_user.id):
        MANAGER_CANCEL_DRAFTS.pop(message.from_user.id, None)
        await message.answer("Нет доступа к изменению статуса.")
        return
    draft = MANAGER_CANCEL_DRAFTS.get(message.from_user.id)
    if not draft:
        return
    reason = " ".join((message.text or "").split())
    if not reason:
        await message.answer(
            "Напишите причину отмены текстом.",
            reply_markup=build_reply_keyboard([[KeyboardButton(text=MANAGER_ORDERS_TEXT)]]),
        )
        return
    order_code = draft["order_code"]
    current_order = get_tg_order(order_code)
    if not current_order:
        MANAGER_CANCEL_DRAFTS.pop(message.from_user.id, None)
        await message.answer(
            "Заказ не найден.",
            reply_markup=build_reply_keyboard([[KeyboardButton(text=MANAGER_ORDERS_TEXT)]]),
        )
        return
    if (current_order.get("status") or "") in FINAL_ORDER_STATUSES:
        MANAGER_CANCEL_DRAFTS.pop(message.from_user.id, None)
        await message.answer(
            "Заказ уже закрыт. Статус изменить нельзя.",
            reply_markup=build_reply_keyboard([[KeyboardButton(text=MANAGER_ORDERS_TEXT)]]),
        )
        return
    update_tg_order_status(order_code, "cancelled", message.from_user)
    append_manager_log("order_status_changed", actor_id=message.from_user.id, target_id=order_code, details=f"Отмена. Причина: {reason}")
    order = get_tg_order(order_code)
    await notify_client_status_change(order, "cancelled", reason=reason)
    MANAGER_CANCEL_DRAFTS.pop(message.from_user.id, None)
    await message.answer(
        manager_order_text(order),
        parse_mode=ParseMode.HTML,
        reply_markup=manager_order_keyboard(order_code, order.get("status"), message.from_user.id),
    )


@dp.message(
    F.text,
    lambda message: ORDER_DRAFTS.get(message.from_user.id, {}).get("step") == "name"
    and message.text not in HOME_TEXTS
    and message.text not in BACK_TEXTS,
)
async def order_name_message(message: Message):
    draft = ORDER_DRAFTS.get(message.from_user.id)
    if not draft or draft.get("step") != "name":
        return
    name = " ".join((message.text or "").split())
    if not name:
        await message.answer(tr(message.from_user.id, "enter_name"), reply_markup=back_only_keyboard(message.from_user.id))
        return
    name_parts = name.split(maxsplit=1)
    draft["customer_name"] = name
    draft["first_name"] = name_parts[0]
    draft["last_name"] = name_parts[1] if len(name_parts) > 1 else ""
    draft["step"] = "contact"
    await message.answer(
        tr(message.from_user.id, "checkout_contact"),
        reply_markup=contact_request_keyboard(message.from_user.id),
    )


@dp.message(F.contact)
async def order_contact_message(message: Message, bot: Bot):
    if MANAGER_BOT_TOKEN and getattr(bot, "token", "") == MANAGER_BOT_TOKEN:
        if manager_has_access(message.from_user.id):
            await message.answer("Менеджерский бот Diamant.", reply_markup=manager_main_keyboard(message.from_user.id))
            return
        if message.from_user.id in MANAGER_CONTACT_DRAFTS:
            contact = message.contact
            if contact.user_id != message.from_user.id:
                await message.answer("Отправьте свой контакт.")
                return
            data = seed_env_managers(manager_access_data())
            chat_id = str(message.from_user.id)
            record = data.get("pending", {}).setdefault(
                chat_id,
                {
                    "username": message.from_user.username or "",
                    "first_name": message.from_user.first_name or "",
                    "last_name": message.from_user.last_name or "",
                    "display_name": manager_user_label(message.from_user),
                    "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
            record["phone"] = contact.phone_number or ""
            save_manager_access_data(data)
            MANAGER_CONTACT_DRAFTS.pop(message.from_user.id, None)
            append_manager_log("access_request", actor_id=message.from_user.id, target_id=message.from_user.id, details=f"{record.get('display_name')}; phone: {record.get('phone')}")
            await notify_manager_access_request(message.from_user)
            await message.answer("Заявка отправлена администратору.")
            return
        await message.answer(
            "У вас нет доступа. Для регистрации отправьте /start.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    draft = ORDER_DRAFTS.get(message.from_user.id)
    if not draft or draft.get("step") != "contact":
        return
    contact = message.contact
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(tr(message.from_user.id, "send_own_contact"), reply_markup=contact_request_keyboard(message.from_user.id))
        return
    draft["phone"] = contact.phone_number
    draft["step"] = "region"
    await message.answer(tr(message.from_user.id, "select_region"), reply_markup=region_keyboard(message.from_user.id))


@dp.message(F.text.in_(set(REGIONS)))
async def order_region_message(message: Message):
    draft = ORDER_DRAFTS.get(message.from_user.id)
    if not draft or draft.get("step") != "region":
        return
    draft["region"] = message.text
    draft["step"] = "location"
    await message.answer(tr(message.from_user.id, "send_location"), reply_markup=back_only_keyboard(message.from_user.id))


@dp.message(F.location)
async def order_location_message(message: Message):
    draft = ORDER_DRAFTS.get(message.from_user.id)
    if not draft or draft.get("step") != "location":
        return
    draft["delivery_lat"] = message.location.latitude
    draft["delivery_lng"] = message.location.longitude
    order_code, error = create_tg_order(draft)
    if error:
        await message.answer(
            localized_order_error(message.from_user.id, error) + "\n" + tr(message.from_user.id, "check_cart"),
            reply_markup=main_menu(message.from_user.id),
        )
        return
    manager_notified = await notify_managers(order_code)
    ORDER_DRAFTS.pop(message.from_user.id, None)
    await message.answer(
        tr(message.from_user.id, "order_accepted").format(order=display_order_code(order_code)) + "\n"
        + tr(message.from_user.id, "manager_will_contact") + "\n"
        + tr(message.from_user.id, "order_status_hint").format(orders=tr(message.from_user.id, "orders"))
        + ("" if manager_notified else "\n\n" + tr(message.from_user.id, "manager_not_notified")),
        reply_markup=main_menu(message.from_user.id),
    )


@dp.message(
    F.text,
    lambda message: ORDER_DRAFTS.get(message.from_user.id, {}).get("step") == "location"
    and message.text not in HOME_TEXTS
    and message.text not in BACK_TEXTS,
)
async def order_location_prompt_message(message: Message):
    await message.answer(tr(message.from_user.id, "send_location_again"), reply_markup=back_only_keyboard(message.from_user.id))


@dp.message(F.text.in_(HOME_TEXTS))
async def home_message(message: Message):
    cancel_search(message.from_user.id)
    ORDER_DRAFTS.pop(message.from_user.id, None)
    REVIEW_DRAFTS.pop(message.from_user.id, None)
    old_state = USER_STATES.get(message.from_user.id, {})
    await delete_navigation_messages(message, old_state)
    USER_STATES[message.from_user.id] = {"section": "home", "view": "home", "filters": {}}
    await message.answer(tr(message.from_user.id, "main_menu"), reply_markup=main_menu(message.from_user.id))


@dp.message(F.text.in_(BACK_TEXTS))
async def back_message(message: Message):
    cancel_search(message.from_user.id)
    ORDER_DRAFTS.pop(message.from_user.id, None)
    REVIEW_DRAFTS.pop(message.from_user.id, None)
    state = USER_STATES.get(message.from_user.id, {})
    view = state.get("view")
    if view in {"product_details", "filter_values", "search_results", "category_filters"}:
        await safe_delete_message(message)
    if view == "product_details":
        state["view"] = "category_filters" if state.get("category_key") else "catalog"
        if state.get("category_key"):
            await send_filter_status(message, category_filter_keyboard(message.from_user.id))
        else:
            await message.answer(tr(message.from_user.id, "catalog"), reply_markup=catalog_keyboard(message.from_user.id))
    elif view == "filter_values":
        state["view"] = "category_filters"
        await send_filter_status(message, category_filter_keyboard(message.from_user.id))
    elif view == "search_results":
        if state.get("category_key") == "sale":
            await show_sale_menu(message)
            return
        state["view"] = "category_filters"
        await send_filter_status(message, category_filter_keyboard(message.from_user.id))
    elif view == "category_filters":
        previous = state.get("previous_view", "catalog")
        if previous == "sale":
            state["view"] = "sale"
            state["section"] = "sale"
            await message.answer(tr(message.from_user.id, "sale"), reply_markup=sale_keyboard(message.from_user.id))
        else:
            USER_STATES[message.from_user.id] = {"section": "catalog", "view": "catalog", "filters": {}}
            await message.answer(tr(message.from_user.id, "catalog"), reply_markup=catalog_keyboard(message.from_user.id))
    elif view == "sale":
        USER_STATES[message.from_user.id] = {"section": "catalog", "view": "catalog", "filters": {}}
        await message.answer(tr(message.from_user.id, "catalog"), reply_markup=catalog_keyboard(message.from_user.id))
    elif view in {"catalog", "sell"}:
        USER_STATES[message.from_user.id] = {"section": "home", "view": "home", "filters": {}}
        await message.answer(tr(message.from_user.id, "main_menu"), reply_markup=main_menu(message.from_user.id))
    else:
        USER_STATES[message.from_user.id] = {"section": "home", "view": "home", "filters": {}}
        await message.answer(tr(message.from_user.id, "main_menu"), reply_markup=main_menu(message.from_user.id))


@dp.message(F.text.in_({"Ювелирные украшения", "Часы на продажу", "Антиквариат"}))
async def sell_info_message(message: Message):
    await send_sell_prices_image(message)


@dp.message(F.text.regexp(r"сум/гр$"))
async def sell_price_placeholder(message: Message):
    await safe_delete_message(message)


@dp.message(F.text.in_(SALE_TEXTS))
async def sale_message(message: Message):
    old_state = USER_STATES.get(message.from_user.id, {})
    await delete_navigation_messages(message, old_state)
    USER_STATES[message.from_user.id] = {"section": "sale", "view": "sale", "filters": {}}
    await message.answer(tr(message.from_user.id, "sale"), reply_markup=sale_keyboard(message.from_user.id))


@dp.message(F.text.in_(SALE_SEARCH_TEXTS))
async def sale_search_message(message: Message):
    old_state = USER_STATES.get(message.from_user.id, {})
    await delete_navigation_messages(message, old_state)
    select_category_state(message.from_user.id, "sale", True)
    await send_search_results(message, message.from_user.id, "sale", 0)


@dp.message(F.text.in_(set(CATEGORY_TEXT_TO_KEY.keys())))
async def category_message(message: Message):
    category_key = CATEGORY_TEXT_TO_KEY[message.text]
    sale_mode = USER_STATES.get(message.from_user.id, {}).get("section") == "sale"
    old_state = USER_STATES.get(message.from_user.id, {})
    await delete_navigation_messages(message, old_state)
    await safe_delete_message(message)
    select_category_state(message.from_user.id, category_key, sale_mode)
    await send_filter_status(message, category_filter_keyboard(message.from_user.id))


@dp.message(F.text.in_(set(FILTER_TITLE_TO_KEY.keys())))
async def filter_open_message(message: Message):
    state = USER_STATES.get(message.from_user.id, {})
    category_key = state.get("category_key")
    allowed_titles = {filter_title(message.from_user.id, key) for key in CATEGORY_CONFIG.get(category_key, {}).get("filters", [])}
    allowed_titles.update(FILTER_CONFIG[key]["title"] for key in CATEGORY_CONFIG.get(category_key, {}).get("filters", []))
    if not category_key or message.text not in allowed_titles:
        return
    filter_key = FILTER_TITLE_TO_KEY[message.text]
    state["view"] = "filter_values"
    state["current_filter"] = filter_key
    await safe_delete_message(message)
    await send_filter_status(message, filter_values_keyboard(message.from_user.id, filter_key))


@dp.message(F.text.in_({"🔎 Искать", "Искать", "🔎 Qidirish", "Qidirish"}))
async def search_message(message: Message):
    state = USER_STATES.get(message.from_user.id, {})
    category_key = state.get("category_key")
    if not category_key:
        await message.answer(tr(message.from_user.id, "choose_category_first"), reply_markup=catalog_keyboard(message.from_user.id))
        return
    await safe_delete_message(message)
    await send_search_results(message, message.from_user.id, category_key, 0)


@dp.message(F.text.in_({"<", ">"}))
async def search_page_message(message: Message):
    state = USER_STATES.get(message.from_user.id, {})
    if state.get("view") != "search_results":
        return

    category_key = state.get("category_key")
    if not category_key:
        return

    await safe_delete_message(message)
    total = state.get("search_total") or get_filtered_count(message.from_user.id, category_key)
    offset = int(state.get("search_offset", 0))
    if message.text == "<":
        offset = max(offset - PAGE_SIZE, 0)
    else:
        max_offset = max(((total - 1) // PAGE_SIZE) * PAGE_SIZE, 0)
        offset = min(offset + PAGE_SIZE, max_offset)
    await send_search_results(message, message.from_user.id, category_key, offset)


@dp.message(F.text.regexp(r"^\d+/\d+$"))
async def search_page_indicator_message(message: Message):
    state = USER_STATES.get(message.from_user.id, {})
    if state.get("view") != "search_results":
        return
    await safe_delete_message(message)
    category_key = state.get("category_key")
    total = int(state.get("search_total") or 0)
    offset = int(state.get("search_offset") or 0)
    if not category_key or total <= 0:
        return
    current_page = offset // PAGE_SIZE + 1
    block_start = ((current_page - 1) // 40) * 40 + 1
    await message.answer(
        tr(message.from_user.id, "page_picker"),
        reply_markup=page_picker_keyboard(message.from_user.id, category_key, total, current_page, block_start),
    )


@dp.message(F.text.in_({"Фильтры", "Filtrlar"}))
async def search_filters_message(message: Message):
    state = USER_STATES.get(message.from_user.id, {})
    category_key = state.get("category_key")
    if not category_key:
        await message.answer(tr(message.from_user.id, "catalog"), reply_markup=catalog_keyboard(message.from_user.id))
        return
    state["view"] = "category_filters"
    await safe_delete_message(message)
    await send_filter_status(message, category_filter_keyboard(message.from_user.id))


@dp.message(F.entities)
async def debug_custom_emoji_message(message: Message):
    pieces = []
    for entity in message.entities or []:
        if entity.type == "custom_emoji" and entity.custom_emoji_id:
            fallback = entity.extract_from(message.text or "") or "▫️"
            pieces.append((entity.custom_emoji_id, fallback))
    if pieces:
        ids = [emoji_id for emoji_id, _ in pieces]
        html_chain = "".join(
            f'<tg-emoji emoji-id="{html.escape(emoji_id)}">{html.escape(fallback)}</tg-emoji>'
            for emoji_id, fallback in pieces
        )
        await message.answer(
            "custom_emoji_id по порядку:\n"
            + "\n".join(ids)
            + "\n\nГотовая цепочка для кода:\n"
            + f"<code>{html.escape(html_chain)}</code>",
            parse_mode=ParseMode.HTML,
        )


@dp.message()
async def filter_value_message(message: Message):
    state = USER_STATES.get(message.from_user.id, {})
    if state.get("view") != "filter_values":
        return
    filter_key = state.get("current_filter")
    if not filter_key:
        return
    text = message.text.replace("✅ ", "").strip()
    values = get_filter_values(filter_key)
    matched = None
    for value_id, label in values:
        if label == text or translate_filter_value(message.from_user.id, label) == text:
            matched = str(value_id)
            break
    if matched is None:
        return
    selected = state.setdefault("filters", {}).setdefault(filter_key, set())
    if matched in selected:
        selected.remove(matched)
    else:
        selected.add(matched)
    await safe_delete_message(message)
    await send_filter_status(message, filter_values_keyboard(message.from_user.id, filter_key))


@dp.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


async def refresh_manager_access_request_messages(chat_id):
    if not manager_bot:
        return
    messages = MANAGER_ACCESS_REQUEST_MESSAGES.get(str(chat_id), {})
    for admin_id, message_id in list(messages.items()):
        try:
            await manager_bot.edit_message_reply_markup(
                chat_id=int(admin_id),
                message_id=int(message_id),
                reply_markup=manager_access_keyboard(chat_id, admin_id),
            )
        except Exception:
            pass


async def finalize_manager_access_request_messages(chat_id, label):
    if not manager_bot:
        return
    messages = MANAGER_ACCESS_REQUEST_MESSAGES.pop(str(chat_id), {})
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label[:64], callback_data="noop")]]
    )
    for admin_id, message_id in messages.items():
        try:
            await manager_bot.edit_message_reply_markup(
                chat_id=int(admin_id),
                message_id=int(message_id),
                reply_markup=markup,
            )
        except Exception:
            pass


@dp.callback_query(F.data.startswith("accessclaim:"))
async def manager_access_claim_request(callback: CallbackQuery):
    if not manager_is_admin(callback.from_user.id):
        await callback.answer("Только админ может обслуживать заявку.", show_alert=True)
        return
    chat_id = callback.data.split(":", 1)[1]
    pending = manager_access_claim(chat_id, callback.from_user)
    if not pending:
        await callback.answer("Заявка уже обработана.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return
    serviced_by = str(pending.get("serviced_by") or "")
    if serviced_by != str(callback.from_user.id):
        serviced_name = pending.get("serviced_name") or manager_access_display_name(serviced_by)
        await callback.answer(f"Заявку уже обслуживает {serviced_name}.", show_alert=True)
    else:
        await callback.answer("Заявка закреплена за вами.")
    await refresh_manager_access_request_messages(chat_id)


@dp.callback_query(F.data.startswith("access:"))
async def manager_access_decision(callback: CallbackQuery):
    if not manager_is_admin(callback.from_user.id):
        await callback.answer("Только админ может выдавать доступ.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некорректная команда", show_alert=True)
        return
    _, chat_id, role = parts
    data = seed_env_managers(manager_access_data())
    pending = data.get("pending", {}).get(str(chat_id))
    if not pending:
        await callback.answer("Заявка уже обработана.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return
    if str(pending.get("serviced_by") or "") != str(callback.from_user.id):
        serviced_name = pending.get("serviced_name") or manager_access_display_name(pending.get("serviced_by"), data)
        await callback.answer(f"Заявку обслуживает {serviced_name}.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=manager_access_keyboard(chat_id, callback.from_user.id))
        return
    if role == "deny":
        data = manager_access_data()
        data.get("pending", {}).pop(str(chat_id), None)
        save_manager_access_data(data)
        append_manager_log("access_denied", actor_id=callback.from_user.id, target_id=chat_id)
        await finalize_manager_access_request_messages(chat_id, "Заявка отклонена")
        await callback.answer("Заявка отклонена")
        try:
            await manager_bot.send_message(
                chat_id,
                "Доступ к менеджерскому боту не выдан. Для повторной регистрации отправьте /start.",
                reply_markup=ReplyKeyboardRemove(),
            )
        except Exception:
            pass
        return
    if role not in {"viewer", "manager"}:
        await callback.answer("Неизвестная роль", show_alert=True)
        return
    set_manager_role(chat_id, role)
    append_manager_log("access_granted", actor_id=callback.from_user.id, target_id=chat_id, details=role)
    label = "только просмотр" if role == "viewer" else "менеджер"
    await finalize_manager_access_request_messages(chat_id, f"Доступ выдан: {label}")
    await callback.answer(f"Доступ выдан: {label}")
    try:
        await manager_bot.send_message(chat_id, f"Доступ выдан: {label}.", reply_markup=manager_main_keyboard(chat_id))
    except Exception:
        pass


@dp.callback_query(F.data == "accesslist")
async def manager_access_list(callback: CallbackQuery):
    if not manager_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text(
        manager_access_list_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=manager_access_list_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("accessedit:"))
async def manager_access_edit(callback: CallbackQuery):
    if not manager_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    chat_id = callback.data.split(":")[1]
    data = seed_env_managers(manager_access_data())
    record = data.get("users", {}).get(chat_id) or data.get("pending", {}).get(chat_id)
    if not record:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return
    username = f"@{record.get('username')}" if record.get("username") else "без username"
    name = record.get("display_name") or " ".join(part for part in [record.get("first_name"), record.get("last_name")] if part)
    role = data.get("users", {}).get(chat_id, {}).get("role") or "нет доступа"
    pending_record = data.get("pending", {}).get(chat_id)
    service_text = ""
    if pending_record and pending_record.get("serviced_by"):
        service_text = f"\nОбслуживает: <b>{html.escape(pending_record.get('serviced_name') or manager_access_display_name(pending_record.get('serviced_by'), data))}</b>"
    text = (
        "<b>Доступ пользователя</b>\n"
        f"{html.escape(name or chat_id)} ({html.escape(username)})\n"
        f"Телефон: <code>{html.escape(record.get('phone') or '')}</code>\n"
        f"Роль: <b>{html.escape(role)}</b>"
        f"{service_text}"
    )
    markup = manager_access_keyboard(chat_id, callback.from_user.id) if pending_record else manager_access_edit_keyboard(chat_id)
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data.startswith("accessset:"))
async def manager_access_set(callback: CallbackQuery):
    if not manager_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, chat_id, role = callback.data.split(":")
    if str(chat_id) in ADMIN_MANAGER_IDS and role != "admin":
        await callback.answer("Эти админы закреплены по ID.", show_alert=True)
        return
    data = seed_env_managers(manager_access_data())
    if role == "deny":
        data.get("users", {}).pop(str(chat_id), None)
        data.get("pending", {}).pop(str(chat_id), None)
        save_manager_access_data(data)
        append_manager_log("access_removed", actor_id=callback.from_user.id, target_id=chat_id)
        try:
            await manager_bot.send_message(
                chat_id,
                "Доступ к менеджерскому боту убран. Для повторной регистрации отправьте /start.",
                reply_markup=ReplyKeyboardRemove(),
            )
        except Exception:
            pass
        await callback.answer("Доступ убран")
    elif role in {"viewer", "manager"}:
        set_manager_role(chat_id, role)
        label = "только просмотр" if role == "viewer" else "менеджер"
        append_manager_log("access_changed", actor_id=callback.from_user.id, target_id=chat_id, details=role)
        try:
            await manager_bot.send_message(chat_id, f"Доступ обновлён: {label}.", reply_markup=manager_main_keyboard(chat_id))
        except Exception:
            pass
        await callback.answer(f"Роль: {label}")
    else:
        await callback.answer("Неизвестная роль", show_alert=True)
        return
    await callback.message.edit_text(
        manager_access_list_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=manager_access_list_keyboard(),
    )


@dp.callback_query(F.data == "accesslogs")
async def manager_access_logs(callback: CallbackQuery):
    if not manager_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text(
        manager_logs_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=manager_access_home_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("remark:"))
async def manager_remark_start(callback: CallbackQuery):
    if not manager_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    chat_id = callback.data.split(":")[1]
    if str(chat_id) in ADMIN_MANAGER_IDS:
        await callback.answer("Админам замечания не пишем.", show_alert=True)
        return
    MANAGER_REMARK_DRAFTS[callback.from_user.id] = {"target_id": chat_id}
    await callback.message.answer("Напишите замечание одним сообщением. Оно сохранится и уйдёт сотруднику.")
    await callback.answer()


@dp.callback_query(F.data == "do_search")
async def do_search(callback: CallbackQuery):
    state = USER_STATES.get(callback.from_user.id, {})
    category_key = state.get("category_key")
    if not category_key:
        await callback.answer(tr(callback.from_user.id, "choose_category_first"))
        return
    await callback.message.delete()
    state.pop("filter_status_message_id", None)
    await send_search_results(callback.message, callback.from_user.id, category_key, 0)
    await callback.answer()


@dp.callback_query(F.data == "reset_filters")
async def reset_filters(callback: CallbackQuery):
    state = USER_STATES.get(callback.from_user.id)
    if not state or not state.get("category_key"):
        await callback.answer(tr(callback.from_user.id, "reset_filters"))
        return
    state["filters"] = {}
    state["view"] = "category_filters"
    state.pop("current_filter", None)
    await show_text(
        callback,
        filter_status_text(callback.from_user.id),
        parse_mode=ParseMode.HTML,
        reply_markup=category_filter_keyboard(callback.from_user.id),
    )
    await callback.answer(tr(callback.from_user.id, "reset_filters"))


@dp.callback_query(F.data == "home")
async def home(callback: CallbackQuery):
    cancel_search(callback.from_user.id)
    await show_text(callback, tr(callback.from_user.id, "main_menu"), reply_markup=main_menu(callback.from_user.id))
    await callback.answer()


@dp.callback_query(F.data == "catalog")
async def catalog(callback: CallbackQuery):
    cancel_search(callback.from_user.id)
    await show_text(callback, tr(callback.from_user.id, "catalog"), reply_markup=catalog_keyboard(callback.from_user.id))
    await callback.answer()


@dp.callback_query(F.data == "sale")
async def sale(callback: CallbackQuery):
    cancel_search(callback.from_user.id)
    USER_STATES[callback.from_user.id] = {"section": "sale", "view": "sale", "filters": {}}
    await show_text(callback, tr(callback.from_user.id, "sale"), reply_markup=sale_keyboard(callback.from_user.id))
    await callback.answer()


@dp.callback_query(F.data == "sell")
async def sell(callback: CallbackQuery):
    cancel_search(callback.from_user.id)
    await send_sell_prices_image(callback.message)
    await callback.answer()


@dp.callback_query(F.data.startswith("sellinfo:"))
async def sell_info(callback: CallbackQuery):
    await send_sell_prices_image(callback.message)
    await callback.answer()


@dp.callback_query(F.data.startswith("csel:"))
async def category_select(callback: CallbackQuery):
    cancel_search(callback.from_user.id)
    parts = callback.data.split(":")
    category_key = parts[1]
    sale_mode = len(parts) > 2 and parts[2] == "sale"
    select_category_state(callback.from_user.id, category_key, sale_mode)
    await show_text(callback, filter_status_text(callback.from_user.id), parse_mode=ParseMode.HTML, reply_markup=category_filter_keyboard(callback.from_user.id))
    await callback.answer()


@dp.callback_query(F.data.startswith("fopen:"))
async def filter_open(callback: CallbackQuery):
    filter_key = callback.data.split(":")[1]
    state = USER_STATES.setdefault(callback.from_user.id, {"category_key": "ring", "sale": False, "filters": {}})
    state["view"] = "filter_values"
    state["current_filter"] = filter_key
    await show_text(callback, filter_status_text(callback.from_user.id), parse_mode=ParseMode.HTML, reply_markup=filter_values_keyboard(callback.from_user.id, filter_key))
    await callback.answer()


@dp.callback_query(F.data.startswith("fval:"))
async def filter_toggle(callback: CallbackQuery):
    _, filter_key, value_id = callback.data.split(":", 2)
    state = USER_STATES.setdefault(callback.from_user.id, {"category_key": "ring", "sale": False, "filters": {}})
    selected = state.setdefault("filters", {}).setdefault(filter_key, set())
    if value_id in selected:
        selected.remove(value_id)
    else:
        selected.add(value_id)
    if filter_key == "metal":
        cleanup_incompatible_sample_filters(state)
    await show_text(callback, filter_status_text(callback.from_user.id), parse_mode=ParseMode.HTML, reply_markup=filter_values_keyboard(callback.from_user.id, filter_key))
    await callback.answer("Tanlandi" if user_lang(callback.from_user.id) == "uz" and value_id in selected else "Olindi" if user_lang(callback.from_user.id) == "uz" else "Выбрано" if value_id in selected else "Убрано")


@dp.callback_query(F.data == "fback")
async def filter_back(callback: CallbackQuery):
    cancel_search(callback.from_user.id)
    state = USER_STATES.get(callback.from_user.id)
    if not state:
        await show_text(callback, tr(callback.from_user.id, "catalog"), reply_markup=catalog_keyboard(callback.from_user.id))
    elif state.get("category_key") == "sale":
        USER_STATES[callback.from_user.id] = {"section": "sale", "view": "sale", "filters": {}}
        await show_text(callback, tr(callback.from_user.id, "sale"), reply_markup=sale_keyboard(callback.from_user.id))
    else:
        state["view"] = "category_filters"
        await show_text(callback, filter_status_text(callback.from_user.id), parse_mode=ParseMode.HTML, reply_markup=category_filter_keyboard(callback.from_user.id))
    await callback.answer()


@dp.callback_query(F.data.startswith("search:"))
async def search_products(callback: CallbackQuery):
    _, category_key, offset = callback.data.split(":")
    offset = int(offset)
    state = USER_STATES.setdefault(callback.from_user.id, {"category_key": category_key, "sale": False, "filters": {}})
    state["category_key"] = category_key
    await send_search_results(callback.message, callback.from_user.id, category_key, offset)
    await callback.answer()


@dp.callback_query(F.data.startswith("pages:"))
async def search_pages_block(callback: CallbackQuery):
    _, category_key, block_start = callback.data.split(":")
    state = USER_STATES.get(callback.from_user.id, {})
    total = int(state.get("search_total") or get_filtered_count(callback.from_user.id, category_key))
    offset = int(state.get("search_offset") or 0)
    current_page = offset // PAGE_SIZE + 1
    await callback.message.edit_reply_markup(
        reply_markup=page_picker_keyboard(callback.from_user.id, category_key, total, current_page, int(block_start))
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("page:"))
async def search_page_pick(callback: CallbackQuery):
    _, category_key, page = callback.data.split(":")
    page = max(int(page), 1)
    offset = (page - 1) * PAGE_SIZE
    await callback.message.delete()
    await send_search_results(callback.message, callback.from_user.id, category_key, offset)
    await callback.answer((f"Sahifa {page}" if user_lang(callback.from_user.id) == "uz" else f"Страница {page}"))


@dp.callback_query(F.data == "cats")
async def cats(callback: CallbackQuery):
    categories = get_categories()
    await show_text(callback, "Выбери категорию:", reply_markup=category_keyboard(categories))
    await callback.answer()


@dp.callback_query(F.data == "new")
async def new_products(callback: CallbackQuery):
    products = get_new_products()
    await show_text(callback, "Новинки:", reply_markup=products_keyboard(products))
    await callback.answer()


@dp.callback_query(F.data.startswith("newcards:"))
async def new_products_cards(callback: CallbackQuery):
    _, offset = callback.data.split(":")
    offset = int(offset)
    products = get_new_products_page(offset)
    await send_cards_page(callback, products, offset, "new")


@dp.callback_query(F.data.startswith("cat:"))
async def category_products(callback: CallbackQuery):
    _, category_id, offset = callback.data.split(":")
    products = get_products_for_category(int(category_id), int(offset))
    if products:
        text = "Товары в категории:"
        markup = products_keyboard(products, int(category_id), int(offset))
    else:
        text = "В этой категории пока нет активных товаров."
        markup = category_keyboard(get_categories())
    await show_text(callback, text, reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data.startswith("catcards:"))
async def category_products_cards(callback: CallbackQuery):
    _, category_id, offset = callback.data.split(":")
    category_id = int(category_id)
    offset = int(offset)
    products = get_products_for_category(category_id, offset)
    if len(products) == 5:
        products = products + get_products_for_category(category_id, offset + 5)[:1]
    await send_cards_page(callback, products, offset, "cat", category_id)


@dp.callback_query(F.data.startswith("prod:"))
async def product(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    await send_product(callback, product_id)
    await callback.answer()


@dp.callback_query(F.data.startswith("media:"))
async def product_media(callback: CallbackQuery):
    _, product_id, media_index = callback.data.split(":")
    product_id = int(product_id)
    media_index = int(media_index)
    product = get_product(product_id)
    if not product:
        await callback.answer(tr(callback.from_user.id, "product_not_found"))
        return

    media_items = public_media_urls_for_product(product_id)
    if not media_items:
        await callback.answer(tr(callback.from_user.id, "media_not_found"))
        return

    media_index %= len(media_items)
    url, media_type = media_items[media_index]
    media = await build_product_input_media(product, url, media_type, user_id=callback.from_user.id)
    if not media:
        await callback.answer(tr(callback.from_user.id, "media_load_failed"))
        return

    await callback.message.edit_media(
        media=media,
        reply_markup=product_keyboard(
            product_id,
            len(media_items),
            media_index,
            in_cart=user_has_cart_item(callback.from_user.id, product_id),
            user_id=callback.from_user.id,
        ),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("details:"))
async def product_details(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    product = get_product(product_id)
    if not product:
        await callback.answer(tr(callback.from_user.id, "product_not_found"))
        return
    media = public_media_urls_for_product(product_id)
    if not media:
        await callback.message.answer(
            "Медиафайлы для этого товара не найдены.",
            reply_markup=main_menu(callback.from_user.id),
        )
        await callback.answer()
        return
    USER_STATES.setdefault(callback.from_user.id, {})["view"] = "product_details"
    USER_STATES[callback.from_user.id]["previous_view"] = "search_results"

    first_url, first_media_type = media[0]
    first_sent = await send_media_url(
        callback.message,
        first_url,
        first_media_type,
        reply_markup=order_keyboard(product_id),
    )
    media_group = []
    for url, media_type in media[1:10] if first_sent else media[:10]:
        item = await download_media_item(url, media_type)
        if item:
            media_group.append(item)
    if media_group:
        await callback.message.answer_media_group(media_group)
    elif not first_sent:
        await callback.message.answer(
            "Не удалось загрузить медиафайлы.",
            reply_markup=main_menu(callback.from_user.id),
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("lead:"))
async def lead(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    user = callback.from_user
    product = get_product(product_id)
    if not product:
        await callback.answer(tr(callback.from_user.id, "product_not_found"), show_alert=True)
        return
    ORDER_DRAFTS[user.id] = {
        "step": "name",
        "product": product,
        "user": user,
        "first_name": "",
        "last_name": "",
        "customer_name": "",
    }
    await callback.message.answer(
        tr(callback.from_user.id, "enter_name"),
        reply_markup=back_only_keyboard(callback.from_user.id),
    )
    await callback.answer(tr(callback.from_user.id, "checkout_started"))


@dp.callback_query(F.data.startswith("cart_add:"))
async def cart_add(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    if user_has_cart_item(callback.from_user.id, product_id):
        await cart_view(callback)
        return
    ok, message = add_to_cart(callback.from_user.id, product_id)
    if ok:
        try:
            media_items = public_media_urls_for_product(product_id)
            await callback.message.edit_reply_markup(
                reply_markup=product_keyboard(product_id, len(media_items) or 1, 0, in_cart=True, user_id=callback.from_user.id)
            )
        except Exception:
            pass
    await callback.answer(message, show_alert=True)


@dp.callback_query(F.data == "cart_view")
async def cart_view(callback: CallbackQuery):
    items = get_cart_items(callback.from_user.id)
    await callback.message.answer(cart_text(items, callback.from_user.id), parse_mode=ParseMode.HTML, reply_markup=cart_keyboard(items, callback.from_user.id) or main_menu(callback.from_user.id))
    await callback.answer()


@dp.callback_query(F.data.startswith("cart_prod:"))
async def cart_product(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    await send_product(callback, product_id, in_cart=True, back_to_cart=True)
    await callback.answer()


@dp.callback_query(F.data == "cart_checkout")
async def cart_checkout(callback: CallbackQuery):
    items = get_cart_items(callback.from_user.id)
    if not items:
        await callback.answer(tr(callback.from_user.id, "empty_cart"), show_alert=True)
        return
    missing = [
        item
        for item in items
        if int(item.get("quantity") or 0) <= 0 and int(item.get("reserved_quantity") or 0) <= 0
    ]
    if missing:
        await callback.answer(tr(callback.from_user.id, "cart_missing"), show_alert=True)
        return
    user = callback.from_user
    ORDER_DRAFTS[user.id] = {
        "step": "name",
        "user": user,
        "first_name": "",
        "last_name": "",
        "customer_name": "",
    }
    await callback.message.answer(
        tr(callback.from_user.id, "enter_name"),
        reply_markup=back_only_keyboard(callback.from_user.id),
    )
    await callback.answer(tr(callback.from_user.id, "checkout_started"))


@dp.callback_query(F.data.startswith("cart_remove:"))
async def cart_remove(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    stay_on_product = is_product_card_keyboard(callback.message.reply_markup, product_id)
    media_items = public_media_urls_for_product(product_id) if stay_on_product else []
    media_count = len(media_items) or 1
    media_index = keyboard_media_index(callback.message.reply_markup, media_count)
    remove_from_cart(callback.from_user.id, product_id)
    if stay_on_product:
        await callback.message.edit_reply_markup(
            reply_markup=product_keyboard(product_id, media_count, media_index, in_cart=False, user_id=callback.from_user.id)
        )
        await callback.answer(tr(callback.from_user.id, "removed_from_cart"))
        return
    items = get_cart_items(callback.from_user.id)
    text = cart_text(items, callback.from_user.id)
    markup = cart_keyboard(items, callback.from_user.id)
    if callback.message.text:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=markup or main_menu(callback.from_user.id))
    await callback.answer(tr(callback.from_user.id, "removed_from_cart"))


@dp.callback_query(F.data.startswith("myorders:"))
async def my_orders_page(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    markup, count = client_orders_keyboard(callback.from_user.id, page)
    await callback.message.edit_text(tr(callback.from_user.id, "your_orders") if count else tr(callback.from_user.id, "no_orders"), reply_markup=markup if count else None)
    await callback.answer()


@dp.callback_query(F.data.startswith("myorder:"))
async def my_order_view(callback: CallbackQuery):
    order_code = callback.data.split(":")[1]
    order = get_client_tg_order(order_code, callback.from_user.id)
    if not order:
        await callback.answer(tr(callback.from_user.id, "order_not_found"), show_alert=True)
        return
    text = client_order_text(order)
    markup = client_order_keyboard(order_code, order.get("status") or "new", callback.from_user.id)
    if callback.message.caption:
        await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data.startswith("myitems:"))
async def my_order_items(callback: CallbackQuery):
    order_code = callback.data.split(":")[1]
    order = get_client_tg_order(order_code, callback.from_user.id)
    if not order:
        await callback.answer(tr(callback.from_user.id, "order_not_found"), show_alert=True)
        return
    text = tr(callback.from_user.id, "order_items_title").format(order=html.escape(display_order_code(order_code)))
    markup = client_order_items_keyboard(order_code, callback.from_user.id)
    if callback.message.caption:
        await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data.startswith("reviewskip:"))
async def review_skip(callback: CallbackQuery):
    order_code = callback.data.split(":")[1]
    REVIEW_DRAFTS.pop(callback.from_user.id, None)
    await callback.message.answer(tr(callback.from_user.id, "review_later_hint"), reply_markup=main_menu(callback.from_user.id))
    await callback.answer(tr(callback.from_user.id, "skip_review"))


@dp.callback_query(F.data.startswith("reviewstart:") | F.data.startswith("reviewpick:"))
async def review_pick(callback: CallbackQuery):
    order_code = callback.data.split(":")[1]
    order = get_client_tg_order(order_code, callback.from_user.id)
    if not order:
        await callback.answer(tr(callback.from_user.id, "order_not_found"), show_alert=True)
        return
    if (order.get("status") or "") not in {"completed", "done", "completed_success"}:
        await callback.answer(tr(callback.from_user.id, "review_unavailable"), show_alert=True)
        return
    if order.get("client_review"):
        await callback.answer(tr(callback.from_user.id, "review_exists"), show_alert=True)
        return
    REVIEW_DRAFTS[callback.from_user.id] = {"order_code": order_code}
    await callback.message.answer(tr(callback.from_user.id, "review_prompt"), reply_markup=main_menu(callback.from_user.id))
    await callback.answer()


@dp.callback_query(F.data.startswith("review:"))
async def review_start(callback: CallbackQuery):
    parts = callback.data.split(":")
    order_code = parts[1]
    order = get_client_tg_order(order_code, callback.from_user.id)
    if not order:
        await callback.answer(tr(callback.from_user.id, "order_not_found"), show_alert=True)
        return
    if (order.get("status") or "") not in {"completed", "done", "completed_success"}:
        await callback.answer(tr(callback.from_user.id, "review_unavailable"), show_alert=True)
        return
    if order.get("client_review"):
        await callback.answer(tr(callback.from_user.id, "review_exists"), show_alert=True)
        return
    REVIEW_DRAFTS[callback.from_user.id] = {"order_code": order_code}
    await callback.message.answer(tr(callback.from_user.id, "review_prompt"), reply_markup=main_menu(callback.from_user.id))
    await callback.answer()


@dp.callback_query(F.data.startswith("myprod:"))
async def my_order_product(callback: CallbackQuery):
    _, order_code, product_id = callback.data.split(":")
    order = get_client_tg_order(order_code, callback.from_user.id)
    if not order:
        await callback.answer(tr(callback.from_user.id, "order_not_found"), show_alert=True)
        return
    if not order_has_product(order_code, product_id):
        await callback.answer(tr(callback.from_user.id, "product_not_found"), show_alert=True)
        return
    await send_client_order_product_card(callback, order_code, int(product_id))


@dp.callback_query(F.data.startswith("mymedia:"))
async def my_order_product_media(callback: CallbackQuery):
    _, order_code, product_id, media_index = callback.data.split(":")
    order = get_client_tg_order(order_code, callback.from_user.id)
    if not order:
        await callback.answer(tr(callback.from_user.id, "order_not_found"), show_alert=True)
        return
    product_id = int(product_id)
    if not order_has_product(order_code, product_id):
        await callback.answer(tr(callback.from_user.id, "product_not_found"), show_alert=True)
        return
    media_index = int(media_index)
    product = get_product(product_id)
    if not product:
        await callback.answer(tr(callback.from_user.id, "product_not_found"), show_alert=True)
        return
    media_items = public_media_urls_for_product(product_id)
    if not media_items:
        await callback.answer(tr(callback.from_user.id, "media_not_found"))
        return
    media_index %= len(media_items)
    url, media_type = media_items[media_index]
    media = await build_product_input_media(product, url, media_type, user_id=callback.from_user.id)
    if not media:
        await callback.answer(tr(callback.from_user.id, "media_load_failed"))
        return
    await callback.message.edit_media(
        media=media,
        reply_markup=client_order_product_keyboard(order_code, product_id, len(media_items), media_index, callback.from_user.id),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("mycancel:"))
async def my_order_cancel(callback: CallbackQuery):
    order_code = callback.data.split(":")[1]
    ok, message, order = cancel_client_order(order_code, callback.from_user.id)
    if not ok:
        await callback.answer(message, show_alert=True)
        return
    if order:
        await callback.message.edit_text(
            client_order_text(order),
            parse_mode=ParseMode.HTML,
            reply_markup=client_order_keyboard(order_code, order.get("status") or "cancelled", callback.from_user.id),
        )
    await callback.answer(message, show_alert=True)


@dp.callback_query(F.data.startswith("olist:"))
async def manager_orders_page(callback: CallbackQuery):
    if not manager_has_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) == 2:
        status_filter = "all"
        page = int(parts[1])
    else:
        status_filter = parts[1] if parts[1] in MANAGER_ORDER_FILTER_MAP else "all"
        page = int(parts[2])
    markup, count = manager_orders_keyboard(page, status_filter)
    title = "Заказы:" if status_filter == "all" else f"Заказы: {MANAGER_ORDER_FILTER_MAP[status_filter]['label']}"
    await callback.message.edit_text(title if count else "Заказов пока нет.", reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data.startswith("oview_nogeo:"))
async def manager_order_view_no_geo(callback: CallbackQuery):
    order_code = callback.data.split(":")[1]
    await show_manager_order(callback, order_code, send_location=False)


@dp.callback_query(F.data.startswith("oloc:"))
async def manager_order_location(callback: CallbackQuery):
    if not manager_has_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    order_code = callback.data.split(":")[1]
    order = get_tg_order(order_code)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    sent = await send_order_location(manager_bot, callback.message.chat.id, order)
    await callback.answer("Локация отправлена" if sent else "Локация не указана", show_alert=not sent)


@dp.callback_query(F.data.startswith("oview:"))
async def manager_order_view(callback: CallbackQuery):
    if not manager_has_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    order_code = callback.data.split(":")[1]
    order = get_tg_order(order_code)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    text = manager_order_text(order)
    markup = manager_order_keyboard(order_code, order.get("status"), callback.from_user.id)
    if callback.message.text or callback.message.caption:
        if callback.message.caption:
            await callback.message.edit_caption(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        else:
            await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data.startswith("mstatus:"))
async def manager_order_status_menu(callback: CallbackQuery):
    if not manager_can_manage(callback.from_user.id):
        await callback.answer("Нет доступа к изменению статуса.", show_alert=True)
        return
    order_code = callback.data.split(":")[1]
    order = get_tg_order(order_code)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    if (order.get("status") or "") in FINAL_ORDER_STATUSES:
        await callback.answer("Заказ уже закрыт. Статус изменить нельзя.", show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=manager_status_keyboard(order_code))
    await callback.answer()


@dp.callback_query(F.data.startswith("mitems:"))
async def manager_order_items(callback: CallbackQuery):
    if not manager_has_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    order_code = callback.data.split(":")[1]
    order = get_tg_order(order_code)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    text = f"Товары заказа {html.escape(display_order_code(order_code))}:"
    markup = manager_order_items_keyboard(order_code)
    if callback.message.caption:
        await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data.startswith("mprod:"))
async def manager_product(callback: CallbackQuery):
    if not manager_has_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, order_code, product_id = callback.data.split(":")
    if not order_has_product(order_code, product_id):
        await callback.answer("Товар не найден в заказе", show_alert=True)
        return
    await send_manager_product_card(callback, order_code, int(product_id))


@dp.callback_query(F.data.startswith("mmedia:"))
async def manager_product_media(callback: CallbackQuery):
    if not manager_has_access(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, order_code, product_id, media_index = callback.data.split(":")
    product_id = int(product_id)
    media_index = int(media_index)
    if not order_has_product(order_code, product_id):
        await callback.answer("Товар не найден в заказе", show_alert=True)
        return
    product = get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    media_items = public_media_urls_for_product(product_id)
    if not media_items:
        await callback.answer("Медиа нет")
        return

    media_index %= len(media_items)
    url, media_type = media_items[media_index]
    media = await build_manager_product_input_media(product, url, media_type)
    if not media:
        await callback.answer("Не удалось загрузить медиа")
        return

    await callback.message.edit_media(
        media=media,
        reply_markup=manager_product_keyboard(order_code, product_id, len(media_items), media_index),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("ostatus:"))
async def manager_order_status(callback: CallbackQuery):
    if not manager_can_manage(callback.from_user.id):
        await callback.answer("Нет доступа к изменению статуса.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некорректная команда", show_alert=True)
        return
    _, order_code, status = parts
    if status not in TG_ORDER_STATUSES:
        await callback.answer("Неизвестный статус", show_alert=True)
        return
    current_order = get_tg_order(order_code)
    if not current_order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    if (current_order.get("status") or "") in FINAL_ORDER_STATUSES:
        await callback.answer("Заказ уже закрыт. Статус изменить нельзя.", show_alert=True)
        return
    if status in {"completed", "cancelled"}:
        if callback.message.caption:
            await callback.message.edit_reply_markup(reply_markup=manager_status_confirm_keyboard(order_code, status))
        else:
            await callback.message.edit_reply_markup(reply_markup=manager_status_confirm_keyboard(order_code, status))
        await callback.answer("Подтвердите действие")
        return
    update_tg_order_status(order_code, status, callback.from_user)
    append_manager_log("order_status_changed", actor_id=callback.from_user.id, target_id=order_code, details=status)
    order = get_tg_order(order_code)
    await notify_client_status_change(order, status)
    if callback.message.caption:
        await callback.message.edit_caption(
            manager_order_text(order),
            parse_mode=ParseMode.HTML,
            reply_markup=manager_order_keyboard(order_code, order.get("status"), callback.from_user.id),
        )
    else:
        await callback.message.edit_text(
            manager_order_text(order),
            parse_mode=ParseMode.HTML,
            reply_markup=manager_order_keyboard(order_code, order.get("status"), callback.from_user.id),
        )
    await callback.answer(f"Статус: {TG_ORDER_STATUSES[status]}")


@dp.callback_query(F.data.startswith("ocancel:"))
async def manager_status_cancel_confirm(callback: CallbackQuery):
    if not manager_can_manage(callback.from_user.id):
        await callback.answer("Нет доступа к изменению статуса.", show_alert=True)
        return
    order_code = callback.data.split(":")[1]
    MANAGER_CANCEL_DRAFTS.pop(callback.from_user.id, None)
    await callback.message.edit_reply_markup(reply_markup=manager_status_keyboard(order_code))
    await callback.answer("Действие отменено")


@dp.callback_query(F.data.startswith("oconfirm:"))
async def manager_status_confirm(callback: CallbackQuery):
    if not manager_can_manage(callback.from_user.id):
        await callback.answer("Нет доступа к изменению статуса.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некорректная команда", show_alert=True)
        return
    _, order_code, status = parts
    if status not in {"completed", "cancelled"}:
        await callback.answer("Неизвестный статус", show_alert=True)
        return
    current_order = get_tg_order(order_code)
    if not current_order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    if (current_order.get("status") or "") in FINAL_ORDER_STATUSES:
        await callback.answer("Заказ уже закрыт. Статус изменить нельзя.", show_alert=True)
        return
    if status == "cancelled":
        MANAGER_CANCEL_DRAFTS[callback.from_user.id] = {"order_code": order_code}
        await callback.message.answer(
            "Напишите причину отмены заказа одним сообщением.\n"
            + client_cancel_reason_hint(current_order.get("client_tg_id"))
        )
        await callback.answer("Жду причину отмены")
        return
    update_tg_order_status(order_code, status, callback.from_user)
    append_manager_log("order_status_changed", actor_id=callback.from_user.id, target_id=order_code, details=status)
    order = get_tg_order(order_code)
    await notify_client_status_change(order, status)
    if callback.message.caption:
        await callback.message.edit_caption(
            manager_order_text(order),
            parse_mode=ParseMode.HTML,
            reply_markup=manager_order_keyboard(order_code, order.get("status"), callback.from_user.id),
        )
    else:
        await callback.message.edit_text(
            manager_order_text(order),
            parse_mode=ParseMode.HTML,
            reply_markup=manager_order_keyboard(order_code, order.get("status"), callback.from_user.id),
        )
    await callback.answer(f"Статус: {TG_ORDER_STATUSES[status]}")


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty. Put Telegram bot token into .env")
    try:
        load_user_langs()
        try:
            ensure_tg_orders_table()
            ensure_tg_cart_table()
            ensure_tg_order_items_table()
            ensure_tg_order_reviews_table()
            ensure_manager_access_claim_columns()
            expire_cart_items()
        except Exception as e:
            print(f"⚠️ Database error during initialization: {e}")
            print("⚠️ Bot will start but database features will be limited")
        try:
            await refresh_manager_chat_ids()
        except Exception as e:
            print(f"⚠️ Manager chat refresh error: {e}")
        asyncio.create_task(cart_expirer_loop())
        if manager_bot:
            await dp.start_polling(bot, manager_bot)
        else:
            await dp.start_polling(bot)
    finally:
        if HTTP_SESSION and not HTTP_SESSION.closed:
            await HTTP_SESSION.close()
        DB_POOL.close()


if __name__ == "__main__":
    asyncio.run(main())


