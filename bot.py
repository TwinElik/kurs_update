import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    BufferedInputFile,
    InputMediaPhoto,
    KeyboardButton,
    MenuButtonDefault,
    Message,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

from image_renderer import ORG_TEMPLATES, build_price_image
from price_algorithm import calculate_prices, price_rows


load_dotenv()

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache" / "generated"
DB_PATH = DATA_DIR / "price_history.sqlite3"

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PHONE = os.getenv("PHONE", "").strip()

dp = Dispatcher()

GENERATE_BUTTON = "🧮 Изменить курс"
SHOW_BUTTON = "🖼 Показать 4 фото"

ORG_ORDER = ("diamant", "tillachi", "goldexpert", "skupka")
USER_WAITING_RATE = set()


def main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=GENERATE_BUTTON))
    builder.row(KeyboardButton(text=SHOW_BUTTON))
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
        input_field_placeholder="Выберите действие",
    )


def db_connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                main_rate TEXT NOT NULL,
                rows_json TEXT NOT NULL,
                created_by INTEGER,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generated_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generation_id INTEGER NOT NULL,
                org TEXT NOT NULL,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (generation_id) REFERENCES price_generations(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_price_generations_created_at ON price_generations(created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_generated_images_generation_id ON generated_images(generation_id)"
        )


def cleanup_old_generations():
    cutoff = datetime.now() - timedelta(days=7)
    cutoff_text = cutoff.isoformat(timespec="seconds")
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT id FROM price_generations WHERE created_at < ?",
            (cutoff_text,),
        ).fetchall()
        generation_ids = [row[0] for row in rows]
        if not generation_ids:
            return

        placeholders = ",".join("?" for _ in generation_ids)
        image_rows = conn.execute(
            f"SELECT path FROM generated_images WHERE generation_id IN ({placeholders})",
            generation_ids,
        ).fetchall()
        for (path_text,) in image_rows:
            path = Path(path_text)
            if path.exists():
                path.unlink()

        for generation_id in generation_ids:
            folder = CACHE_DIR / str(generation_id)
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)

        conn.execute(
            f"DELETE FROM generated_images WHERE generation_id IN ({placeholders})",
            generation_ids,
        )
        conn.execute(
            f"DELETE FROM price_generations WHERE id IN ({placeholders})",
            generation_ids,
        )


def parse_main_rate(text):
    match = re.search(r"\d+(?:[.,]\d+)?", text or "")
    if not match:
        return None
    try:
        return Decimal(match.group(0).replace(",", "."))
    except InvalidOperation:
        return None


def org_title(org):
    template = ORG_TEMPLATES.get(org, ORG_TEMPLATES["diamant"])
    return template.get("brand") or org.upper()


def price_text(main_rate, brand="diamant"):
    return f"Основной курс: {main_rate}"


def get_latest_generation():
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT id, main_rate, created_at, rows_json
            FROM price_generations
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return None

        image_rows = conn.execute(
            """
            SELECT org, filename, path
            FROM generated_images
            WHERE generation_id = ?
            ORDER BY id ASC
            """,
            (row[0],),
        ).fetchall()

    images = []
    for org, filename, path_text in image_rows:
        path = Path(path_text)
        if not path.exists():
            return None
        images.append(
            {
                "org": org,
                "filename": filename,
                "path": path,
                "bytes": path.read_bytes(),
            }
        )

    if len(images) != len(ORG_ORDER):
        return None

    return {"id": row[0], "main_rate": row[1], "created_at": row[2], "rows_json": row[3], "images": images}


def is_generated_today(generation):
    try:
        created_at = datetime.fromisoformat(generation["created_at"])
    except (KeyError, TypeError, ValueError):
        return False
    return created_at.date() == datetime.now().date()


def save_generation(main_rate, rows, images, created_by):
    created_at = datetime.now().isoformat(timespec="seconds")
    rows_json = json.dumps(rows, ensure_ascii=False)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with db_connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO price_generations (main_rate, rows_json, created_by, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(main_rate), rows_json, created_by, created_at),
        )
        generation_id = cursor.lastrowid
        generation_dir = CACHE_DIR / str(generation_id)
        generation_dir.mkdir(parents=True, exist_ok=True)

        saved_images = []
        for item in images:
            path = generation_dir / item["filename"]
            path.write_bytes(item["bytes"])
            conn.execute(
                """
                INSERT INTO generated_images (generation_id, org, filename, path, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (generation_id, item["org"], item["filename"], str(path), created_at),
            )
            saved_images.append({**item, "path": path})

    return {
        "id": generation_id,
        "main_rate": str(main_rate),
        "created_at": created_at,
        "images": saved_images,
    }


def media_group_from_images(images, main_rate):
    media = []
    for index, item in enumerate(images):
        caption = price_text(main_rate, item["org"]) if index == 0 else None
        media.append(
            InputMediaPhoto(
                media=BufferedInputFile(item["bytes"], filename=item["filename"]),
                caption=caption,
            )
        )
    return media


async def generate_all_images(message, main_rate):
    cleanup_old_generations()

    rows = {org: price_rows(main_rate, org) for org in ORG_ORDER}
    rows_json = json.dumps(rows, ensure_ascii=False)
    latest = get_latest_generation()
    if (
        latest
        and latest["main_rate"] == str(main_rate)
        and latest["rows_json"] == rows_json
        and is_generated_today(latest)
    ):
        await message.answer(
            "Цена не изменилась. Готовые 4 фото уже сохранены.\n"
            "Нажмите «Показать 4 фото».",
            reply_markup=main_keyboard(),
        )
        return

    progress = await message.answer("Генерация фото: 0/4")

    images = []
    total = len(ORG_ORDER)
    for index, org in enumerate(ORG_ORDER, start=1):
        ranges = calculate_prices(main_rate, org)
        image = build_price_image(ranges, org=org, phone=PHONE or None)
        images.append(
            {
                "org": org,
                "bytes": image,
                "filename": f"{org}_gold_prices_{main_rate}.png",
            }
        )
        await progress.edit_text(
            f"Генерация фото: {index}/{total}\nГотово: {org_title(org)}"
        )

    save_generation(main_rate, rows, images, message.from_user.id)
    await progress.edit_text(
        "Генерация завершена: 4/4"
    )


@dp.message(CommandStart())
async def start(message: Message):
    USER_WAITING_RATE.discard(message.from_user.id)
    await message.answer(
        "Выберите действие:",
        reply_markup=main_keyboard(),
    )


@dp.message(F.text == GENERATE_BUTTON)
async def ask_main_rate(message: Message):
    USER_WAITING_RATE.add(message.from_user.id)
    await message.answer(
        "Введите начальную цену числом, например: 1200",
        reply_markup=main_keyboard(),
    )


@dp.message(F.text == SHOW_BUTTON)
async def show_last_images(message: Message):
    cleanup_old_generations()
    latest = get_latest_generation()
    if not latest:
        await message.answer(
            "Готовых фото пока нет. Сначала нажми «Изменить курс».",
            reply_markup=main_keyboard(),
        )
        return

    await message.answer_media_group(
        media_group_from_images(latest["images"], latest["main_rate"])
    )


@dp.message(F.text)
async def handle_text(message: Message):
    if message.from_user.id not in USER_WAITING_RATE:
        await message.answer(
            "Чтобы изменить курс, сначала нажмите «Изменить курс».",
            reply_markup=main_keyboard(),
        )
        return

    main_rate = parse_main_rate(message.text)
    if main_rate is None or main_rate <= 0:
        await message.answer(
            "Нажми «Изменить курс» и отправь число, например: 1200",
            reply_markup=main_keyboard(),
        )
        return
    if main_rate > 9999:
        await message.answer(
            "Курс не должен быть больше 9999. Введите другое значение.",
            reply_markup=main_keyboard(),
        )
        return

    USER_WAITING_RATE.discard(message.from_user.id)
    await generate_all_images(message, main_rate)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty. Put token into .env")
    init_db()
    cleanup_old_generations()
    bot = Bot(BOT_TOKEN)
    await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
