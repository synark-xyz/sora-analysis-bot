import asyncio
import signal
import sys
import os
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from db.store import init_db
from telegram.handler import TelegramHandler
from scheduler.daemon import Daemon


async def _status_monitor(telegram: "TelegramHandler", daemon: "Daemon"):
    STUCK_THRESHOLD = 120  # seconds — warn if no tick/poll for 2 min
    CHECK_INTERVAL = 30

    await asyncio.sleep(15)  # let startup settle

    while True:
        now = time.monotonic()
        daemon_age = now - daemon.last_tick_at
        poll_age = now - telegram.last_poll_at
        poll_err = telegram.poll_errors

        daemon_ok = daemon_age < STUCK_THRESHOLD
        poll_ok = poll_age < STUCK_THRESHOLD

        daemon_icon = "✅" if daemon_ok else "🔴"
        poll_icon = "✅" if poll_ok else "🔴"

        print(
            f"[Monitor] {daemon_icon} daemon tick {daemon_age:.0f}s ago (#{daemon.tick_count}, last: {daemon.last_scan_label})"
            f"  |  {poll_icon} telegram poll {poll_age:.0f}s ago"
            + (f"  |  ⚠️  poll errors: {poll_err}" if poll_err else "")
        )

        if not daemon_ok:
            print(f"[Monitor] ⚠️  DAEMON STUCK — no tick for {daemon_age:.0f}s")
        if not poll_ok:
            print(f"[Monitor] ⚠️  TELEGRAM STUCK — no poll for {poll_age:.0f}s")

        await asyncio.sleep(CHECK_INTERVAL)


async def main():
    init_db()

    telegram = TelegramHandler()
    daemon = Daemon()

    tasks = [
        asyncio.create_task(telegram.run()),
        asyncio.create_task(daemon.run()),
        asyncio.create_task(_status_monitor(telegram, daemon)),
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
