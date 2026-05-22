# CLAUDE.md

## Project: Sora Telegram Bot (v2)

Personal-use Telegram-based AI trading signal agent. No UI, no trading execution. Provides entry/exit zone signals for US stocks + crypto with full reasoning.

## Entry Point

`python bot.py` — single asyncio process (Telegram bot + scheduler daemon)

## Architecture

```
bot.py                           entry point — asyncio runner
telegram/                        handler, formatter, chart (matplotlib candlestick PNG)
engine/                          5 strategies, confidence scoring, regime detection, filters
data/                            Alpaca (US equities) + CoinGecko (crypto)
analysis/                        News (Yahoo RSS + SEC EDGAR), sentiment (Reddit), fundamentals (FMP)
llm/                             OpenRouter client, analyst agents, signal reporter
memory/                          Karpathy-style LLM wiki, user profile, feedback, autoresearch loop
scheduler/                       Cron scan scheduler (US 3x/day, crypto 4x/day)
db/                              SQLite — 6 tables (watchlist, signals, outcomes, feedback, profile, lessons)
knowledge/                       LLM-maintained wiki (strategy, patterns, lessons, regime, per-symbol)
```

## Env Vars (Required)

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OPENROUTER_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`

## Common Commands

```bash
python bot.py                    # Start bot
pytest tests/ -v                 # Run all tests
python -c "from db.store import init_db; init_db()"  # Initialize DB
```

## Dependencies

python-telegram-bot, httpx, alpaca-py, pandas, yfinance, openai, matplotlib, mplfinance, apscheduler

## Migrated From

Original code in `sora-trading-bot` (commit: 15d0130fb0c6ec124095f2d4bd8427f50c07ccee), extracted as clean v2 project.
