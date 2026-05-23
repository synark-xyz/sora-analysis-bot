import asyncio
import hashlib
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


_BINANCE_PRICE_SYMBOLS = {
    "BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT",
    "BNB": "BNBUSDT", "AVAX": "AVAXUSDT", "LINK": "LINKUSDT",
    "DOT": "DOTUSDT", "MATIC": "MATICUSDT", "ADA": "ADAUSDT", "XRP": "XRPUSDT",
}


def _get_current_price(symbol: str, market: str) -> float | None:
    import os, requests
    try:
        if market == "crypto":
            pair = _BINANCE_PRICE_SYMBOLS.get(symbol.upper())
            if not pair:
                return None
            r = requests.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={"symbol": pair},
                timeout=10,
            )
            return float(r.json()["price"])
        else:
            api_key = os.getenv("FINNHUB_API_KEY", "")
            if not api_key:
                return None
            r = requests.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": symbol, "token": api_key},
                timeout=10,
            )
            price = r.json().get("c")
            return float(price) if price else None
    except Exception:
        return None


class Daemon:
    def __init__(self):
        self.running = True
        self._last_scans = {}
        self._seen_news: set = set()

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
            # Four US scan windows
            for scan_time, scan_name in [
                ((8, 30), "us_premarket"),   # 1 hr before open
                ((9, 50), "us_postopen"),    # 20 min after open
                ((11, 59), "us_midday"),
                ((14, 30), "us_preclose"),   # 1 hr before close
            ]:
                target = now_et.replace(hour=scan_time[0], minute=scan_time[1], second=0, microsecond=0)
                key = f"{scan_name}_{now_et.date()}"
                if target <= now_et < target.replace(second=30) and self._last_scans.get(key) != now_et.date().isoformat():
                    self._last_scans[key] = now_et.date().isoformat()
                    await self._run_us_scan(scan_name)

            # Position scan every 30 min during market hours
            if _is_us_market_open():
                if now_et.minute % 30 == 0 and now_et.second < 30:
                    key = f"positions_{now_et.date()}_{now_et.hour}_{now_et.minute}"
                    if self._last_scans.get(key) != key:
                        self._last_scans[key] = key
                        await self._run_position_scan("us")

        # Crypto scans every 4 hours
        crypto_hour = now_et.hour
        if crypto_hour % 4 == 0 and now_et.minute == 0:
            key = f"crypto_{now_et.date()}_{crypto_hour}"
            if self._last_scans.get(key) != now_et.isoformat(timespec="hours"):
                self._last_scans[key] = now_et.isoformat(timespec="hours")
                await self._run_crypto_scan()

        # Crypto position scan every 2 hours at :30
        if now_et.hour % 2 == 0 and now_et.minute == 30 and now_et.second < 30:
            key = f"crypto_positions_{now_et.date()}_{now_et.hour}"
            if self._last_scans.get(key) != key:
                self._last_scans[key] = key
                await self._run_position_scan("crypto")

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

            from telegram.handler import TelegramHandler
            from telegram.formatter import format_signal_report
            handler = TelegramHandler()

            for sym in us_symbols:
                try:
                    signal = await asyncio.to_thread(run_pipeline, sym, "us", "swing")
                    if signal and signal.get("verdict") != "HOLD" and signal.get("gate_passed"):
                        if signal.get("verdict") == "BUY":
                            price = await asyncio.to_thread(_get_current_price, sym, "us")
                            if price:
                                entry_high = signal.get("entry_high")
                                if entry_high and price > entry_high * 1.05:
                                    print(f"[Daemon] {sym} BUY — ${price:.2f} above entry (${entry_high:.2f}), skipped")
                                    continue
                                # Tighten entry zone to real-time price (±0.3%)
                                signal = dict(signal)
                                signal["entry_low"] = round(price * 0.997, 2)
                                signal["entry_high"] = round(price * 1.003, 2)
                        report = format_signal_report(signal)
                        await handler.send_message(report)
                        print(f"[Daemon] Signal fired: {sym} {signal.get('verdict')}")
                    else:
                        verdict = signal.get("verdict", "None") if signal else "None"
                        print(f"[Daemon] {sym} skipped ({verdict})")
                except Exception as e:
                    print(f"[Daemon] {sym} pipeline error: {e}")

            print(f"[Daemon] US scan complete: {scan_name}")
            await self._run_news_scan(us_symbols, "us")
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

            from telegram.handler import TelegramHandler
            from telegram.formatter import format_signal_report
            handler = TelegramHandler()

            for sym in crypto_symbols:
                try:
                    signal = await asyncio.to_thread(run_pipeline, sym, "crypto", "swing")
                    if signal and signal.get("verdict") != "HOLD" and signal.get("gate_passed"):
                        if signal.get("verdict") == "BUY":
                            price = await asyncio.to_thread(_get_current_price, sym, "crypto")
                            if price:
                                entry_high = signal.get("entry_high")
                                if entry_high and price > entry_high * 1.05:
                                    print(f"[Daemon] {sym} BUY — ${price:.2f} above entry (${entry_high:.2f}), skipped")
                                    continue
                                # Tighten entry zone to real-time price (±0.5% for crypto volatility)
                                signal = dict(signal)
                                signal["entry_low"] = round(price * 0.995, 2)
                                signal["entry_high"] = round(price * 1.005, 2)
                        report = format_signal_report(signal)
                        await handler.send_message(report)
                        print(f"[Daemon] Signal fired: {sym} {signal.get('verdict')}")
                    else:
                        verdict = signal.get("verdict", "None") if signal else "None"
                        print(f"[Daemon] {sym} skipped ({verdict})")
                except Exception as e:
                    print(f"[Daemon] {sym} pipeline error: {e}")

            print(f"[Daemon] Crypto scan complete: {len(crypto_symbols)} symbols")
            await self._run_news_scan(crypto_symbols, "crypto")
        except ImportError as e:
            print(f"[Daemon] Engine not available (crypto scan skipped): {e}")
        except Exception as e:
            print(f"[Daemon] Crypto scan error: {e}")

    async def _run_position_scan(self, market_filter: str = "all"):
        try:
            from db.store import get_open_positions, close_position
            positions = await asyncio.to_thread(get_open_positions)

            if market_filter != "all":
                positions = [p for p in positions if p.get("market") == market_filter]

            if not positions:
                return

            from telegram.handler import TelegramHandler
            from telegram.formatter import format_sl_alert
            handler = TelegramHandler()

            for pos in positions:
                sym = pos["symbol"]
                market = pos.get("market", "us")
                sl = pos.get("stop_loss")
                tp = pos.get("take_profit")

                if not sl and not tp:
                    continue

                price = await asyncio.to_thread(_get_current_price, sym, market)
                if price is None:
                    continue

                if sl:
                    pct_from_sl = (price - sl) / sl * 100
                    if price <= sl:
                        await asyncio.to_thread(close_position, sym, "sl_hit")
                        await handler.send_message(format_sl_alert(pos, price, 0, hit=True))
                        print(f"[Daemon] SL hit: {sym} @ ${price:.2f}")
                        continue
                    elif pct_from_sl <= 2.0:
                        await handler.send_message(format_sl_alert(pos, price, pct_from_sl, hit=False))
                        print(f"[Daemon] SL warning: {sym} {pct_from_sl:.1f}% from SL")

                if tp and price >= tp:
                    await asyncio.to_thread(close_position, sym, "tp_hit")
                    pct_gain = (price - pos["entry_price"]) / pos["entry_price"] * 100
                    await handler.send_message(
                        f"🎯 <b>TARGET REACHED: {sym}</b>\n"
                        f"Price: ${price:.2f}  →  Target: ${tp:.2f}\n"
                        f"Gain: +{pct_gain:.1f}% from entry ${pos['entry_price']:.2f}\n"
                        f"Consider taking profits."
                    )
                    print(f"[Daemon] TP hit: {sym} @ ${price:.2f}")

        except Exception as e:
            print(f"[Daemon] Position scan error: {e}")

    async def _run_news_scan(self, symbols: list, market: str):
        if not symbols:
            return
        try:
            from analysis.news import fetch_news
            from telegram.handler import TelegramHandler
            from telegram.formatter import format_news_alert
            handler = TelegramHandler()

            for sym in symbols:
                source = "cryptopanic" if market == "crypto" else "yahoo"
                try:
                    articles = await asyncio.to_thread(fetch_news, sym, source)
                    for article in articles[:3]:
                        title = article.get("title", "").strip()
                        if not title:
                            continue
                        key = hashlib.md5(f"{sym}:{title}".encode()).hexdigest()
                        if key in self._seen_news:
                            continue
                        self._seen_news.add(key)
                        url = article.get("url", "")
                        await handler.send_message(format_news_alert(sym, title, url))
                        print(f"[Daemon] News alert: {sym} — {title[:60]}")
                        break  # one alert per symbol per scan
                except Exception as e:
                    print(f"[Daemon] News {sym}: {e}")
        except Exception as e:
            print(f"[Daemon] News scan error: {e}")

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
