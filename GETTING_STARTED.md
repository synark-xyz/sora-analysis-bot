# Getting Started: Sora Trading Bot v2

Personal-use Telegram-based AI trading signal agent for US equities and cryptocurrency. Provides entry/exit zone signals with full reasoning through a deterministic technical pipeline augmented by multi-agent LLM debate. No user interface, no trading execution -- signals only.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Configuration](#3-configuration)
4. [Database Setup](#4-database-setup)
5. [First Run](#5-first-run)
6. [Daily Operation](#6-daily-operation)
7. [Telegram Commands Reference](#7-telegram-commands-reference)
8. [Testing](#8-testing)
9. [Troubleshooting](#9-troubleshooting)
10. [VPS Deployment](#10-vps-deployment)
11. [Maintenance](#11-maintenance)

---

## 1. Prerequisites

### System Requirements

- **Python:** 3.11 or later (3.11+ tested, 3.10 minimum)
- **OS:** macOS, Linux, or Windows (VPS deployment instructions for Ubuntu 22.04)
- **RAM:** 256 MB minimum (512 MB recommended for VPS)
- **Storage:** 100 MB free for code, database, and knowledge files
- **Network:** Outbound HTTPS access to Telegram API, Alpaca API, OpenRouter API, Binance API, and optional third-party APIs

### Required Accounts and API Keys

| Service | Required For | How To Get | Cost |
|---------|-------------|------------|------|
| **Telegram Bot Token** | Essential | Message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, follow prompts | Free |
| **Telegram Chat ID** | Essential | The chat/group/channel where the bot delivers signals. Add the bot to the target chat, then visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` to find your `chat_id` | Free |
| **OpenRouter API Key** | Essential (LLM analysis) | Sign up at [openrouter.ai](https://openrouter.ai/keys), create a new key | Pay-per-use (cheap: ~$0.50-2/month for personal use) |
| **Alpaca API Key** | Required for US equities | Sign up at [alpaca.markets](https://alpaca.markets/), create a paper trading or live account, generate API keys from Dashboard | Free for paper trading |
| **Alpaca Secret Key** | Required for US equities | Same as above (paired with API key) | Free for paper trading |

### Optional API Keys

| Service | Used For | How To Get |
|---------|----------|------------|
| **FMP API Key** | Fundamentals (P/E, revenue growth, insider trading, institutional ownership, valuation metrics) | Sign up at [financialmodelingprep.com](https://financialmodelingprep.com/) |
| **Finnhub API Key** | Real-time US stock prices (used for entry zone tightening during automated scans) | Sign up at [finnhub.io](https://finnhub.io/), free tier available |
| **Gemini API Key** | Listed in template (not currently used in main pipeline) | Sign up at [makersuite.google.com](https://makersuite.google.com/) |

### Crypto-Specific Notes

Cryptocurrency data (OHLCV bars for BTC, ETH, SOL, BNB, AVAX, LINK, DOT, MATIC, ADA, XRP) comes from the **Binance public API** -- no API key required. Alpaca is not needed for crypto.

---

## 2. Installation

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd noor-telegram-bot
```

### Step 2: Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# or: .venv\Scripts\activate    # Windows
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

The `requirements.txt` installs:

| Package | Version | Purpose |
|---------|---------|---------|
| python-dotenv | >=1.0 | Load environment variables from `.env` |
| httpx | >=0.27 | Async HTTP client (Telegram API, OpenRouter) |
| python-telegram-bot | >=20.0 | Telegram bot framework (used for type hints; actual polling is raw httpx) |
| alpaca-py | >=0.15 | Alpaca Markets API client (US equities data) |
| pandas | >=2.2 | Data manipulation for indicator computation |
| yfinance | >=0.2 | Yahoo Finance data (earnings calendar, S&P 500 breadth) |
| requests | >=2.31 | Sync HTTP client (Binance API, Finnhub) |
| matplotlib | >=3.8 | Chart generation (technical charts) |
| mplfinance | >=0.12 | Candlestick chart plotting |
| apscheduler | >=3.10 | Scheduling (used for reference; actual scheduling is a custom asyncio loop) |
| pytz | (any) | Timezone support |
| openai | >=1.0 | OpenAI SDK (used for LLM client compatibility) |

**Test dependencies** (installed automatically from requirements.txt):
- pytest >=8.0
- pytest-asyncio >=0.23

### Step 4: Verify Installation

```bash
python -c "import httpx, pandas, alpaca_trade_api; print('All imports OK')"
```

---

## 3. Configuration

### Step 1: Create .env File

Copy the template:

```bash
cp .env.template .env
```

### Step 2: Fill in Your API Keys

Edit `.env` with your actual keys. The file is gitignored and will not be committed.

```ini
# Required - Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=-1001234567890

# Required - OpenRouter for LLM agent analysis
OPENROUTER_API_KEY=sk-or-v1-abcdef1234567890abcdef1234567890

# Required for US equities - Alpaca Markets
ALPACA_API_KEY=AKABCDEF1234567890
ALPACA_SECRET_KEY=abcdef1234567890abcdef1234567890

# Optional - Finnhub real-time prices (recommended for BUY scans)
FINNHUB_API_KEY=abc123def456

# Optional - FMP fundamentals and valuation
FMP_API_KEY=abc123def456

# Optional - Model selection
# DEFAULT_MODEL=openrouter/free
# FAST_MODEL=openrouter/free
# ANALYSIS_MODEL=openrouter/free

# Optional - Database path (defaults to sora.db in project root)
# DB_PATH=sora.db
```

### Environment Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | -- | Telegram bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Yes | -- | Target chat ID for signal delivery (can be a group, channel, or user chat) |
| `OPENROUTER_API_KEY` | Yes | -- | OpenRouter API key for LLM access |
| `ALPACA_API_KEY` | Yes* | -- | Alpaca Markets API key (required only if scanning US equities) |
| `ALPACA_SECRET_KEY` | Yes* | -- | Alpaca Markets secret key (required only if scanning US equities) |
| `FMP_API_KEY` | No | -- | Financial Modeling Prep key (fundamentals and valuation) |
| `FINNHUB_API_KEY` | No | -- | Finnhub API key (real-time US prices for entry zone tightening) |
| `DB_PATH` | No | `sora.db` | SQLite database file path |
| `DEFAULT_MODEL` | No | `openrouter/free` | Default LLM model for chat and general queries |
| `FAST_MODEL` | No | `openrouter/free` | Fast model for bull/bear agents |
| `ANALYSIS_MODEL` | No | `openrouter/free` | Analysis model for synthesis agent |
| `GEMINI_API_KEY` | No | -- | Gemini API key (listed in template, not currently used in main pipeline) |

*Required for US equities. Crypto works without Alpaca keys.

### How to Get Each API Key

**Telegram Bot Token:**
1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow the prompts
3. Copy the token (format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

**Telegram Chat ID:**
1. Add your bot to the target chat (group/channel) or start a private chat with it
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Send a message in the chat, then refresh the page
4. Look for `"chat":{"id":-1001234567890}` -- the `id` value is your `TELEGRAM_CHAT_ID`
5. Negative IDs indicate groups/channels; positive IDs are individual user chats

**OpenRouter API Key:**
1. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
2. Sign in (or create an account)
3. Click "Create Key"
4. Copy the key (starts with `sk-or-v1-`)

**Alpaca API Keys (Paper Trading):**
1. Go to [alpaca.markets](https://alpaca.markets/)
2. Sign up and verify your email
3. Navigate to Dashboard > Paper Trading > API Keys
4. Generate new keys and copy both the API Key ID and Secret Key

### Bot Behavior with Missing Keys

The bot degrades gracefully when optional keys are missing:
- **No Alpaca keys:** US equity scans will fail. Crypto works fine.
- **No OpenRouter key:** LLM-powered analysis, chat agent, and weekly reviews will be disabled. Basic technical signals (pipeline without LLM debate) still produce deterministic BUY/SELL/HOLD signals.
- **No FMP key:** Fundamentals and valuation sections in analysis will be empty.
- **No Finnhub key:** Real-time price checks during automated scans will be skipped (no BUY entry zone tightening).

---

## 4. Database Setup

### Initialize the Database

The bot uses SQLite -- no database server required. Run this once after configuring `.env`:

```bash
python -c "from db.store import init_db; init_db()"
```

This creates the database file at the path specified by `DB_PATH` (default: `sora.db` in the project root) and creates **7 tables**:

| Table | Purpose |
|-------|---------|
| `watchlist` | Symbols to scan (symbol, market, added_at) |
| `signals` | Generated signals (verdict, confidence, entry/exit zones, stop-loss) |
| `signal_outcomes` | Actual returns at 3d, 7d, 14d intervals |
| `user_feedback` | Trade actions (took/skip/partial with reasons) |
| `user_profile` | Trading profile (JSON blob extracted from wiki) |
| `agent_lessons` | LLM-learned lessons and patterns |
| `llm_cache` | LLM response cache (5-hour TTL) |
| `positions` | Open/closed positions with entry price, SL, TP |

### Re-initialization

Running `init_db()` again is safe -- it uses `CREATE TABLE IF NOT EXISTS` and will not overwrite existing data. To reset the database entirely, delete the file and re-run:

```bash
rm sora.db && python -c "from db.store import init_db; init_db()"
```

### Database File Location

The default location is `sora.db` in the project root directory. To use a different path, set the `DB_PATH` environment variable in `.env`. The `.gitignore` excludes `*.db` files so your data stays local.

---

## 5. First Run

### Start the Bot

```bash
python bot.py
```

### Expected Output

You should see something like this:

```
Sora Bot v2 starting...
[Daemon] Started
```

The bot launches two concurrent asyncio tasks:
1. **Telegram polling loop** -- listens for commands and messages via long-polling
2. **Scheduler daemon** -- checks time every 30 seconds and triggers scans at market-appropriate times

### Verify It Works

1. Open Telegram and go to the chat you configured as `TELEGRAM_CHAT_ID`
2. Send `/start` or `/help`
3. The bot should reply with the help text listing available commands
4. Send `/status` to see bot health, API key status, and watchlist count

### Common First-Run Issues

**Bot does not respond:**
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are correct in `.env`
- Ensure the bot is a member of the target chat (for groups/channels)
- Check the console output for error messages

**"OPENROUTER_API_KEY not set" status error:**
- Normal if you only want deterministic signals. If you want LLM features, add the key to `.env` and restart.

**Database errors:**
- Run `python -c "from db.store import init_db; init_db()"` to ensure tables exist.

### Adding Your First Symbol

Once the bot is running, add a symbol to scan:

```
/watchlist -add BTC
```

This adds Bitcoin to the crypto watchlist. Now you can manually trigger an analysis:

```
/analyze BTC
```

Or add a US stock:

```
/watchlist -add AAPL
```

### Stopping the Bot

Press `Ctrl+C` to stop. The bot handles shutdown gracefully -- it cancels both tasks and exits cleanly.

---

## 6. Daily Operation

### How the Bot Works

The bot is a **passive signal generator** -- it does not execute trades. It monitors your watchlist on a schedule and sends Telegram messages when it detects actionable signals.

### Automated Scan Schedule

All times are in **US Eastern Time (ET)**. The scheduler uses NYSE holiday awareness -- US scans do not run on weekends or market holidays.

| Scan | Schedule | Market | What Happens |
|------|----------|--------|-------------|
| **US Pre-market** | 8:30 AM ET on trading days | US equities | Runs the full pipeline on every US watchlist symbol. If a BUY signal passes the signal gate and real-time price is within 5% of the entry zone, the entry zone is tightened to +/-0.3% of current price and a report is sent. |
| **US Pre-close** | 3:00 PM ET on trading days | US equities | Same as pre-market scan. Catches end-of-day setups. |
| **Crypto** | Every 4 hours at :00 (midnight, 4am, 8am, 12pm, 4pm, 8pm ET) on trading days | Crypto | Runs the full pipeline on every crypto watchlist symbol. Entry zones tightened to +/-0.5% of current price for BUY signals. |
| **Position Scan (US)** | Every 30 minutes during market hours (9:30 AM - 4:00 PM ET) | US open positions | Checks stop-loss and take-profit levels against real-time prices. Sends alerts when price is within 2% of SL or when SL/TP is hit. |
| **Position Scan (Crypto)** | Every 2 hours at :30 past the hour | Crypto open positions | Same SL/TP monitoring for crypto positions. |
| **News Scan** | Immediately after each US or crypto market scan | Per market | Fetches recent news headlines for scanned symbols. Sends one alert per symbol per scan. |
| **Weekly Review** | Sunday 8:00 PM ET | All | Evaluates signal accuracy, updates lessons and patterns, identifies strategy over/underperformance. |

### Signal Pipeline (What Happens When a Symbol Is Scanned)

The pipeline that runs for each symbol has multiple quality gates:

1. **Fetch OHLCV bars** -- 90 days of daily data (Alpaca for US, Binance for crypto)
2. **Compute indicators** -- EMA, RSI, MACD, Bollinger Bands, Supertrend, VWAP, ADX, ATR, volume metrics
3. **Detect market regime** -- Classifies as BULL, BEAR, NEUTRAL, RANGING, or VOLATILE (using SPY for US, BTC for crypto as proxies)
4. **Select strategy** -- Tries all regime-compatible strategies and picks the best one
5. **Score confidence** -- 7-dimension deterministic scoring (0-100): trend strength, signal alignment, volatility quality, volume confirmation, regime fit, historical performance, drawdown state
6. **Validate confluence** -- Checks that technical factors agree (ADX, EMA, RSI, volume, regime). Alignment ratio must be >= 50%.
7. **Check signal gate** -- 8 hard rules including R:R >= 1.5:1, confidence floor, volume confirmation, news cooldown, stop-loss sanity
8. **LLM debate (optional)** -- If the pipeline is running in full analysis mode, the Bull Agent builds the bullish case, the Bear Agent stress-tests it, and the Analyst Agent synthesizes the final verdict
9. **Deliver report** -- If all gates pass, a formatted signal report is sent to Telegram

### Your Daily Workflow

1. **Morning check:** Check the chat for any pre-market signals sent around 8:30 AM ET
2. **Review signals:** Read the signal reports -- each includes entry zone, stop-loss, take-profit, R:R ratio, confidence score, and technical breakdown
3. **Log actions:** When you take or skip a trade, log it:
   ```
   /trade AAPL took "aligned with thesis, good R:R"
   ```
4. **Manage positions:** Log any positions you enter:
   ```
   /position -add AAPL 175.50 100 sl:168.00 tp:195.00
   ```
5. **Add notes:** Save observations or ideas:
   ```
   /note "AAPL showing bullish flag pattern on 4h"
   ```
6. **Evening check:** Review pre-close signals around 3:00 PM ET
7. **End of week:** Check the Sunday weekly review for strategy performance insights

### What the Bot Sends You

**Signal Report** (when a BUY/SELL signal passes all gates):
- Symbol and verdict (BUY/SELL/HOLD)
- Entry zone (low-high price range)
- Take-profit and stop-loss levels
- Risk/reward ratio
- Confidence score with 7-dimension breakdown
- Strategy that triggered
- Current market regime
- LLM summary (if full analysis mode)

**Position Alert** (during position scans):
- Stop-loss warning when price is within 2% of SL
- Stop-loss hit notification (position auto-closed in DB)
- Take-profit reached notification

**News Alert** (after market scans):
- Symbol and headline with URL
- One alert per symbol per scan cycle

---

## 7. Telegram Commands Reference

### Analysis Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/analyze SYMBOL` | Quick technical signal (deterministic pipeline, ~30s). Returns entry/exit zones, confidence, and strategy. | `/analyze AAPL` |
| `/analyze SYMBOL -full` | Deep multi-agent LLM report (~90s). Runs Bull/Bear debate + Analyst synthesis. | `/analyze AAPL -full` |
| `/analyze SYMBOL -mm` | Moomoo 5-step framework analysis (structured fundamental + technical + risk). | `/analyze AAPL -mm` |
| `/analyze SYMBOL -swing` | Force swing timeframe analysis (days-weeks). | `/analyze AAPL -swing` |
| `/analyze SYMBOL -long` | Force long-term timeframe analysis (weeks-months). | `/analyze BTC -long` |

### Watchlist Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/watchlist -add SYMBOL` | Add a symbol to watchlist. Auto-detects market (crypto vs US). | `/watchlist -add AAPL` |
| `/watchlist -remove SYMBOL` | Remove a symbol from watchlist. | `/watchlist -remove AAPL` |
| `/watchlist -ls` | List all watchlist symbols with market and add date. | `/watchlist -ls` |
| `/watchlist` | Same as `-ls` when called without arguments. | `/watchlist` |

### Position Management Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/position -add SYMBOL PRICE [QTY] [sl:X] [tp:X]` | Log a new open position. SL and TP are optional. | `/position -add AAPL 175.50 100 sl:168 tp:195` |
| `/position -ls` | List all open positions with entry price, SL, TP, and status. | `/position -ls` |
| `/position -close SYMBOL` | Close an open position (manual close). | `/position -close AAPL` |

### Knowledge and Memory Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/note "text"` | Save a free-form thought, observation, or trading idea. LLM will process and merge into wiki. | `/note "AAPL showing bullish divergence on RSI"` |
| `/note -symbol SYMBOL "text"` | Save a symbol-specific note. | `/note -symbol BTC "resistance at 65K, accumulation pattern"` |
| `/strategy add "rule"` | Add a custom strategy rule or observation. | `/strategy add "avoid trading during FOMC weeks"` |
| `/wiki TOPIC` | View a wiki page. Topics: strategy, patterns, lessons, regime, or any symbol name. | `/wiki lessons` |
| `/think SYMBOL "thesis"` | Save a structured trading thesis for a symbol. Included in future analyses. | `/think AAPL "services revenue growth will offset hardware slowdown"` |

### Trade Feedback Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/trade SYMBOL took [reason]` | Log that you took a trade. Reason is optional. | `/trade AAPL took "strong setup, good volume"` |
| `/trade SYMBOL skip [reason]` | Log that you skipped a signal. | `/trade AAPL skip "market too volatile"` |
| `/trade SYMBOL partial [reason]` | Log that you took a partial position. | `/trade AAPL partial "half size, uncertain about market"` |

### Drill-Down Analysis Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/history SYMBOL 7d` | View recent signal history for a symbol (last N days). | `/history AAPL 30d` |
| `/backtest SYMBOL 6m` | Backtest all strategies on a symbol for a period. Currently returns mock data. | `/backtest AAPL 6m` |
| `/reasoning SYMBOL` | Technical breakdown (LLM-powered, requires OpenRouter). | `/reasoning AAPL` |
| `/catalyst SYMBOL` | News catalyst analysis (requires working news module). | `/catalyst AAPL` |
| `/sentiment SYMBOL` | Sentiment analysis (requires working sentiment module). | `/sentiment BTC` |
| `/why SYMBOL` | Entry rationale for latest signal. | `/why AAPL` |

### System Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/scan` | Scan the entire watchlist through the full pipeline. Reports results per symbol. | `/scan` |
| `/scan -quick` | Quick scan -- technical scores only (no full analysis). | `/scan -quick` |
| `/regime` | Show current market regime for US (based on SPY) and crypto (based on BTC). | `/regime` |
| `/status` | System health: watchlist count, signals in last 7d, LLM cache count, API key status. | `/status` |
| `/profile` | View your trading profile (risk tolerance, preferred strategies, etc., extracted from wiki). | `/profile` |
| `/help` | Display command reference. | `/help` |
| `/start` | Same as `/help`. | `/start` |
| `/clear` | Clear pending updates and reset chat history. | `/clear` |
| `/cancel` | Same as `/clear`. | `/cancel` |

### Free-Form Chat (No Command Prefix)

Any message not starting with `/` is routed to the **LLM chat agent** (requires OpenRouter key). The agent has tool access to:

- `analyze_symbol` -- run technical analysis on any symbol
- `get_recent_signals` -- fetch recent signals from the database
- `get_watchlist` -- list watchlist symbols
- `get_lessons` -- query stored lessons and notes

The agent maintains a conversation history (last 10 messages) and can use tools in response to your questions.

**Example free-form chat:**
- "What's the market looking like today?"
- "Check BTC for me"
- "What signals did you generate this week?"
- "Any lessons learned from recent AAPL trades?"

---

## 8. Testing

### Running the Test Suite

```bash
pytest tests/ -v
```

### What Gets Tested

The test suite is in `tests/` with `pytest-asyncio` mode set to `auto` (async tests run automatically):

| Test File | What It Covers |
|-----------|---------------|
| `test_breadth.py` | S&P 500 Bullish Percent Index calculation |
| `test_crypto_feed.py` | Binance crypto data fetching |
| `test_daemon_schedule.py` | Scheduler timing logic, trading day detection, NYSE holiday awareness |
| `test_earnings.py` | Earnings proximity calculation |
| `test_realtime_prices.py` | Real-time price fetching |
| `test_signal_quality.py` | Signal quality metrics and validation |

### Test Dependencies

Tests require `pytest` and `pytest-asyncio` (both in `requirements.txt`).

### Running a Specific Test

```bash
pytest tests/test_daemon_schedule.py -v
```

### Note on Tests

Some tests may require API keys or network access to pass. Tests that depend on external APIs may fail if the API is unavailable or the required credentials are not set. This is expected for offline development.

---

## 9. Troubleshooting

### Bot Won't Start

**"ModuleNotFoundError: No module named 'dotenv'"**
```bash
pip install python-dotenv
# or: pip install -r requirements.txt
```

**"No module named 'httpx'"**
```bash
pip install httpx
```

**"OPENROUTER_API_KEY not set"**
- Add `OPENROUTER_API_KEY=your_key` to `.env`
- Bot will still start, but LLM features will be disabled

**"ValueError: TELEGRAM_BOT_TOKEN not configured"**
- Verify `.env` exists and contains `TELEGRAM_BOT_TOKEN=your_token`
- Run the bot from the project root directory so `.env` is found

### Telegram Connection Issues

**Bot does not respond to commands:**
- Check that `TELEGRAM_BOT_TOKEN` is valid (visit `https://api.telegram.org/bot<YOUR_TOKEN>/getMe` -- should return `{"ok":true}`)
- Check that `TELEGRAM_CHAT_ID` is correct (run the getUpdates URL check from Section 3)
- Ensure the bot is a member of the target group/channel
- Check console logs for HTTP errors from the Telegram API

**"sendMessage FAIL" in logs:**
- The bot received the command but the response could not be delivered
- Common cause: bot was removed from the group, or chat_id changed

**"httpx is None" warning in logs:**
- `httpx` is not installed. Install it: `pip install httpx`

### API Key Errors

**Alpaca errors (US scans fail):**
- Verify `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` are correct
- Check that the Alpaca account is active (paper trading accounts expire after 30 days of inactivity)
- Alpaca may rate-limit: wait 1 minute and try again

**OpenRouter errors (LLM analysis fails):**
- Verify `OPENROUTER_API_KEY` is correct
- Check your OpenRouter credits/balance at [openrouter.ai](https://openrouter.ai/)
- The bot uses token-bucket rate limiting (4 requests per minute) -- waiting is normal
- Response cache has 5-hour TTL -- repeated identical queries will use cache

**Finnhub errors (real-time prices fail):**
- Finnhub free tier has rate limits (60 requests per minute)
- The bot degrades gracefully -- scans continue without price tightening

### Database Issues

**"sqlite3.OperationalError: no such table"**
- Run `python -c "from db.store import init_db; init_db()"` to create tables

**"disk I/O error" or "database is locked":**
- SQLite is single-writer. Only one bot instance should run at a time.
- Check for zombie processes: `ps aux | grep bot.py`

**Database file not found:**
- The bot creates the DB file at `DB_PATH` from `.env`, or defaults to `sora.db`
- Ensure the directory is writable

### Symbol Not Found

**"No signal generated for SYMBOL"**
- For US equities: verify the symbol is traded on NASDAQ or NYSE
- For crypto: only supported symbols work (BTC, ETH, SOL, BNB, AVAX, LINK, DOT, MATIC, ADA, XRP)
- Insufficient data: the pipeline requires at least 20 daily bars (90 are fetched)
- Low confidence: the signal may have been rejected by confidence engine (< 35 score)

**"Added X (us) to watchlist" for a crypto symbol:**
- The bot auto-detects market from a known set of crypto symbols
- Supported crypto: BTC, ETH, SOL, BNB, AVAX, LINK, DOT, MATIC, ADA, XRP, DOGE
- If your symbol is not in this set, it defaults to "us"

### Crypto vs US Symbols

**Crypto symbols supported:** BTC, ETH, SOL, BNB, AVAX, LINK, DOT, MATIC, ADA, XRP
- DOGE is recognized as crypto for watchlist detection but may not have real-time price lookup

**Crypto data source:** Binance public API (no key required) -- 90 daily bars
**US data source:** Alpaca Markets API (key required) -- 90 daily bars

### Other Issues

**High memory usage:**
- Matplotlib chart generation can be memory-intensive
- LLM response cache can grow over time (SQLite, no automatic pruning)
- Restart the bot periodically to clear memory

**Bot time drift:**
- The scheduler uses `America/New_York` timezone for all market timing
- System clock must be accurate (use NTP)

**Service keeps restarting (VPS):**
- Check `journalctl -u noor-bot -n 100` for Python traceback
- Common causes: missing dependency, import error, API key not set

---

## 10. VPS Deployment

### Deploying on Ubuntu 22.04 with systemd

This is a summary. A detailed deployment plan is at `docs/superpowers/plans/2026-05-24-vps-deployment.md`.

### Step 1: Server Setup

SSH into your VPS and run:

```bash
# Update system
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip git

# Create a dedicated user
useradd -m -s /bin/bash noor

# Clone the repository
mkdir -p /opt/noor-bot
git clone <your-repo-url> /opt/noor-bot
chown -R noor:noor /opt/noor-bot

# Create virtual environment and install dependencies
su - noor
cd /opt/noor-bot
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
exit
```

### Step 2: Configure Environment

```bash
cp /opt/noor-bot/.env.template /opt/noor-bot/.env
# Edit with nano/vim and fill in all API keys
nano /opt/noor-bot/.env
chmod 600 /opt/noor-bot/.env
chown noor:noor /opt/noor-bot/.env
```

### Step 3: Create systemd Service

Create `/etc/systemd/system/noor-bot.service`:

```ini
[Unit]
Description=Noor Trading Bot
After=network.target

[Service]
Type=simple
User=noor
WorkingDirectory=/opt/noor-bot
EnvironmentFile=/opt/noor-bot/.env
ExecStart=/opt/noor-bot/.venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Step 4: Enable and Start

```bash
systemctl daemon-reload
systemctl enable noor-bot
systemctl start noor-bot
```

### Step 5: Verify

```bash
systemctl status noor-bot
# Should show: Active: active (running)
```

Send a Telegram message to verify the bot responds.

### Useful systemd Commands

```bash
# View recent logs
journalctl -u noor-bot -n 100

# Follow live logs
journalctl -u noor-bot -f

# Restart the bot
systemctl restart noor-bot

# Stop the bot
systemctl stop noor-bot
```

### Updating the Bot

```bash
ssh root@YOUR_SERVER_IP
cd /opt/noor-bot
git pull
systemctl restart noor-bot
journalctl -u noor-bot -f
```

### VPS Requirements

- **Minimum:** 1 CPU, 512 MB RAM, 10 GB SSD
- **Recommended:** 1 CPU, 1 GB RAM, 20 GB SSD
- **OS:** Ubuntu 22.04 LTS (other Linux distros will work with adjusted package commands)
- **Network:** Outbound HTTPS access (no inbound ports needed for bot operation)

---

## 11. Maintenance

### Logs

The bot uses a custom colored logging formatter (`log.py`). Log output goes to stdout:

- **Log format:** `HH:MM:SS ET  LEVEL  MODULE    message`
- **Color coding:** INFO=green, WARN=yellow, ERROR=red, HTTP=blue, LLM=magenta, TELEGRAM=cyan, DATA=blue
- **HTTP level (15):** Special log level for HTTP request timing

On VPS, logs are captured by systemd journal. To save logs to a file:

```bash
journalctl -u noor-bot --since "1 hour ago" > /var/log/noor-bot.log
```

For local development, redirect stdout to a file:

```bash
python bot.py > bot.log 2>&1
```

### Database Backup

The SQLite database contains all signals, watchlist, positions, feedback, and LLM cache. Back it up regularly:

```bash
# Simple copy backup (bot must NOT be running for safe copy)
cp sora.db sora.db.backup.$(date +%Y%m%d)

# Or use sqlite3 for live backup (bot can be running)
sqlite3 sora.db ".backup sora.db.backup.$(date +%Y%m%d)"
```

Recommended backup schedule:
- **Daily** for active trading
- **Weekly** for casual use
- **Keep 7-30 days** of backups

Bot data is gitignored (`*.db`), so backups must be done manually or via cron.

### Database Maintenance

The LLM cache table can grow large over time (5-hour TTL entries that expire). Clean expired entries:

```bash
python -c "
import sqlite3, os
db = os.environ.get('DB_PATH', 'sora.db')
conn = sqlite3.connect(db)
c = conn.cursor()
c.execute('DELETE FROM llm_cache WHERE expires_at < datetime(\"now\")')
deleted = c.rowcount
conn.commit()
conn.close()
print(f'Cleaned {deleted} expired cache entries')
"
```

### Wiki Management

The bot maintains an LLM-powered wiki in `knowledge/wiki/`:

```
knowledge/
  wiki/
    strategy.md        # Active trading strategies and rules
    patterns.md        # Recognized chart patterns
    lessons.md         # Accumulated lessons from review cycles
    regime.md          # Market regime observations
    symbols/
      AAPL.md          # Per-symbol wiki pages
      BTC.md
      ...
  raw/
    inputs.log         # Raw input log for audit trail
```

**How wiki grows:**
- `/note` commands trigger LLM analysis and wiki updates
- `/trade` feedback is ingested into wiki lessons
- Weekly reviews update strategy, patterns, and regime pages
- `/think` theses are saved as symbol-specific wiki entries

**To manually edit a wiki page:**
Just edit the markdown files directly. The LLM will read the current content during next analysis.

**To clear wiki content:**
Delete the files or directories and restart the bot. The LLM will regenerate content as new notes and scans occur.

### Watching Scan Windows

After deployment, verify the daemon fires at the correct times by monitoring logs:

| Time (ET) | Day | Expected log |
|-----------|-----|-------------|
| 8:30 AM | Mon-Fri | `[Daemon] US scan starting: us_premarket` |
| 3:00 PM | Mon-Fri | `[Daemon] US scan starting: us_preclose` |
| 9:30 AM - 4:00 PM (every 30min) | Mon-Fri | `[Daemon] Position scan` |
| 0:00/4:00/8:00/12:00/16:00/20:00 | Mon-Fri | `[Daemon] Crypto scan` |
| Sunday 8:00 PM | Weekly | `[Daemon] Weekly review` |

### Bot Updates

When updating the codebase:

1. Pull new code: `git pull`
2. Reinstall dependencies if requirements.txt changed: `pip install -r requirements.txt`
3. Re-run DB init if new tables were added: `python -c "from db.store import init_db; init_db()"`
4. Restart the bot

### Knowledge Graph

The project includes an interactive knowledge graph at `graphify-out/graph.html` (generated from codebase structure). Open it in a browser to explore module relationships, data flow, and dependencies.
