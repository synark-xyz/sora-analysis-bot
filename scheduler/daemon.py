import asyncio
import os
import signal
from datetime import datetime, date
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

_NYSE_HOLIDAYS = {
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18",
    "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01",
    "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
    "2026-11-26", "2026-12-25",
}


def _is_trading_day(d=None):
    if d is None:
        d = date.today()
    return d.weekday() < 5 and d.isoformat() not in _NYSE_HOLIDAYS


def _is_us_market_open():
    now_et = datetime.now(ET)
    if not _is_trading_day(now_et.date()):
        return False
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now_et < market_close


class Daemon:
    def __init__(self):
        self.running = True
        self._last_scans = {}

    async def run(self):
        print("[Daemon] Started")

        while self.running:
            try:
                await self._tick()
            except Exception as e:
                print(f"[Daemon] Error: {e}")
            await asyncio.sleep(30)

    async def _tick(self):
        now_et = datetime.now(ET)

        if _is_trading_day(now_et.date()):
            for scan_time, scan_name in [
                ((9, 29), "us_morning"),
                ((11, 59), "us_midday"),
                ((15, 29), "us_preclose"),
            ]:
                target = now_et.replace(hour=scan_time[0], minute=scan_time[1], second=0, microsecond=0)
                key = f"us_{scan_name}_{now_et.date()}"
                if target <= now_et < now_et.replace(second=30) and self._last_scans.get(key) != now_et.date().isoformat():
                    self._last_scans[key] = now_et.date().isoformat()
                    await self._run_us_scan(scan_name)

        crypto_hour = now_et.hour
        if crypto_hour % 4 == 0 and now_et.minute == 0:
            key = f"crypto_{now_et.date()}_{crypto_hour}"
            if self._last_scans.get(key) != now_et.isoformat(timespec="h"):
                self._last_scans[key] = now_et.isoformat(timespec="h")
                await self._run_crypto_scan()

        if now_et.weekday() == 6 and now_et.hour == 20 and now_et.minute == 0:
            key = f"weekly_{now_et.isocalendar()[1]}"
            if self._last_scans.get(key) != str(now_et.isocalendar()[1]):
                self._last_scans[key] = str(now_et.isocalendar()[1])
                await self._run_weekly_review()

    async def _run_us_scan(self, scan_name):
        print(f"[Daemon] US scan starting: {scan_name}")
        try:
            from engine.orchestrator import run_pipeline
            from db.store import get_watchlist

            symbols = await asyncio.to_thread(get_watchlist)
            us_symbols = [s["symbol"] for s in symbols if s.get("market") == "us"]

            if not us_symbols:
                print("[Daemon] No US symbols in watchlist")
                return

            results = await run_pipeline(symbols=us_symbols, scan_name=scan_name)

            try:
                from telegram.handler import TELEGRAM_CHAT_ID
                from telegram.handler import TelegramHandler

                handler = TelegramHandler()
                for signal in results:
                    from telegram.formatter import format_signal_report
                    report = format_signal_report(signal)
                    await handler.send_message(report)
            except ImportError:
                for s in us_symbols:
                    print(f"[Daemon] Signal ready: {s}")

            print(f"[Daemon] US scan complete: {scan_name}")
        except ImportError as e:
            print(f"[Daemon] Engine not available (scan skipped): {e}")
        except Exception as e:
            print(f"[Daemon] Scan error: {e}")

    async def _run_crypto_scan(self):
        print("[Daemon] Crypto scan starting")
        try:
            from engine.orchestrator import run_pipeline
            from db.store import get_watchlist

            symbols = await asyncio.to_thread(get_watchlist)
            crypto_symbols = [s["symbol"] for s in symbols if s.get("market") == "crypto"]

            if not crypto_symbols:
                return

            results = await run_pipeline(symbols=crypto_symbols, scan_name="crypto")

            try:
                from telegram.handler import TelegramHandler

                handler = TelegramHandler()
                for signal in results:
                    from telegram.formatter import format_signal_report
                    report = format_signal_report(signal)
                    await handler.send_message(report)
            except ImportError:
                pass

            print(f"[Daemon] Crypto scan complete: {len(crypto_symbols)} symbols")
        except ImportError as e:
            print(f"[Daemon] Engine not available (crypto scan skipped): {e}")
        except Exception as e:
            print(f"[Daemon] Crypto scan error: {e}")

    async def _run_weekly_review(self):
        print("[Daemon] Weekly review starting")
        try:
            from memory.learner import run_weekly_review
            result = await run_weekly_review()

            try:
                from telegram.handler import TelegramHandler
                handler = TelegramHandler()
                await handler.send_message(
                    f"<b>Weekly Review Complete</b>\n\n{result.get('summary', 'Done')}"
                )
            except ImportError:
                pass

            print("[Daemon] Weekly review complete")
        except ImportError as e:
            print(f"[Daemon] Learner module not available (review skipped): {e}")
        except Exception as e:
            print(f"[Daemon] Weekly review error: {e}")
