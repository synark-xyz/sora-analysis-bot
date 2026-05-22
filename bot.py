import asyncio
import signal
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from db.store import init_db
from telegram.handler import TelegramHandler
from scheduler.daemon import Daemon


async def main():
    init_db()

    telegram = TelegramHandler()
    daemon = Daemon()

    tasks = [
        asyncio.create_task(telegram.run()),
        asyncio.create_task(daemon.run()),
    ]

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[Bot] Shutting down...")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    print("Sora Bot v2 starting...")

    asyncio.run(main())
    print("Sora Bot stopped")
    sys.exit(0)
