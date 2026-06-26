import json
import os

import pika
from dotenv import load_dotenv


load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@127.0.0.1:5672/")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "kurs_site_sync")


def publish_site_sync_job(message):
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=json.dumps(message, ensure_ascii=False).encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
            ),
        )
        connection.close()
        return True
    except Exception as exc:
        print(f"RabbitMQ publish failed: {type(exc).__name__}: {exc}")
        return False
