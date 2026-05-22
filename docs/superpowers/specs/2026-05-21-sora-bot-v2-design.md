# Sora Bot v2 — Design Spec

**Date:** 2026-05-21  
**Status:** Approved  
**Branch:** `feat/sora-bot-v2`
**Reference:** `docs/noor_bot_arch.json` (machine-readable, implementation-ready)

---

## Context

Current codebase is a 10,000+ line Flask app with 18 React pages, paper trading, Stripe, and 22 DB tables — built for multi-user monetization. The actual value is the signal pipeline: 5 technical strategies, 7-dimension confidence scoring, regime detection. Everything else is overhead.

This spec redesigns the product from scratch as a personal-use, Telegram-only AI signal agent. No UI. No trading execution. Pure signal + entry/exit zone reports with reasoning grounded in the user's own strategy.

---

## What It Is

A standalone Python bot (`python bot.py`) that:
- Scans US stocks + crypto on a schedule and delivers signals to Telegram
- Answers on-demand analysis commands (`/analyze AAPL -full`)
- Maintains a Karpathy-style LLM wiki of the user's strategy, trading psychology, and signal history
- Self-improves weekly via an autoresearch loop (evaluates signal accuracy, updates strategy weights)
- Learns the user's behavioral patterns from feedback commands

---

## Section 1 — Structure

**Entry point:** `python bot.py` — asyncio.gather runs Telegram bot + background scheduler in one process. No Flask. No web server. No auth.

```
bot.py
telegram/     handler.py · formatter.py · chart.py
engine/       orchestrator.py · strategies.py · confidence.py · regime.py · filters.py
data/         us_feed.py (Alpaca) · crypto_feed.py (CoinGecko)
analysis/     news.py · sentiment.py · fundamental.py
llm/          client.py (OpenRouter) · analyst.py · reporter.py
memory/       wiki.py · profile.py · feedback.py · learner.py
scheduler/    daemon.py
db/           store.py
knowledge/    SCHEMA.md (user writes once) · wiki/ · raw/
```

**DB — 6 tables only:** `watchlist`, `signals`, `signal_outcomes`, `user_feedback`, `user_profile`, `agent_lessons`

**Required env vars:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OPENROUTER_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`

---

## Section 2 — Knowledge Base

Pattern: **Karpathy LLM Wiki** + **Autoresearch self-improvement loop**

User dumps raw thoughts anywhere. LLM distills into wiki. User never manually maintains files.

**Wiki structure (`knowledge/wiki/`):**
- `strategy.md` — distilled trading rules (LLM-maintained)
- `patterns.md` — detected behavioral patterns
- `lessons.md` — what worked, what didn't, why
- `regime.md` — user performance by market condition
- `symbols/SYMBOL.md` — per-symbol knowledge (one per watchlist item)

**Three wiki operations:**
- **INGEST** — any `/note`, `/think`, `/trade`, `/strategy add` triggers LLM to update 3–5 relevant wiki pages
- **QUERY** — every `/analyze` loads `strategy.md + symbols/SYMBOL.md + patterns.md` as LLM context
- **LINT** — weekly + `/wiki lint`: health-check for contradictions, stale claims, orphan pages

**User input channels:**
```
/note "text"                    free-form thought
/note -symbol AAPL "text"       symbol-specific annotation
/think AAPL "text"              pre-analysis thesis, injected into next /analyze
/strategy add "rule"            append explicit rule
/trade AAPL took                signal taken (replaces /did)
/trade AAPL skip "reason"       signal skipped
/trade AAPL partial "note"      partial position
```

**Autoresearch loop (Sunday 8pm):**
1. Evaluate last week's signals vs actual price outcomes (T+3/7/14)
2. Compare — which strategies over/underperformed by regime?
3. Update confidence weights in `lessons.md`
4. Backtest updated weights on last 30 days
5. Keep if accuracy improves, revert if worse
6. Send weekly digest to Telegram

---

## Section 3 — Commands + Report Format

**Full command set:**
```
/analyze SYMBOL [-full] [-swing] [-long]
/watchlist -add SYMBOL | -remove SYMBOL | -ls
/trade SYMBOL took | skip "reason" | partial "note"
/note "text" | /note -symbol SYMBOL "text"
/think SYMBOL "text"
/strategy add "rule"
/wiki SYMBOL | strategy | patterns | lint
/reasoning SYMBOL       full technical breakdown
/backtest SYMBOL 6m     strategy historical performance
/catalyst SYMBOL        earnings, events, insider activity
/sentiment SYMBOL       news + Reddit detail
/why SYMBOL             entry zone rationale
/regime [SYMBOL]
/history SYMBOL 7d
/profile
/scan [-quick]
/status | /help
```

**Standard report (swing):**
```
━━━━━━━━━━━━━━━━━━━━━━━
📊 AAPL  ·  BUY SIGNAL
━━━━━━━━━━━━━━━━━━━━━━━
Confidence  78 / 100  [HIGH]
Strategy    BollingerSqueeze
Regime      Trending (Bullish) · ADX 31

📍 ENTRY ZONE    $183.50 – $185.00
   Anchor: SMA50 at $182.80, VWAP at $183.10

🎯 EXIT TARGET   $194.50  (+5.4%)
   Anchor: Aug-24 resistance cluster, Fib 161.8%

🛑 STOP LOSS     $179.00  (-2.5%)
   Anchor: 1.5× ATR below entry

⚖️  RISK / REWARD   1 : 2.2
⏱  Timeframe        Swing (5–12 days)

CONFIDENCE BREAKDOWN
  Trend Strength      ████████░░  82%
  Signal Alignment    ███████░░░  74%
  Volatility Quality  ████████░░  80%
  Volume Confirm      █████████░  88%
  Regime Fit          ███████░░░  72%
  Historical Perf     ██████░░░░  64%

Your rules: ✓ all passed
[chart PNG]
```

**Long-term report:** same format + fundamentals line (revenue growth, P/E, insider activity). Stop = 2×ATR, wider entry zone anchored to SMA200.

**Drill-downs on demand:** `/reasoning`, `/backtest`, `/catalyst`, `/sentiment`, `/why`

---

## Section 4 — Data Strategy

| Market | Feed | Schedule | Notes |
|---|---|---|---|
| US Equities | Alpaca daily bars | 9:30am / 12pm / 3:30pm EST | yfinance fallback on 429 |
| Crypto | CoinGecko OHLC (free, no key) | Every 4 hours, 24/7 | BTC dominance for regime |
| News (US) | Yahoo Finance RSS + SEC EDGAR | Per-request, cached 2h | Free, no key |
| News (Crypto) | CryptoPanic RSS | Per-request, cached 2h | Free, no key |
| Fundamentals | FMP free tier | Weekly refresh | P/E, revenue growth, insider delta |
| Sentiment | Reddit API | Per `/sentiment` command | Free |

Crypto meme filter: auto-reject if market cap < $5B or coin age < 2 years.

---

## Section 5 — Agents

4 agents. All via OpenRouter.

| Agent | Model | Role | LLM Calls |
|---|---|---|---|
| BullAgent | llama-3.1-8b (free) | Strongest bullish case | 1 |
| BearAgent | llama-3.1-8b (free) | Stress-test bull thesis | 1 |
| AnalystAgent | deepseek-v3 (free) | Synthesize + apply user wiki | 1 |
| ReviewAgent | deepseek-v3 (free) | Weekly autoresearch loop | weekly |

**`/analyze -full`:** BullAgent → BearAgent → AnalystAgent = 3 LLM calls, ~60–90s  
**`/analyze` (quick):** AnalystAgent only = 1 LLM call, ~20–30s  
**`/scan -quick`:** zero LLM calls, ~3s/symbol

---

## Section 6 — Backtesting

Walk-forward simulation on Alpaca historical bars (up to 5 years, free). Indicators computed on `bars[0:i]` only — no lookahead. All 5 strategies tested per symbol. Entry at next bar open after signal. Exit on stop (1.5×ATR), target (3×ATR), or max hold exceeded.

Output: win rate, trade count, avg return, max drawdown per strategy. Cached 7 days. Result feeds `AnalystAgent` context and populates confidence dimension 6 (Historical Perf) with real data.

---

## Section 7 — LLM Caching + Rate Limits

OpenRouter free tier: ~10 RPM. Naive 30-symbol scan = 90 LLM calls. Solution: 3-layer cache reduces to ~5 actual calls per scan.

| Layer | Key | TTL | What's Cached |
|---|---|---|---|
| Indicators | symbol + bar date | Until new bar | RSI, EMA, ATR, etc. |
| LLM response | sha256(symbol + indicators + regime + headlines) | 4 hours | Full signal output |
| News | symbol + source | 2 hours | Fetched + summarized news |

Async queue: `asyncio.Queue` + worker pool of 3. Token bucket rate limiter at 8 calls/min. Exponential backoff on 429 (2s→4s→8s, 3 retries max). Telegram shows "Scanning 28 symbols..." then results stream in as ready.

---

## Section 8 — Migration

**Branch:** `feat/sora-bot-v2`

**Port unchanged:** `core/strategies.py`, `core/confidence.py`

**Port with adaptation:** `pipeline/orchestrator.py` (multi-market dispatch), `core/regime.py` (crypto regime), `core/trade_filters.py` (disable earnings for crypto), `pipeline/daemon.py` (simplified + crypto schedule), `core/llm_client.py` (OpenRouter adapter)

**Delete after v2 verified:** `ui/`, `run.py`, `core/paper_trader.py`, `core/analytics.py`, `core/coach.py`, `payment/`, `compliance/`

**New:** all files in `telegram/`, `data/`, `analysis/`, `llm/`, `memory/`, `knowledge/`, `db/store.py`, `bot.py`

---

## Verification

```bash
# Bot starts without error
python bot.py

# Telegram commands respond correctly
/status           → system health green
/watchlist -add AAPL  → "AAPL added (us)"
/analyze AAPL     → signal card + chart PNG in ~30s
/analyze AAPL -full   → full report in ~90s
/scan -quick      → scores for all watchlist symbols in <30s
/backtest AAPL 6m → strategy table with real win rates
/trade AAPL took  → "Logged. Wiki updated."
/wiki strategy    → shows distilled strategy.md
/profile          → shows user trading profile

# Weekly loop runs without error (test manually)
python -c "from memory.learner import ReviewAgent; ReviewAgent().run_sync()"
```
