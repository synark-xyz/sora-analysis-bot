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

    await asyncio.gather(
        telegram.run(),
        daemon.run(),
    )


if __name__ == "__main__":
    print("No Trading Bot v2 starting...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Noor Bot stopped")
        sys.exit(0)
