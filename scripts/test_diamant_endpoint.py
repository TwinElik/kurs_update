import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime

from dotenv import load_dotenv


load_dotenv()

url = os.getenv("DIAMANT_ENDPOINT_URL", "").strip()
secret = os.getenv("DIAMANT_ENDPOINT_TOKEN", "").strip()
if not url or not secret:
    raise SystemExit("Fill DIAMANT_ENDPOINT_URL and DIAMANT_ENDPOINT_TOKEN in .env")

source_price_id = int(time.time())
payload = {
    "event": "gold_price_updated",
    "generation_id": source_price_id,
    "kurs": 890000,
    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "brands": {
        "diamant": {
            "375_from": 575000,
            "375_to": 630000,
            "583_from": 890000,
            "583_to": 1500000,
            "585_from": 890000,
            "585_to": 1090000,
            "750_from": 1145000,
            "750_to": 1500000,
            "850_from": 1300000,
            "850_to": 1500000,
            "875_from": 1340000,
            "875_to": 1540000,
            "916_from": 1400000,
            "916_to": 1600000,
            "999_from": 1530000,
            "999_to": 1680000,
        }
    },
}

body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
timestamp = str(int(time.time()))
signature = hmac.new(
    secret.encode("utf-8"),
    timestamp.encode("ascii") + b"." + body,
    hashlib.sha256,
).hexdigest()

request = urllib.request.Request(
    url,
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-Gold-Price-Timestamp": timestamp,
        "X-Gold-Price-Signature": signature,
    },
    method="POST",
)

try:
    with urllib.request.urlopen(request, timeout=10) as response:
        print(response.status, response.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    print(exc.code, exc.read().decode("utf-8"))
    raise SystemExit(1) from exc
