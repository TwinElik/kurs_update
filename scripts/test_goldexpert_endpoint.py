import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from price_algorithm import calculate_prices


load_dotenv()

url = os.getenv("GOLDEXPERT_ENDPOINT_URL", "").strip()
secret = os.getenv("GOLDEXPERT_ENDPOINT_TOKEN", "").strip()
if not url or not secret:
    raise SystemExit("Fill GOLDEXPERT_ENDPOINT_URL and GOLDEXPERT_ENDPOINT_TOKEN in .env")

source_price_id = int(time.time())
main_rate = 890
price_ranges = calculate_prices(main_rate, "goldexpert")
prices = {}
for sample, (minimum, maximum) in price_ranges.items():
    prices[f"{sample}_from"] = int(minimum)
    prices[f"{sample}_to"] = int(maximum)

payload = {
    "event": "gold_price_updated",
    "generation_id": source_price_id,
    "kurs": main_rate * 1000,
    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "brands": {"goldexpert": prices},
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

public_url = url.rsplit("/", 1)[0] + "/current-gold-prices.json?v=" + str(source_price_id)
try:
    with urllib.request.urlopen(public_url, timeout=10) as response:
        public_data = json.loads(response.read().decode("utf-8"))
except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
    raise SystemExit(f"Public JSON check failed: {exc}") from exc

expected = prices["999_from"]
actual = public_data.get("fields", {}).get("proba_999_begin")
if public_data.get("ok") is not True or actual != expected:
    raise SystemExit(
        f"Public JSON has wrong proba_999_begin: expected {expected}, got {actual}"
    )

print(f"Public JSON OK: proba_999_begin={actual}")
