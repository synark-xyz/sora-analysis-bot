import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

_OFFSET_FILE = Path(__file__).parent.parent / ".tg_offset"

try:
    import httpx
except ImportError:
    httpx = None

from log import get_logger

log = get_logger("telegram.handler", "TELEGRAM")

from telegram.formatter import (
    format_signal_report,
    format_watchlist,
    format_status,
    format_regime,
    format_help,
    format_backtest,
    format_history,
    format_profile,
)

try:
    from db.store import (
        get_watchlist,
        add_watchlist_symbol,
        remove_watchlist_symbol,
        save_signal,
        get_signals,
        save_feedback,
        get_profile,
        save_profile,
        save_lesson,
        get_lessons,
    )
except ImportError:
    get_watchlist = lambda: []
    add_watchlist_symbol = lambda s, m="us": {}
    remove_watchlist_symbol = lambda s: False
    save_signal = lambda d: 0
    get_signals = lambda d=7, l=50: []
    save_feedback = lambda s, a, r=None, e=None: 0
    get_profile = lambda: {}
    save_profile = lambda p: None
    save_lesson = lambda lt, s, p, ci=0: 0
    get_lessons = lambda l=20: []

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


class TelegramHandler:
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.running = True
        self._poll_timeout = 30
        self.http_client = None

    async def _ensure_client(self):
        if self.http_client is None and httpx is not None:
            self.http_client = httpx.AsyncClient(timeout=35.0)

    async def send_message(self, text, parse_mode="HTML", chat_id=None):
        if httpx is None:
            return
        await self._ensure_client()
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id or self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            t0 = time.monotonic()
            r = await self.http_client.post(url, json=payload)
            elapsed = time.monotonic() - t0
            data = r.json()
            if data.get("ok"):
                log.http("sendMessage OK  %.1fs", elapsed)
            else:
                log.http("sendMessage FAIL  %.1fs  %s", elapsed, data.get("description", ""))
            return data
        except Exception as e:
            return None

    async def send_photo(self, photo_bytes, caption="", chat_id=None):
        if httpx is None:
            return
        await self._ensure_client()
        url = f"{self.base_url}/sendPhoto"
        files = {"photo": ("chart.png", photo_bytes, "image/png")}
        data = {"chat_id": chat_id or self.chat_id, "caption": caption, "parse_mode": "HTML"}
        try:
            r = await self.http_client.post(url, data=data, files=files)
            return r.json()
        except Exception:
            return None

    async def send_action(self, action="typing", chat_id=None):
        if httpx is None:
            return
        await self._ensure_client()
        url = f"{self.base_url}/sendChatAction"
        payload = {"chat_id": chat_id or self.chat_id, "action": action}
        try:
            await self.http_client.post(url, json=payload)
        except Exception:
            pass

    async def poll_updates(self, offset=0):
        if httpx is None:
            await asyncio.sleep(10)
            return offset

        await self._ensure_client()
        url = f"{self.base_url}/getUpdates"
        params = {
            "offset": offset,
            "timeout": self._poll_timeout,
            "allowed_updates": ["message"],
        }
        try:
            t0 = time.monotonic()
            r = await self.http_client.get(url, params=params)
            elapsed = time.monotonic() - t0
            data = r.json()
            updates = len(data.get("result", []))
            if updates:
                log.http("getUpdates OK  %d updates  %.1fs", updates, elapsed)
        except Exception:
            return offset

        if not data.get("ok"):
            return offset

        for update in data.get("result", []):
            new_offset = update["update_id"] + 1
            if new_offset > offset:
                offset = new_offset
            await self._handle_update(update)

        return offset

    async def _handle_update(self, update):
        try:
            message = update.get("message")
            if not message:
                return
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "").strip()
            if not text:
                return

            if text.startswith("/"):
                parts = text.split(maxsplit=1)
                cmd = parts[0].split("@")[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                await self._route_command(cmd, args, chat_id)
        except Exception as e:
            log.error("unhandled error in update %s: %s", update.get("update_id"), e)

    async def _route_command(self, cmd, args, chat_id):
        await self.send_action(chat_id=chat_id)

        cmd_map = {
            "/start": self._handle_help,
            "/help": self._handle_help,
            "/analyze": self._handle_analyze,
            "/watchlist": self._handle_watchlist,
            "/trade": self._handle_trade,
            "/note": self._handle_note,
            "/strategy": self._handle_strategy,
            "/wiki": self._handle_wiki,
            "/status": self._handle_status,
            "/regime": self._handle_regime,
            "/scan": self._handle_scan,
            "/backtest": self._handle_backtest,
            "/history": self._handle_history,
            "/profile": self._handle_profile,
            "/reasoning": self._handle_reasoning,
            "/catalyst": self._handle_catalyst,
            "/sentiment": self._handle_sentiment,
            "/why": self._handle_why,
            "/think": self._handle_think,
            "/clear": self._handle_clear,
            "/cancel": self._handle_clear,
        }

        handler = cmd_map.get(cmd)
        if handler:
            await handler(args, chat_id)
        else:
            await self.send_message(
                f"Unknown command: {cmd}\n/help for available commands",
                chat_id=chat_id,
            )

    async def _handle_help(self, args, chat_id):
        await self.send_message(format_help(), chat_id=chat_id)

    async def _handle_analyze(self, args, chat_id):
        if not args:
            await self.send_message(
                "Usage: /analyze SYMBOL [-full] [-swing] [-long]",
                chat_id=chat_id,
            )
            return

        parts = args.split()
        symbol = parts[0].upper()
        flags = [p.lower() for p in parts[1:]]
        is_full = "-full" in flags
        is_swing = "-swing" in flags
        is_long = "-long" in flags

        await self.send_message(f"Analyzing {symbol}...", chat_id=chat_id)

        try:
            from engine.orchestrator import run_analysis

            signal = await run_analysis(
                symbol=symbol,
                full=is_full,
                swing=is_swing,
                long_term=is_long,
            )
        except ImportError:
            signal = self._mock_signal(symbol)
        except Exception as e:
            log.error("run_analysis failed for %s: %s", symbol, e)
            await self.send_message(f"Analysis failed for {symbol}: {e}", chat_id=chat_id)
            return

        report = format_signal_report(signal)
        await self.send_message(report, chat_id=chat_id)

        if signal.get("verdict") != "HOLD":
            try:
                save_signal(signal)
            except Exception:
                pass

    async def _handle_watchlist(self, args, chat_id):
        if not args:
            items = await asyncio.to_thread(get_watchlist)
            await self.send_message(format_watchlist(items), chat_id=chat_id)
            return

        parts = args.split()
        flag = parts[0].lower()

        if flag == "-ls" or flag == "--ls" or flag == "ls":
            items = await asyncio.to_thread(get_watchlist)
            await self.send_message(format_watchlist(items), chat_id=chat_id)
        elif flag in ("-add", "--add", "add"):
            if len(parts) < 2:
                await self.send_message("Usage: /watchlist -add SYMBOL", chat_id=chat_id)
                return
            symbol = parts[1].upper()
            market = self._detect_market(symbol)
            result = await asyncio.to_thread(add_watchlist_symbol, symbol, market)
            await self.send_message(
                f"Added {symbol} ({market}) to watchlist",
                chat_id=chat_id,
            )
        elif flag in ("-remove", "--remove", "remove", "-rm", "--rm"):
            if len(parts) < 2:
                await self.send_message("Usage: /watchlist -remove SYMBOL", chat_id=chat_id)
                return
            symbol = parts[1].upper()
            ok = await asyncio.to_thread(remove_watchlist_symbol, symbol)
            if ok:
                await self.send_message(f"Removed {symbol} from watchlist", chat_id=chat_id)
            else:
                await self.send_message(f"{symbol} not in watchlist", chat_id=chat_id)
        else:
            await self.send_message(
                "Usage: /watchlist -add SYMBOL | -remove SYMBOL | -ls",
                chat_id=chat_id,
            )

    async def _handle_trade(self, args, chat_id):
        if not args:
            await self.send_message(
                "Usage: /trade SYMBOL took|skip|partial [reason]",
                chat_id=chat_id,
            )
            return
        parts = args.split(maxsplit=2)
        symbol = parts[0].upper()
        if len(parts) < 2:
            await self.send_message("Specify: took, skip, or partial", chat_id=chat_id)
            return
        action = parts[1].lower()
        if action not in ("took", "skip", "partial"):
            await self.send_message("Action must be: took, skip, or partial", chat_id=chat_id)
            return
        reason = parts[2] if len(parts) > 2 else None

        await asyncio.to_thread(save_feedback, symbol, action, reason)
        await self.send_message(
            f"Logged: {symbol} {action}. Wiki will be updated.",
            chat_id=chat_id,
        )

        await asyncio.to_thread(
            save_lesson, "feedback", symbol,
            f"User {action} on {symbol}: {reason or 'no reason given'}",
        )

    async def _handle_note(self, args, chat_id):
        if not args:
            await self.send_message("Usage: /note \"text\" or /note -symbol SYMBOL \"text\"",
                                    chat_id=chat_id)
            return

        symbol = None
        text = args

        m = re.match(r"-symbol\s+(\S+)\s+\"(.+)\"", args)
        if m:
            symbol = m.group(1).upper()
            text = m.group(2)
        else:
            m = re.match(r"\"(.+)\"", args)
            if m:
                text = m.group(1)

        note_type = f"note:{symbol}" if symbol else "note"
        await asyncio.to_thread(
            save_lesson, "note", symbol or "GENERAL", text,
        )
        await self.send_message(
            f"Noted{' for ' + symbol if symbol else ''}. Wiki updated.",
            chat_id=chat_id,
        )

    async def _handle_strategy(self, args, chat_id):
        if not args:
            await self.send_message(
                "Usage: /strategy add \"rule\"",
                chat_id=chat_id,
            )
            return
        if args.startswith("add "):
            rule = args[4:].strip().strip('"')
            await asyncio.to_thread(save_lesson, "strategy_rule", "GENERAL", rule)
            await self.send_message(f"Strategy rule added: {rule}", chat_id=chat_id)
        else:
            await self.send_message("Usage: /strategy add \"rule\"", chat_id=chat_id)

    async def _handle_wiki(self, args, chat_id):
        topic = args.strip().lower() if args else "strategy"

        try:
            from memory.wiki import get_wiki_page
            content = await get_wiki_page(topic)
        except ImportError:
            lessons = await asyncio.to_thread(get_lessons, 10)
            lines = [f"<b>Wiki: {topic}</b>", ""]
            for l in lessons:
                lines.append(f"  [{l['lesson_type']}] {l['symbol']}: {l['pattern'][:100]}")
            content = "\n".join(lines)

        await self.send_message(content[:4000], chat_id=chat_id)

    async def _handle_status(self, args, chat_id):
        try:
            watchlist_items = await asyncio.to_thread(get_watchlist)
            recent_signals = await asyncio.to_thread(get_signals, 7, 10)
            lessons = await asyncio.to_thread(get_lessons, 5)
        except Exception:
            watchlist_items = []
            recent_signals = []
            lessons = []

        llm_cache_count = 0
        try:
            conn = __import__("sqlite3").connect(os.environ.get("DB_PATH", "sora.db"))
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM llm_cache")
            llm_cache_count = c.fetchone()[0]
            conn.close()
        except Exception:
            pass

        status = {
            "uptime": "N/A",
            "last_scan": "N/A",
            "watchlist_count": len(watchlist_items),
            "signals_7d": len(recent_signals),
            "llm_cache_count": llm_cache_count,
            "llm_status": "OK" if os.environ.get("OPENROUTER_API_KEY") else "no key",
            "alpaca_status": "OK" if os.environ.get("ALPACA_API_KEY") else "no key",
            "errors": [],
        }
        if not os.environ.get("OPENROUTER_API_KEY"):
            status["errors"].append("OPENROUTER_API_KEY not set")
        if not os.environ.get("ALPACA_API_KEY"):
            status["errors"].append("ALPACA_API_KEY not set")

        await self.send_message(format_status(status), chat_id=chat_id)

    async def _handle_regime(self, args, chat_id):
        try:
            from engine.regime import get_regime
            regime = await get_regime()
        except ImportError:
            regime = {
                "us": {"regime": "N/A", "trend": "N/A", "adx": "N/A"},
                "crypto": {"regime": "N/A", "btc_change": 0},
            }
        await self.send_message(format_regime(regime), chat_id=chat_id)

    async def _handle_scan(self, args, chat_id):
        quick = args.strip().lower() in ("-quick", "--quick", "quick")

        items = await asyncio.to_thread(get_watchlist)
        if not items:
            await self.send_message("Watchlist is empty. Add symbols first.", chat_id=chat_id)
            return

        symbols = [i["symbol"] for i in items]
        await self.send_message(
            f"Scanning {len(symbols)} symbols: {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}",
            chat_id=chat_id,
        )

        if quick:
            for sym in symbols:
                try:
                    from engine.orchestrator import quick_score
                    score = await asyncio.to_thread(quick_score, sym)
                except Exception:
                    score = {"symbol": sym, "score": 50}
                reasons = score.get("reasons")
                msg = f"<b>{sym}</b>: {score.get('score', 'N/A')}/100"
                if reasons:
                    msg += "\n  " + " · ".join(reasons)
                await self.send_message(msg, chat_id=chat_id)
                await asyncio.sleep(0.5)
        else:
            for sym in symbols:
                await self.send_message(f"Analyzing {sym}...", chat_id=chat_id)
                try:
                    from engine.orchestrator import run_analysis
                    signal = await run_analysis(symbol=sym)
                except Exception as e:
                    await self.send_message(
                        f"<b>{sym}</b> analysis error: {e}",
                        chat_id=chat_id,
                    )
                    continue

                try:
                    report = format_signal_report(signal)
                    await self.send_message(report, chat_id=chat_id)
                except Exception as e:
                    await self.send_message(
                        f"<b>{sym}</b> report error: {e}",
                        chat_id=chat_id,
                    )

                if signal.get("verdict") != "HOLD":
                    try:
                        save_signal(signal)
                    except Exception:
                        pass

                await asyncio.sleep(1)

        await self.send_message("Scan complete.", chat_id=chat_id)

    async def _handle_backtest(self, args, chat_id):
        if not args:
            await self.send_message("Usage: /backtest SYMBOL 6m", chat_id=chat_id)
            return
        parts = args.split()
        symbol = parts[0].upper()
        period = parts[1] if len(parts) > 1 else "6m"

        try:
            from engine.orchestrator import run_backtest
            results = await run_backtest(symbol, period)
        except ImportError:
            results = self._mock_backtest(symbol)

        await self.send_message(format_backtest(results, symbol), chat_id=chat_id)

    async def _handle_history(self, args, chat_id):
        if not args:
            await self.send_message("Usage: /history SYMBOL 7d", chat_id=chat_id)
            return
        parts = args.split()
        symbol = parts[0].upper()
        days_str = parts[1] if len(parts) > 1 else "7d"
        days = int(re.sub(r"\D", "", days_str)) if re.search(r"\d", days_str) else 7

        signals = await asyncio.to_thread(get_signals, days, 30)
        sym_signals = [s for s in signals if s["symbol"] == symbol]
        await self.send_message(format_history(sym_signals), chat_id=chat_id)

    async def _handle_profile(self, args, chat_id):
        profile = await asyncio.to_thread(get_profile)
        await self.send_message(format_profile(profile), chat_id=chat_id)

    async def _handle_reasoning(self, args, chat_id):
        if not args:
            await self.send_message("Usage: /reasoning SYMBOL", chat_id=chat_id)
            return
        symbol = args.strip().upper()
        await self.send_message(
            f"<b>Technical Breakdown: {symbol}</b>\n\nReasoning requires LLM module. Coming soon.",
            chat_id=chat_id,
        )

    async def _handle_catalyst(self, args, chat_id):
        if not args:
            await self.send_message("Usage: /catalyst SYMBOL", chat_id=chat_id)
            return
        symbol = args.strip().upper()
        await self.send_message(
            f"<b>Catalyst: {symbol}</b>\n\nCatalyst analysis requires news module. Coming soon.",
            chat_id=chat_id,
        )

    async def _handle_sentiment(self, args, chat_id):
        if not args:
            await self.send_message("Usage: /sentiment SYMBOL", chat_id=chat_id)
            return
        symbol = args.strip().upper()
        await self.send_message(
            f"<b>Sentiment: {symbol}</b>\n\nSentiment analysis requires sentiment module. Coming soon.",
            chat_id=chat_id,
        )

    async def _handle_why(self, args, chat_id):
        if not args:
            await self.send_message("Usage: /why SYMBOL", chat_id=chat_id)
            return
        symbol = args.strip().upper()
        await self.send_message(
            f"<b>Entry Rationale: {symbol}</b>\n\nDetailed rationale requires analysis module. Coming soon.",
            chat_id=chat_id,
        )

    async def _handle_think(self, args, chat_id):
        if not args:
            await self.send_message("Usage: /think SYMBOL \"thesis\"", chat_id=chat_id)
            return
        m = re.match(r"(\S+)\s+\"(.+)\"", args)
        if m:
            symbol = m.group(1).upper()
            thesis = m.group(2)
            await asyncio.to_thread(save_lesson, "thesis", symbol, thesis)
            await self.send_message(
                f"Thesis saved for {symbol}. Will be included in next analysis.",
                chat_id=chat_id,
            )
        else:
            await self.send_message(
                "Usage: /think SYMBOL \"your thesis here\"",
                chat_id=chat_id,
            )

    async def _handle_clear(self, args, chat_id):
        if self.http_client:
            url = f"{self.base_url}/getUpdates"
            await self.http_client.get(url, params={"offset": -1})
        await self.send_message(
            "Cleared all pending updates.", chat_id=chat_id
        )

    def _detect_market(self, symbol):
        known_crypto = {"BTC", "ETH", "SOL", "BNB", "AVAX", "LINK", "DOT", "MATIC", "ADA", "XRP", "DOGE"}
        return "crypto" if symbol in known_crypto else "us"

    def _mock_signal(self, symbol):
        return {
            "symbol": symbol,
            "market": self._detect_market(symbol),
            "verdict": "HOLD",
            "confidence": 50,
            "entry_low": None,
            "entry_high": None,
            "exit_target": None,
            "stop_loss": None,
            "rr_ratio": None,
            "reason": "Engine not available. Running in mock mode.",
            "strategy": "N/A",
            "regime": "N/A",
            "timeframe": "N/A",
        }

    def _mock_bars(self):
        return []

    def _mock_backtest(self, symbol):
        return [
            {
                "strategy": "EMARSIVolume",
                "win_rate": 58,
                "trades": 24,
                "wins": 14,
                "avg_return": 1.2,
                "max_drawdown": -3.5,
            },
            {
                "strategy": "SupertrendMACD",
                "win_rate": 62,
                "trades": 18,
                "wins": 11,
                "avg_return": 1.8,
                "max_drawdown": -2.8,
            },
            {
                "strategy": "BollingerSqueeze",
                "win_rate": 55,
                "trades": 30,
                "wins": 16,
                "avg_return": 1.5,
                "max_drawdown": -4.1,
            },
            {
                "strategy": "RSIMeanReversion",
                "win_rate": 48,
                "trades": 22,
                "wins": 10,
                "avg_return": 0.9,
                "max_drawdown": -3.2,
            },
            {
                "strategy": "VWAPMomentum",
                "win_rate": 60,
                "trades": 20,
                "wins": 12,
                "avg_return": 2.1,
                "max_drawdown": -3.0,
            },
        ]

    async def run(self):
        if httpx is None:
            return

        await self._ensure_client()
        try:
            offset = int(_OFFSET_FILE.read_text().strip())
        except Exception:
            offset = 0

        while self.running:
            offset = await self.poll_updates(offset)
            _OFFSET_FILE.write_text(str(offset))
            await asyncio.sleep(1)

        if self.http_client:
            await self.http_client.aclose()
