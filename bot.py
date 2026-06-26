import json
import os
import re
import shutil
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymysql
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
from price_algorithm import PROBES, calculate_prices, price_rows
from rabbitmq_publisher import publish_site_sync_job
from sites_config import SITE_BY_BRAND, SITES


load_dotenv()

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache" / "generated"

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PHONE = os.getenv("PHONE", "").strip()
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", ""),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", ""),
    "charset": "utf8mb4",
    "connect_timeout": 5,
    "read_timeout": 10,
    "write_timeout": 10,
}

dp = Dispatcher()

GENERATE_BUTTON = "🧮 Изменить курс"
SHOW_BUTTON = "🖼 Показать 4 фото"
SYNC_STATUS_BUTTON = "📡 Статус сайтов"
RETRY_SYNC_BUTTON = "🔁 Повторить failed sync"

ORG_ORDER = ("diamant", "tillachi", "goldexpert", "skupka")
USER_WAITING_RATE = set()
PRICE_TABLES = {
    "diamant": "diamant_gold_prices",
    "tillachi": "tillachi_gold_prices",
    "goldexpert": "goldexpert_gold_prices",
    "skupka": "skupka_gold_prices",
}


def main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=GENERATE_BUTTON))
    builder.row(KeyboardButton(text=SHOW_BUTTON))
    builder.row(KeyboardButton(text=SYNC_STATUS_BUTTON))
    builder.row(KeyboardButton(text=RETRY_SYNC_BUTTON))
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
        input_field_placeholder="Выберите действие",
    )


class DbConnection:
    def __enter__(self):
        self.conn = pymysql.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            self.cursor.close()
            self.conn.close()

    def execute(self, sql, params=None):
        self.cursor.execute(sql, params or ())
        return self.cursor


def db_connect():
    if not DB_CONFIG["user"] or not DB_CONFIG["database"]:
        raise RuntimeError("MySQL settings are empty. Fill DB_HOST, DB_USER, DB_PASSWORD, DB_NAME in .env")
    return DbConnection()


def sql_quote(name):
    return "`" + str(name).replace("`", "``") + "`"


def kurs_value(main_rate):
    return int((Decimal(str(main_rate)) * Decimal(1000)).to_integral_value())


def flat_price_columns():
    columns = []
    for sample in PROBES:
        columns.extend((f"{sample}_from", f"{sample}_to"))
    return columns


def create_flat_price_table(conn, table_name):
    price_columns_sql = ",\n                ".join(
        f"{sql_quote(column)} INT NOT NULL" for column in flat_price_columns()
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {sql_quote(table_name)} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            kurs INT NOT NULL,
            {price_columns_sql},
            created_at DATETIME NOT NULL,
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def init_db():
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_generations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                main_rate VARCHAR(32) NOT NULL,
                rows_json LONGTEXT NOT NULL,
                created_by BIGINT NULL,
                created_at DATETIME NOT NULL,
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generated_images (
                id INT AUTO_INCREMENT PRIMARY KEY,
                generation_id INT NOT NULL,
                org VARCHAR(64) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                path TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                INDEX idx_generation_id (generation_id),
                FOREIGN KEY (generation_id) REFERENCES price_generations(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        for table_name in PRICE_TABLES.values():
            create_flat_price_table(conn, table_name)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS site_sync_jobs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                brand VARCHAR(64) NOT NULL,
                source_table VARCHAR(128) NOT NULL,
                source_price_id INT NOT NULL,
                target_site VARCHAR(255) NOT NULL,
                target_table VARCHAR(128) NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                attempts INT NOT NULL DEFAULT 0,
                last_error TEXT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                UNIQUE KEY uq_brand_source_price (brand, source_price_id),
                INDEX idx_status_created_at (status, created_at),
                INDEX idx_brand_status (brand, status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )


def cleanup_old_generations():
    cutoff = datetime.now() - timedelta(days=7)
    cutoff_text = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT id FROM price_generations WHERE created_at < %s",
            (cutoff_text,),
        ).fetchall()
        generation_ids = [row[0] for row in rows]
        for table_name in PRICE_TABLES.values():
            conn.execute(
                f"DELETE FROM {sql_quote(table_name)} WHERE created_at < %s",
                (cutoff_text,),
            )
        if not generation_ids:
            return

        placeholders = ",".join("%s" for _ in generation_ids)
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
            WHERE generation_id = %s
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
        raw_created_at = generation["created_at"]
        created_at = raw_created_at if isinstance(raw_created_at, datetime) else datetime.fromisoformat(raw_created_at)
    except (KeyError, TypeError, ValueError):
        return False
    return created_at.date() == datetime.now().date()


def save_flat_price_row(conn, org, main_rate, created_at):
    table_name = PRICE_TABLES[org]
    prices = calculate_prices(main_rate, org)
    columns = ["kurs"]
    values = [kurs_value(main_rate)]

    for sample in PROBES:
        price_from, price_to = prices[str(sample)]
        columns.extend((f"{sample}_from", f"{sample}_to"))
        values.extend((price_from, price_to))

    columns.append("created_at")
    values.append(created_at)

    columns_sql = ", ".join(sql_quote(column) for column in columns)
    placeholders = ", ".join("%s" for _ in values)
    cursor = conn.execute(
        f"INSERT INTO {sql_quote(table_name)} ({columns_sql}) VALUES ({placeholders})",
        values,
    )
    return cursor.lastrowid


def create_site_sync_job(conn, org, source_price_id, created_at):
    site = SITE_BY_BRAND.get(org)
    if not site:
        return None
    cursor = conn.execute(
        """
        INSERT INTO site_sync_jobs (
            brand, source_table, source_price_id, target_site, target_table,
            status, attempts, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, 'pending', 0, %s, %s)
        ON DUPLICATE KEY UPDATE
            status = IF(status = 'success', status, 'pending'),
            updated_at = VALUES(updated_at)
        """,
        (
            org,
            site["source_table"],
            source_price_id,
            site["target_site"],
            site["target_table"],
            created_at,
            created_at,
        ),
    )
    if cursor.lastrowid:
        return cursor.lastrowid
    row = conn.execute(
        """
        SELECT id
        FROM site_sync_jobs
        WHERE brand = %s AND source_price_id = %s
        LIMIT 1
        """,
        (org, source_price_id),
    ).fetchone()
    return row[0] if row else None


def queue_site_sync_job(conn, job_id, org, source_price_id):
    if not job_id:
        return False
    published = publish_site_sync_job(
        {
            "job_id": job_id,
            "brand": org,
            "source_price_id": source_price_id,
        }
    )
    if published:
        conn.execute(
            """
            UPDATE site_sync_jobs
            SET status = 'queued', updated_at = %s
            WHERE id = %s AND status IN ('pending', 'failed')
            """,
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), job_id),
        )
    return published


def get_sync_status_text():
    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT brand, status, COUNT(*)
            FROM site_sync_jobs
            GROUP BY brand, status
            ORDER BY brand, status
            """
        ).fetchall()
    if not rows:
        return "Sync jobs not found yet."

    grouped = {}
    for brand, status, count in rows:
        grouped.setdefault(brand, {})[status] = count

    lines = ["Site sync status:"]
    for site in SITES:
        brand = site["brand"]
        stats = grouped.get(brand, {})
        if not stats:
            lines.append(f"{brand}: no jobs")
            continue
        details = ", ".join(f"{status}={count}" for status, count in sorted(stats.items()))
        lines.append(f"{brand}: {details}")
    return "\n".join(lines)


def retry_failed_sync_jobs(limit=100):
    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT id, brand, source_price_id
            FROM site_sync_jobs
            WHERE status IN ('failed', 'pending')
            ORDER BY id ASC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
        queued = 0
        for job_id, brand, source_price_id in rows:
            if queue_site_sync_job(conn, job_id, brand, source_price_id):
                queued += 1
    return len(rows), queued


def save_generation(main_rate, rows, images, created_by):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows_json = json.dumps(rows, ensure_ascii=False)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    sync_jobs = []
    with db_connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO price_generations (main_rate, rows_json, created_by, created_at)
            VALUES (%s, %s, %s, %s)
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
                VALUES (%s, %s, %s, %s, %s)
                """,
                (generation_id, item["org"], item["filename"], str(path), created_at),
            )
            saved_images.append({**item, "path": path})

        for org in ORG_ORDER:
            source_price_id = save_flat_price_row(conn, org, main_rate, created_at)
            job_id = create_site_sync_job(conn, org, source_price_id, created_at)
            sync_jobs.append((job_id, org, source_price_id))

    with db_connect() as conn:
        for job_id, org, source_price_id in sync_jobs:
            queue_site_sync_job(conn, job_id, org, source_price_id)

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


@dp.message(F.text == SYNC_STATUS_BUTTON)
async def show_sync_status(message: Message):
    await message.answer(get_sync_status_text(), reply_markup=main_keyboard())


@dp.message(F.text == RETRY_SYNC_BUTTON)
async def retry_sync(message: Message):
    total, queued = retry_failed_sync_jobs()
    await message.answer(
        f"Sync retry: found {total}, queued {queued}.",
        reply_markup=main_keyboard(),
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
