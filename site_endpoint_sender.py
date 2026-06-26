import os

import aiohttp
from dotenv import load_dotenv


load_dotenv()

DISABLE_DIAMANT_ENDPOINT_SYNC = os.getenv("ENABLE_DIAMANT_ENDPOINT_SYNC", "1").strip() == "0"
DIAMANT_ENDPOINT_URL = os.getenv("DIAMANT_ENDPOINT_URL", "").strip()
DIAMANT_ENDPOINT_TOKEN = os.getenv("DIAMANT_ENDPOINT_TOKEN", "").strip()


async def send_diamant_price_event(event):
    if DISABLE_DIAMANT_ENDPOINT_SYNC:
        print("Diamant endpoint sync skipped: ENABLE_DIAMANT_ENDPOINT_SYNC=0")
        return False
    if not DIAMANT_ENDPOINT_URL or not DIAMANT_ENDPOINT_TOKEN:
        print("Diamant endpoint sync skipped: DIAMANT_ENDPOINT_URL or DIAMANT_ENDPOINT_TOKEN is empty")
        return False

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        headers = {
            "Content-Type": "application/json",
            "X-Gold-Price-Token": DIAMANT_ENDPOINT_TOKEN,
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(DIAMANT_ENDPOINT_URL, json=event, headers=headers) as response:
                body = await response.text()
                if response.status < 200 or response.status >= 300:
                    print(f"Diamant endpoint sync failed: HTTP {response.status}: {body[:300]}")
                    return False
        print("Diamant endpoint sync OK")
        return True
    except Exception as exc:
        print(f"Diamant endpoint sync failed: {type(exc).__name__}: {exc}")
        return False
