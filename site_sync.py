import asyncio
import json
import os
from contextlib import contextmanager
from datetime import datetime

import aiohttp
import pymysql
from dotenv import load_dotenv


load_dotenv()

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

SYNC_JOB_TABLE = "site_sync_jobs"
SYNC_TIMEOUT_SECONDS = int(os.getenv("SITE_SYNC_TIMEOUT_SECONDS", "10"))


def _env_name(brand, suffix):
    return f"{brand.upper()}_{suffix}"


def _enabled_from_env(brand, url, token):
    value = os.getenv(_env_name(brand, "SYNC_ENABLED"), "").strip()
    if value:
        return value == "1"
    if brand == "diamant":
        legacy = os.getenv("ENABLE_DIAMANT_ENDPOINT_SYNC", "").strip()
        if legacy:
            return legacy == "1"
    return bool(url and token)


def get_site_configs():
    configs = []
    for brand in ("diamant", "tillachi", "goldexpert", "skupka"):
        url = os.getenv(_env_name(brand, "ENDPOINT_URL"), "").strip()
        token = os.getenv(_env_name(brand, "ENDPOINT_TOKEN"), "").strip()

        if brand == "diamant":
            url = url or os.getenv("DIAMANT_ENDPOINT_URL", "").strip()
            token = token or os.getenv("DIAMANT_ENDPOINT_TOKEN", "").strip()

        if _enabled_from_env(brand, url, token):
            configs.append(
                {
                    "brand": brand,
                    "endpoint_url": url,
                    "token": token,
                }
            )
    return configs


@contextmanager
def db_connection():
    if not DB_CONFIG["user"] or not DB_CONFIG["database"]:
        raise RuntimeError("MySQL settings are empty. Fill DB_HOST, DB_USER, DB_PASSWORD, DB_NAME in .env")

    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_sync_db():
    with db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS `{SYNC_JOB_TABLE}` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `brand` VARCHAR(64) NOT NULL,
                    `endpoint_url` TEXT NOT NULL,
                    `source_price_id` INT NOT NULL,
                    `payload_json` LONGTEXT NOT NULL,
                    `status` VARCHAR(32) NOT NULL DEFAULT 'pending',
                    `attempts` INT NOT NULL DEFAULT 0,
                    `last_error` TEXT NULL,
                    `created_at` DATETIME NOT NULL,
                    `updated_at` DATETIME NOT NULL,
                    `synced_at` DATETIME NULL,
                    UNIQUE KEY `uq_brand_source_price` (`brand`, `source_price_id`),
                    INDEX `idx_status_updated_at` (`status`, `updated_at`),
                    INDEX `idx_source_price_id` (`source_price_id`)
                ) DEFAULT CHARSET=utf8mb4
                """
            )


def enqueue_site_sync_jobs(event):
    init_sync_db()
    configs = get_site_configs()
    if not configs:
        print("Site sync skipped: no enabled site endpoints")
        return []

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload_json = json.dumps(event, ensure_ascii=False)
    source_price_id = int(event["generation_id"])
    job_ids = []

    with db_connection() as conn:
        with conn.cursor() as cursor:
            for config in configs:
                cursor.execute(
                    f"""
                    INSERT INTO `{SYNC_JOB_TABLE}`
                        (brand, endpoint_url, source_price_id, payload_json, status, attempts, created_at, updated_at)
                    VALUES
                        (%s, %s, %s, %s, 'pending', 0, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        endpoint_url = VALUES(endpoint_url),
                        payload_json = VALUES(payload_json),
                        status = IF(status = 'success', status, 'pending'),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        config["brand"],
                        config["endpoint_url"],
                        source_price_id,
                        payload_json,
                        now,
                        now,
                    ),
                )
                cursor.execute(
                    f"""
                    SELECT id
                    FROM `{SYNC_JOB_TABLE}`
                    WHERE brand = %s AND source_price_id = %s
                    """,
                    (config["brand"], source_price_id),
                )
                row = cursor.fetchone()
                if row:
                    job_ids.append(row[0])
    return job_ids


def fetch_sync_jobs(statuses=("pending", "failed"), limit=10):
    init_sync_db()
    placeholders = ", ".join(["%s"] * len(statuses))
    with db_connection() as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                f"""
                SELECT id, brand, endpoint_url, source_price_id, payload_json, status, attempts
                FROM `{SYNC_JOB_TABLE}`
                WHERE status IN ({placeholders})
                ORDER BY updated_at ASC, id ASC
                LIMIT %s
                """,
                (*statuses, int(limit)),
            )
            return list(cursor.fetchall())


def get_sync_status(limit=20):
    init_sync_db()
    with db_connection() as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                f"""
                SELECT brand, status, COUNT(*) AS count
                FROM `{SYNC_JOB_TABLE}`
                GROUP BY brand, status
                ORDER BY brand ASC, status ASC
                """
            )
            totals = list(cursor.fetchall())
            cursor.execute(
                f"""
                SELECT id, brand, source_price_id, status, attempts, last_error, updated_at, synced_at
                FROM `{SYNC_JOB_TABLE}`
                ORDER BY updated_at DESC, id DESC
                LIMIT %s
                """,
                (int(limit),),
            )
            latest = list(cursor.fetchall())
    return {"totals": totals, "latest": latest}


def _mark_job_result(job_id, success, error=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_connection() as conn:
        with conn.cursor() as cursor:
            if success:
                cursor.execute(
                    f"""
                    UPDATE `{SYNC_JOB_TABLE}`
                    SET status = 'success',
                        attempts = attempts + 1,
                        last_error = NULL,
                        updated_at = %s,
                        synced_at = %s
                    WHERE id = %s
                    """,
                    (now, now, int(job_id)),
                )
            else:
                cursor.execute(
                    f"""
                    UPDATE `{SYNC_JOB_TABLE}`
                    SET status = 'failed',
                        attempts = attempts + 1,
                        last_error = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    ((error or "unknown error")[:2000], now, int(job_id)),
                )


async def send_sync_job(job):
    configs = {config["brand"]: config for config in get_site_configs()}
    config = configs.get(job["brand"])
    if not config or not config.get("token"):
        error = f"missing endpoint token for brand {job['brand']}"
        _mark_job_result(job["id"], False, error)
        print(f"Site sync failed: job={job['id']} {error}")
        return False

    endpoint_url = config.get("endpoint_url") or job["endpoint_url"]
    if not endpoint_url:
        error = f"missing endpoint url for brand {job['brand']}"
        _mark_job_result(job["id"], False, error)
        print(f"Site sync failed: job={job['id']} {error}")
        return False

    try:
        payload = json.loads(job["payload_json"])
    except json.JSONDecodeError as exc:
        error = f"invalid payload json: {exc}"
        _mark_job_result(job["id"], False, error)
        print(f"Site sync failed: job={job['id']} {error}")
        return False

    try:
        timeout = aiohttp.ClientTimeout(total=SYNC_TIMEOUT_SECONDS)
        headers = {
            "Content-Type": "application/json",
            "X-Gold-Price-Token": config["token"],
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(endpoint_url, json=payload, headers=headers) as response:
                body = await response.text()
                if response.status < 200 or response.status >= 300:
                    error = f"HTTP {response.status}: {body[:500]}"
                    _mark_job_result(job["id"], False, error)
                    print(f"Site sync failed: job={job['id']} brand={job['brand']} {error}")
                    return False

        _mark_job_result(job["id"], True)
        print(f"Site sync OK: job={job['id']} brand={job['brand']} source_price_id={job['source_price_id']}")
        return True
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        _mark_job_result(job["id"], False, error)
        print(f"Site sync failed: job={job['id']} brand={job['brand']} {error}")
        return False


async def process_sync_jobs(limit=10):
    jobs = fetch_sync_jobs(limit=limit)
    if not jobs:
        return 0
    results = await asyncio.gather(*(send_sync_job(job) for job in jobs))
    return sum(1 for result in results if result)


async def enqueue_and_send_site_sync_jobs(event):
    job_ids = enqueue_site_sync_jobs(event)
    if not job_ids:
        return 0

    with db_connection() as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            placeholders = ", ".join(["%s"] * len(job_ids))
            cursor.execute(
                f"""
                SELECT id, brand, endpoint_url, source_price_id, payload_json, status, attempts
                FROM `{SYNC_JOB_TABLE}`
                WHERE id IN ({placeholders}) AND status != 'success'
                """,
                tuple(job_ids),
            )
            jobs = list(cursor.fetchall())

    if not jobs:
        return 0

    results = await asyncio.gather(*(send_sync_job(job) for job in jobs))
    return sum(1 for result in results if result)
