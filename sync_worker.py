import asyncio
import os

from dotenv import load_dotenv

from site_sync import init_sync_db, process_sync_jobs


load_dotenv()

SYNC_WORKER_INTERVAL_SECONDS = int(os.getenv("SYNC_WORKER_INTERVAL_SECONDS", "60"))
SYNC_WORKER_BATCH_SIZE = int(os.getenv("SYNC_WORKER_BATCH_SIZE", "10"))


async def main():
    init_sync_db()
    print("Site sync worker started")
    while True:
        try:
            synced = await process_sync_jobs(limit=SYNC_WORKER_BATCH_SIZE)
            if synced:
                print(f"Site sync worker synced {synced} job(s)")
        except Exception as exc:
            print(f"Site sync worker error: {type(exc).__name__}: {exc}")
        await asyncio.sleep(SYNC_WORKER_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
