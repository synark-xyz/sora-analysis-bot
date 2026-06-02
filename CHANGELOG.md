# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-05-25

### Added

- Initial v2 release extracted from `sora-trading-bot`
- Multi-agent LLM analysis pipeline: Bull Agent, Bear Agent, Analyst Agent with debate scoring
- Five built-in trading strategies: EMA+RSI+Volume, Supertrend+MACD, Bollinger Squeeze, RSI Mean Reversion, VWAP Momentum
- Deterministic confidence engine with 7 explainable dimensions (0-100 scoring)
- Market regime detection: BULL, BEAR, NEUTRAL, RANGING, VOLATILE via ADX + trend + volatility
- Confluence validator and signal gate (8-rule pre-notification filter)
- Moomoo 5-step structured analysis framework
- Pre-execution filters: earnings proximity, liquidity, volume environment, spread, ATR
- Market-aware scheduling: pre-market (8:30 ET), pre-close (15:00 ET), crypto every 4h, position monitoring
- Telegram command interface with 20+ slash commands and free-form LLM chat
- Karpathy-style LLM wiki system with auto-ingestion and linting
- Feedback loop: trade outcomes, signal tracking, outcome-adjusted conviction
- User profile extraction from wiki content
- News aggregation (Yahoo Finance RSS, CryptoPanic RSS)
- Fundamentals and valuation via Financial Modeling Prep
- Earnings calendar proximity detection
- S&P 500 Bullish Percent Index (market breadth)
- Real-time price integration via Finnhub
- Position tracking with automatic SL/TP monitoring
- Candlestick chart generation (matplotlib/mplfinance, dark theme)
- Weekly review agent with strategy evaluation and pattern extraction
- OpenRouter LLM client with token-bucket rate limiting and SQLite response cache
- SQLite persistence with 8 tables
- VPS deployment documentation with systemd service template
- Comprehensive README and GETTING_STARTED documentation
- Interactive knowledge graph (graphify-out/graph.html)
- GitHub Pages landing page (index.html)

### Changed

- Complete rewrite from single-file prototype to modular architecture (engine/, telegram/, data/, analysis/, llm/, memory/, scheduler/, db/)
- Replaced manual CoinGecko integration with Binance klines API for crypto OHLCV
- Replaced Alpaca/CoinGecko real-time prices with Finnhub (US) and Binance (crypto)
- Migrated from `noor-trading-bot` commit `15d0130fb0c6ec124095f2d4bd8427f50c07ccee`

### Fixed

- Clean Ctrl+C shutdown via asyncio task cancellation
- Robust JSON extraction from LLM responses
- Correct handling of `/analyze` command flags
- Alpaca latest quote for real-time US stock prices
- Tightened entry zones to real-time price for daemon notifications
- NYSE holiday-aware scheduling
