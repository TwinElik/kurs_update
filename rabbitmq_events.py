import json
import os
import time

import aio_pika
from dotenv import load_dotenv

from price_algorithm import PROBES, calculate_prices


load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://jewelry_user:my_secure_password@localhost/")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "gold_price_events")


def _flat_prices_for_brand(main_rate, brand):
    prices = calculate_prices(main_rate, brand)
    result = {}
    for sample in PROBES:
        price_from, price_to = prices[str(sample)]
        result[f"{sample}_from"] = price_from
        result[f"{sample}_to"] = price_to
    return result


def build_gold_price_event(main_rate, generation):
    return {
        "event": "gold_price_updated",
        "generation_id": generation["id"],
        "price": float(main_rate),
        "kurs": int(float(main_rate) * 1000),
        "timestamp": int(time.time()),
        "created_at": generation["created_at"],
        "brands": {
            brand: _flat_prices_for_brand(main_rate, brand)
            for brand in ("diamant", "tillachi", "goldexpert", "skupka")
        },
    }


async def publish_gold_price_event(main_rate, generation):
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(RABBITMQ_QUEUE, durable=True)
            message = aio_pika.Message(
                body=json.dumps(
                    build_gold_price_event(main_rate, generation),
                    ensure_ascii=False,
                ).encode("utf-8"),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await channel.default_exchange.publish(
                message,
                routing_key=RABBITMQ_QUEUE,
            )
        return True
    except Exception as exc:
        print(f"RabbitMQ publish failed: {type(exc).__name__}: {exc}")
        return False

