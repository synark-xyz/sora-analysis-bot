# Graph Report - .  (2026-05-24)

## Corpus Check
- Corpus is ~31,933 words - fits in a single context window. You may not need a graph.

## Summary
- 482 nodes · 1033 edges · 27 communities detected
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 164 edges (avg confidence: 0.76)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Telegram Handler & Formatting|Telegram Handler & Formatting]]
- [[_COMMUNITY_LLM Client & Signal Testing|LLM Client & Signal Testing]]
- [[_COMMUNITY_Pipeline Orchestrator|Pipeline Orchestrator]]
- [[_COMMUNITY_SQLite Database & Storage|SQLite Database & Storage]]
- [[_COMMUNITY_Trading Strategies|Trading Strategies]]
- [[_COMMUNITY_Regime Detection|Regime Detection]]
- [[_COMMUNITY_Market Breadth|Market Breadth]]
- [[_COMMUNITY_Confidence Engine|Confidence Engine]]
- [[_COMMUNITY_Bot Core & Deployment|Bot Core & Deployment]]
- [[_COMMUNITY_Earnings Analysis|Earnings Analysis]]
- [[_COMMUNITY_Signal Gate & Validation|Signal Gate & Validation]]
- [[_COMMUNITY_News & Sentiment Analysis|News & Sentiment Analysis]]
- [[_COMMUNITY_Real-Time Data & Scheduling|Real-Time Data & Scheduling]]
- [[_COMMUNITY_Filters & Earnings Guard|Filters & Earnings Guard]]
- [[_COMMUNITY_Crypto Data Feed|Crypto Data Feed]]
- [[_COMMUNITY_External Price Providers|External Price Providers]]
- [[_COMMUNITY_LLM Agent Pipeline|LLM Agent Pipeline]]
- [[_COMMUNITY_Scheduler Timing|Scheduler Timing]]
- [[_COMMUNITY_Chart Generation|Chart Generation]]
- [[_COMMUNITY_Fundamentals|Fundamentals]]
- [[_COMMUNITY_Signal Reporter|Signal Reporter]]
- [[_COMMUNITY_Trade Feedback|Trade Feedback]]
- [[_COMMUNITY_LLM Infrastructure|LLM Infrastructure]]
- [[_COMMUNITY_Scheduler Scan Logic|Scheduler Scan Logic]]
- [[_COMMUNITY_Database Module|Database Module]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]

## God Nodes (most connected - your core abstractions)
1. `TelegramHandler` - 45 edges
2. `LLMClient` - 30 edges
3. `_compute_indicators()` - 24 edges
4. `_get_conn()` - 21 edges
5. `_run_full_analysis()` - 19 edges
6. `now()` - 16 edges
7. `run_pipeline()` - 15 edges
8. `Daemon` - 13 edges
9. `format_signal_report()` - 13 edges
10. `detect_regime()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `get_recent_signals_for_symbol returns list of dicts with required keys.` --uses--> `LLMClient`  [INFERRED]
  /Users/sayem/Business_MVPs/noor-telegram-bot/tests/test_signal_quality.py → /Users/sayem/Business_MVPs/noor-telegram-bot/llm/client.py
- `Sora Bot v2` --references--> `sora-trading-bot (V1)`  [EXTRACTED]
  docs/superpowers/specs/2026-05-21-sora-bot-v2-design.md → CLAUDE.md
- `Sora Bot v2` --references--> `memory/ module`  [EXTRACTED]
  docs/superpowers/specs/2026-05-21-sora-bot-v2-design.md → CLAUDE.md
- `Sora Bot v2` --references--> `knowledge/ module`  [EXTRACTED]
  docs/superpowers/specs/2026-05-21-sora-bot-v2-design.md → CLAUDE.md
- `Earnings Proximity Guard` --implements--> `analysis/ module`  [INFERRED]
  docs/superpowers/plans/2026-05-24-signal-quality-improvements.md → CLAUDE.md

## Hyperedges (group relationships)
- **Sora Bot v2 Architecture** — claude_md__bot_py, claude_md__telegram_module, claude_md__engine_module, claude_md__data_module, claude_md__analysis_module, claude_md__llm_module, claude_md__memory_module, claude_md__scheduler_module, claude_md__db_module, claude_md__knowledge_module [EXTRACTED 1.00]
- **7 Signal Quality Improvements** — signal_quality_plan__earnings_proximity_guard, signal_quality_plan__rr_pregate, signal_quality_plan__volume_confirmation, signal_quality_plan__market_breadth_filter, signal_quality_plan__historical_signal_injection, signal_quality_plan__debate_scoring, signal_quality_plan__outcome_conviction [EXTRACTED 1.00]
- **LLM Agent Pipeline (Bull->Bear->Analyst)** — v2_design__bull_agent, v2_design__bear_agent, v2_design__analyst_agent [EXTRACTED 1.00]
- **Real-Time Data Provider Swap** — realtime_plan__finnhub, realtime_plan__binance, claude_md__alpaca, claude_md__coingecko [EXTRACTED 1.00]
- **Daemon Schedule Changes (May 2026)** — realtime_plan__daemon_tick, realtime_plan__weekday_trading_guard, realtime_plan__scan_window_tightening [EXTRACTED 1.00]

## Communities

### Community 0 - "Telegram Handler & Formatting"
Cohesion: 0.08
Nodes (19): main(), Daemon, _confidence_label(), _dollar(), format_backtest(), format_confidence_bar(), format_help(), format_history() (+11 more)

### Community 1 - "LLM Client & Signal Testing"
Cohesion: 0.06
Nodes (37): analyze_full(), analyze_moomoo(), analyze_quick(), _get_api_key(), LLMClient, Returns (content, None) for text reply or (None, tool_calls) for tool invocation, TokenBucket, ReviewAgent (+29 more)

### Community 2 - "Pipeline Orchestrator"
Cohesion: 0.18
Nodes (33): _adx(), _assess_conditions(), _atr(), _bb_squeeze(), _bollinger(), _build_reason(), _build_result(), _calc_historical_volatility() (+25 more)

### Community 3 - "SQLite Database & Storage"
Cohesion: 0.17
Nodes (27): add_position(), add_watchlist_symbol(), cache_llm_get(), cache_llm_set(), close_position(), _dict_from_row(), format_signal_history(), _get_conn() (+19 more)

### Community 4 - "Trading Strategies"
Cohesion: 0.16
Nodes (19): Enum, engine/orchestrator.py — Multi-market signal pipeline.  Pipeline flow:   Market, BollingerSqueeze, EMARSIVolume, get_all_regime_strategies(), get_strategies(), get_strategies_for_regime(), get_strategy() (+11 more)

### Community 5 - "Regime Detection"
Cohesion: 0.18
Nodes (20): _calc_adx(), _calc_historical_volatility(), _calc_trend(), _calc_volatility(), detect_regime(), _fetch_alpaca_spy(), fetch_crypto_bars(), fetch_spy_bars() (+12 more)

### Community 6 - "Market Breadth"
Cohesion: 0.22
Nodes (13): breadth_context_str(), _fetch_spx_breadth_pct(), get_market_breadth(), Market breadth filter. Fetches S&P 500 Bullish Percent Index (^SPXBDP) via yfina, Fetch latest S&P500 Bullish Percent Index value (0-100)., Return breadth dict:       {         "breadth_pct": float | None,  # 0-100, % of, Format breadth dict into a one-line LLM context string., test_breadth_context_str_weak() (+5 more)

### Community 7 - "Confidence Engine"
Cohesion: 0.3
Nodes (14): ConfidenceComponent, ConfidenceEngine, ConfidenceResult, _drawdown_state(), _historical_performance(), engine/confidence.py — Deterministic, explainable confidence engine.  Seven dime, Deterministic confidence engine with 7 explainable dimensions., _regime_fit() (+6 more)

### Community 8 - "Bot Core & Deployment"
Cohesion: 0.12
Nodes (17): analysis/ module, bot.py, knowledge/ module, memory/ module, scheduler/ module, sora-trading-bot (V1), telegram/ module, noor-telegram-bot (+9 more)

### Community 9 - "Earnings Analysis"
Cohesion: 0.23
Nodes (12): days_to_earnings(), earnings_risk_flag(), _fetch_earnings_date(), Earnings proximity guard. Returns days until next earnings and a HIGH/LOW risk f, Fetch next earnings date via yfinance. Returns UTC datetime or None., Return number of calendar days until next earnings.     Returns None if earnings, Return 'HIGH' if earnings within EARNINGS_RISK_DAYS, else 'LOW'.     Crypto symb, test_days_to_earnings_returns_int_when_date_available() (+4 more)

### Community 10 - "Signal Gate & Validation"
Cohesion: 0.37
Nodes (13): _check_confidence(), _check_entry_zone(), check_gate(), _check_news_cooldown(), _check_rr(), _check_rsi(), _check_stop_sanity(), _check_volume() (+5 more)

### Community 11 - "News & Sentiment Analysis"
Cohesion: 0.19
Nodes (8): ColoredFormatter, get_logger(), _http(), _fetch_cryptopanic(), fetch_news(), analysis/news.py — News headline fetcher.  Sources:   - Yahoo Finance RSS (free,, get_sentiment(), analysis/sentiment.py — Sentiment analysis.  On-demand sentiment fetcher. Crypto

### Community 12 - "Real-Time Data & Scheduling"
Cohesion: 0.31
Nodes (10): _get_current_price(), _is_trading_day(), _is_us_market_open(), test_crypto_price_calls_binance(), test_crypto_price_returns_none_on_exception(), test_crypto_price_unknown_symbol_returns_none(), test_us_price_calls_finnhub(), test_us_price_returns_none_on_exception() (+2 more)

### Community 13 - "Filters & Earnings Guard"
Cohesion: 0.31
Nodes (12): check_all(), _check_earnings(), _check_liquidity(), _check_spread(), _check_volume_environment(), FilterResult, engine/filters.py — Pre-execution trade filters (v2, crypto-friendly).  Each fil, Skip if overall volume environment is abnormal. (+4 more)

### Community 14 - "Crypto Data Feed"
Cohesion: 0.31
Nodes (9): fetch_bars(), data/crypto_feed.py — Cryptocurrency OHLCV feed via Binance public API.  No API, _make_kline(), test_binance_symbols_has_ten_entries(), test_fetch_bars_api_error_returns_empty(), test_fetch_bars_calls_correct_binance_symbol(), test_fetch_bars_returns_ohlcv_dicts(), test_fetch_bars_unknown_symbol_returns_empty() (+1 more)

### Community 15 - "External Price Providers"
Cohesion: 0.21
Nodes (12): Alpaca, CoinGecko, engine/ module, Binance over CoinGecko Rationale, Finnhub over Alpaca IEX Rationale, REST over WebSocket Rationale, Binance (Real-Time Crypto Prices + Klines), fetch_bars() in crypto_feed.py (+4 more)

### Community 16 - "LLM Agent Pipeline"
Cohesion: 0.2
Nodes (12): db/store.py — signal history queries, Bull/Bear Debate Scoring, Historical Signal Injection, llm/analyst.py — enhanced analyze_full(), Outcome-Adjusted Conviction, AnalystAgent, Autoresearch Self-Improvement Loop, BearAgent (+4 more)

### Community 17 - "Scheduler Timing"
Cohesion: 0.44
Nodes (9): daemon(), _FixedDatetime, test_crypto_scan_blocked_on_weekend(), test_crypto_scan_fires_on_weekday(), test_midday_not_fired(), test_postopen_not_fired(), test_preclose_fires_at_15_00(), test_premarket_still_fires() (+1 more)

### Community 18 - "Chart Generation"
Cohesion: 0.53
Nodes (9): _add_signal_annotations_mpf(), _add_signal_annotations_mpl(), _bars_to_dataframe(), _compute_ema(), _compute_in_series(), _empty_chart(), generate_chart(), _generate_mpf() (+1 more)

### Community 19 - "Fundamentals"
Cohesion: 0.44
Nodes (7): _fetch_insider(), _fetch_institutional(), _fetch_profile(), get_fundamentals(), get_valuation(), analysis/fundamental.py — Fundamentals from Financial Modeling Prep (FMP).  Free, Fetch valuation metrics from FMP — P/B, P/S, PEG, EV/EBITDA, ROE, ROA, analyst e

### Community 20 - "Signal Reporter"
Cohesion: 0.67
Nodes (5): build_confidence_bar(), build_report(), _confidence_label(), format_report(), parse_signal_response()

### Community 21 - "Trade Feedback"
Cohesion: 0.83
Nodes (2): log_trade_action(), process_trade_feedback()

### Community 22 - "LLM Infrastructure"
Cohesion: 0.5
Nodes (4): llm/ module, OpenRouter, Token Bucket Rate Limiter + Async Queue, 3-Layer LLM Cache (Indicators/LLM/News)

### Community 23 - "Scheduler Scan Logic"
Cohesion: 0.67
Nodes (3): _tick() in scheduler/daemon.py, Scan Window Tightening (premarket+preclose only), Weekday Trading Guard

### Community 24 - "Database Module"
Cohesion: 1.0
Nodes (2): db/ module, SQLite DB

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): data/ module

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): pytest

## Knowledge Gaps
- **47 isolated node(s):** `Returns (content, None) for text reply or (None, tool_calls) for tool invocation`, `Fetch next earnings date via yfinance. Returns UTC datetime or None.`, `Return number of calendar days until next earnings.     Returns None if earnings`, `Return 'HIGH' if earnings within EARNINGS_RISK_DAYS, else 'LOW'.     Crypto symb`, `Fetch latest S&P500 Bullish Percent Index value (0-100).` (+42 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Trade Feedback`** (4 nodes): `log_trade_action()`, `process_trade_feedback()`, `feedback.py`, `feedback.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Database Module`** (2 nodes): `db/ module`, `SQLite DB`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `data/ module`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `pytest`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_run_full_analysis()` connect `Pipeline Orchestrator` to `LLM Client & Signal Testing`, `SQLite Database & Storage`, `Regime Detection`, `Market Breadth`, `Earnings Analysis`, `News & Sentiment Analysis`, `Fundamentals`?**
  _High betweenness centrality (0.221) - this node is a cross-community bridge._
- **Why does `now()` connect `Regime Detection` to `Telegram Handler & Formatting`, `LLM Client & Signal Testing`, `Earnings Analysis`, `Signal Gate & Validation`, `Real-Time Data & Scheduling`, `Filters & Earnings Guard`, `Scheduler Timing`?**
  _High betweenness centrality (0.149) - this node is a cross-community bridge._
- **Why does `TelegramHandler` connect `Telegram Handler & Formatting` to `LLM Client & Signal Testing`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `TelegramHandler` (e.g. with `Daemon` and `LLMClient`) actually correct?**
  _`TelegramHandler` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `LLMClient` (e.g. with `ReviewAgent` and `When ATR/price < 0.003, _run_full_analysis returns HOLD without LLM call.`) actually correct?**
  _`LLMClient` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `_compute_indicators()` (e.g. with `test_volume_signal_strong_on_spike()` and `test_volume_signal_weak_on_low_volume()`) actually correct?**
  _`_compute_indicators()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `_run_full_analysis()` (e.g. with `test_rr_pregate_skips_llm_on_flatline()` and `test_earnings_high_risk_forces_wait()`) actually correct?**
  _`_run_full_analysis()` has 14 INFERRED edges - model-reasoned connections that need verification._