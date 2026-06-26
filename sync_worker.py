import json
import os
from datetime import datetime

import pika
import pymysql
from dotenv import load_dotenv

from price_algorithm import PROBES
from sites_config import SITE_BY_BRAND


load_dotenv()

CENTRAL_DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", ""),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", ""),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "connect_timeout": 5,
    "read_timeout": 10,
    "write_timeout": 10,
}

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@127.0.0.1:5672/")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "kurs_site_sync")


def sql_quote(name):
    return "`" + str(name).replace("`", "``") + "`"


def db_connect(config):
    return pymysql.connect(**config)


def site_db_config(site):
    prefix = site["db_env_prefix"]
    return {
        "host": os.getenv(f"{prefix}_HOST", ""),
        "port": int(os.getenv(f"{prefix}_PORT", "3306")),
        "user": os.getenv(f"{prefix}_USER", ""),
        "password": os.getenv(f"{prefix}_PASSWORD", ""),
        "database": os.getenv(f"{prefix}_NAME", ""),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "connect_timeout": 5,
        "read_timeout": 10,
        "write_timeout": 10,
    }


def validate_site_config(config, brand):
    missing = [key for key in ("host", "user", "database") if not config.get(key)]
    if missing:
        raise RuntimeError(f"Missing site DB config for {brand}: {', '.join(missing)}")


def flat_price_columns():
    columns = []
    for sample in PROBES:
        columns.extend((f"{sample}_from", f"{sample}_to"))
    return columns


def create_site_table_if_needed(conn, table_name):
    price_columns_sql = ",\n                ".join(
        f"{sql_quote(column)} INT NOT NULL" for column in flat_price_columns()
    )
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {sql_quote(table_name)} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                source_price_id INT NOT NULL,
                kurs INT NOT NULL,
                {price_columns_sql},
                created_at DATETIME NOT NULL,
                UNIQUE KEY uq_source_price_id (source_price_id),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cursor.execute(f"SHOW COLUMNS FROM {sql_quote(table_name)} LIKE 'source_price_id'")
        if not cursor.fetchone():
            cursor.execute(
                f"ALTER TABLE {sql_quote(table_name)} ADD COLUMN source_price_id INT NULL AFTER id"
            )
        cursor.execute(f"SHOW INDEX FROM {sql_quote(table_name)} WHERE Key_name = 'uq_source_price_id'")
        if not cursor.fetchone():
            cursor.execute(
                f"ALTER TABLE {sql_quote(table_name)} ADD UNIQUE KEY uq_source_price_id (source_price_id)"
            )
    conn.commit()


def mark_job(job_id, status, error=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_connect(CENTRAL_DB_CONFIG) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE site_sync_jobs
                SET status = %s,
                    attempts = attempts + 1,
                    last_error = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (status, error, now, job_id),
            )
        conn.commit()


def fetch_job_and_price(job_id):
    with db_connect(CENTRAL_DB_CONFIG) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM site_sync_jobs WHERE id = %s LIMIT 1", (job_id,))
            job = cursor.fetchone()
            if not job:
                raise RuntimeError(f"Job {job_id} not found")
            cursor.execute(
                f"SELECT * FROM {sql_quote(job['source_table'])} WHERE id = %s LIMIT 1",
                (job["source_price_id"],),
            )
            price = cursor.fetchone()
            if not price:
                raise RuntimeError(
                    f"Source price {job['source_price_id']} not found in {job['source_table']}"
                )
            cursor.execute(
                """
                UPDATE site_sync_jobs
                SET status = 'processing', updated_at = %s
                WHERE id = %s
                """,
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), job_id),
            )
        conn.commit()
    return job, price


def insert_site_price(job, price):
    brand = job["brand"]
    site = SITE_BY_BRAND.get(brand)
    if not site:
        raise RuntimeError(f"Unknown brand: {brand}")

    config = site_db_config(site)
    validate_site_config(config, brand)

    columns = ["source_price_id", "kurs", *flat_price_columns(), "created_at"]
    values = [job["source_price_id"], price["kurs"]]
    for sample in PROBES:
        values.extend((price[f"{sample}_from"], price[f"{sample}_to"]))
    values.append(price["created_at"])

    columns_sql = ", ".join(sql_quote(column) for column in columns)
    placeholders = ", ".join("%s" for _ in values)

    with db_connect(config) as conn:
        create_site_table_if_needed(conn, job["target_table"])
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {sql_quote(job['target_table'])} ({columns_sql})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE source_price_id = source_price_id
                """,
                values,
            )
        conn.commit()


def process_message(body):
    payload = json.loads(body.decode("utf-8"))
    job_id = int(payload["job_id"])
    try:
        job, price = fetch_job_and_price(job_id)
        insert_site_price(job, price)
        mark_job(job_id, "success")
        print(f"Synced job {job_id}: {job['brand']} -> {job['target_site']}")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        mark_job(job_id, "failed", error[:2000])
        print(f"Sync job {job_id} failed: {error}")


def main():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        try:
            process_message(body)
        except Exception as exc:
            print(f"Bad sync message skipped: {type(exc).__name__}: {exc}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
    print(f"Waiting for sync jobs in queue: {RABBITMQ_QUEUE}")
    channel.start_consuming()


if __name__ == "__main__":
    main()
