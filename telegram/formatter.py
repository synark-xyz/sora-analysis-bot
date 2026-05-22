def format_confidence_bar(score, width=12):
    if score < 0:
        score = 0
    if score > 100:
        score = 100
    filled = round(score / 100 * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def _confidence_label(score):
    if score >= 80:
        return "HIGH"
    elif score >= 60:
        return "MEDIUM"
    else:
        return "LOW"


def _pct_str(value):
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def _dollar(value):
    if value is None:
        return "N/A"
    return f"${value:.2f}"


def format_signal_report(signal):
    symbol = signal.get("symbol", "?")
    verdict = signal.get("verdict", "HOLD")
    confidence = signal.get("confidence", 0)
    label = _confidence_label(confidence)
    strategy = signal.get("strategy", "—")
    regime = signal.get("regime", "—")
    entry_low = signal.get("entry_low")
    entry_high = signal.get("entry_high")
    exit_target = signal.get("exit_target")
    stop_loss = signal.get("stop_loss")
    rr = signal.get("rr_ratio")
    reason = signal.get("reason", "")

    entry_return = None
    if exit_target and entry_low:
        entry_return = ((exit_target - entry_low) / entry_low) * 100
    stop_return = None
    if stop_loss and entry_low:
        stop_return = ((stop_loss - entry_low) / entry_low) * 100

    lines = [
        f"<b>{'📊'} {symbol}  ·  {verdict} SIGNAL</b>",
        f"Confidence  {confidence:.0f} / 100  [{label}]",
        f"Strategy    {strategy}",
        f"Regime      {regime}",
        "",
    ]

    if entry_low is not None and entry_high is not None:
        lines.append(f"{'📍'} ENTRY ZONE    {_dollar(entry_low)} \u2013 {_dollar(entry_high)}")
        if signal.get("entry_anchor"):
            lines.append(f"   Anchor: {signal['entry_anchor']}")
    if exit_target is not None:
        lines.append(f"{'🎯'} EXIT TARGET   {_dollar(exit_target)}  ({_pct_str(entry_return)})")
        if signal.get("exit_anchor"):
            lines.append(f"   Anchor: {signal['exit_anchor']}")
    if stop_loss is not None:
        lines.append(f"{'🛑'} STOP LOSS     {_dollar(stop_loss)}  ({_pct_str(stop_return)})")
        if signal.get("stop_anchor"):
            lines.append(f"   Anchor: {signal['stop_anchor']}")
    if rr is not None:
        lines.append(f"{'⚖️'}  RISK / REWARD   1 : {rr:.1f}")
    if signal.get("timeframe"):
        lines.append(f"{'⏱'}  Timeframe        {signal['timeframe']}")
    else:
        lines.append(f"{'⏱'}  Timeframe        Swing (5\u201312 days)")

    conf_breakdown = signal.get("confidence_breakdown") or signal.get("breakdown")
    if conf_breakdown:
        lines.append("")
        lines.append("CONFIDENCE BREAKDOWN")
        for dim in conf_breakdown:
            if isinstance(dim, dict):
                name = dim.get("name", "?")
                score = dim.get("score", 0)
                lines.append(f"  {name:<20} {format_confidence_bar(score)}  {score:.0f}%")
            elif isinstance(dim, (list, tuple)):
                lines.append(f"  {dim[0]:<20} {format_confidence_bar(dim[1])}  {dim[1]:.0f}%")

    rules = signal.get("rules_check") or signal.get("rules")
    if rules:
        lines.append("")
        lines.append(f"Your rules: {rules}")

    if reason:
        lines.append("")
        lines.append(f"<i>{reason}</i>")

    return "\n".join(lines)


def format_watchlist(symbols):
    if not symbols:
        return "<b>Watchlist is empty.</b>"

    lines = [f"<b>Watchlist ({len(symbols)} symbols)</b>", ""]
    for s in symbols:
        market_tag = "{:4s}".format(s.get("market", "?"))
        lines.append(f"  {s['symbol']:<8} [{market_tag}]")
    return "\n".join(lines)


def format_status(status):
    lines = [
        f"<b>System Health</b>",
        f"  Bot Uptime:   {status.get('uptime', 'N/A')}",
        f"  Last Scan:    {status.get('last_scan', 'never')}",
        f"  Watchlist:    {status.get('watchlist_count', 0)} symbols",
        f"  Signals (7d): {status.get('signals_7d', 0)}",
        f"  LLM Cached:   {status.get('llm_cache_count', 0)} entries",
        f"  OpenRouter:   {status.get('llm_status', 'unknown')}",
        f"  Alpaca:       {status.get('alpaca_status', 'unknown')}",
    ]
    if status.get("errors"):
        lines.append("")
        lines.append(f"<b>Errors:</b>")
        for e in status["errors"]:
            lines.append(f"  {'⚠️'} {e}")
    return "\n".join(lines)


def format_regime(regime):
    us = regime.get("us", {})
    crypto = regime.get("crypto", {})

    lines = [
        "<b>Market Regime</b>",
        "",
        f"<b>US Equities</b>",
        f"  Regime:    {us.get('regime', 'N/A')}",
        f"  Trend:     {us.get('trend', 'N/A')}",
        f"  ADX:       {us.get('adx', 'N/A')}",
        f"  SPY:       {_dollar(us.get('spy_price'))}  ({_pct_str(us.get('spy_change'))})",
        "",
        f"<b>Crypto</b>",
        f"  Regime:    {crypto.get('regime', 'N/A')}",
        f"  BTC:       {_dollar(crypto.get('btc_price'))}  ({_pct_str(crypto.get('btc_change'))})",
        f"  BTC Dom:   {crypto.get('btc_dominance', 'N/A')}%",
    ]
    return "\n".join(lines)


def format_help():
    return """<b>Noor Bot v2 — Commands</b>

<b>Analysis</b>
  /analyze SYMBOL       Quick signal (technical, ~30s)
  /analyze SYMBOL -full Deep report (~90s)
  /analyze SYMBOL -swing Force swing timeframe
  /analyze SYMBOL -long Force long-term

<b>Watchlist</b>
  /watchlist -add SYMBOL    Add symbol
  /watchlist -remove SYMBOL Remove symbol
  /watchlist -ls            List all

<b>Knowledge</b>
  /note "text"              Free-form thought
  /note -symbol SYMBOL "text"
  /strategy add "rule"      Add rule
  /wiki SYMBOL|strategy|patterns|lint

<b>Feedback</b>
  /trade SYMBOL took|skip|partial
  /history SYMBOL 7d

<b>Drill-down</b>
  /reasoning SYMBOL
  /backtest SYMBOL 6m
  /catalyst SYMBOL
  /sentiment SYMBOL
  /why SYMBOL

<b>System</b>
  /scan        Scan watchlist
  /scan -quick Technical scores only
  /regime      Market regime
  /profile     Your trading profile
  /status      System health
  /help        This message"""


def format_backtest(results, symbol):
    if not results:
        return f"<b>No backtest results for {symbol}.</b>"

    lines = [f"<b>Backtest: {symbol}</b>", ""]
    for r in results:
        name = r.get("strategy", "?")
        win_rate = r.get("win_rate", 0)
        trades = r.get("trades", 0)
        avg_ret = r.get("avg_return", 0)
        max_dd = r.get("max_drawdown", 0)
        lines.append(
            f"  <b>{name}</b>"
        )
        lines.append(
            f"    Win Rate: {win_rate:.0f}% ({r.get('wins', 0)}/{trades})"
        )
        lines.append(f"    Avg Ret:  {_pct_str(avg_ret)}")
        lines.append(f"    Max DD:   {_pct_str(max_dd)}")
        lines.append("")

    if results:
        best = max(results, key=lambda x: x.get("win_rate", 0))
        lines.append(f"<b>Best:</b> {best['strategy']} ({best.get('win_rate', 0):.0f}% WR)")

    return "\n".join(lines)


def format_history(signals):
    if not signals:
        return "<b>No signal history found.</b>"

    lines = [f"<b>Signal History ({len(signals)} signals)</b>", ""]
    for s in signals:
        created = s.get("created_at", "")[:16]
        verdict = s.get("verdict", "?")
        conf = s.get("confidence", 0)
        sym = s.get("symbol", "?")
        strat = s.get("strategy", "?")
        lines.append(
            f"  {created}  {sym:<6} {verdict:<4} {conf:3.0f}  {strat}"
        )
    return "\n".join(lines)


def format_profile(profile):
    if not profile:
        return "<b>No profile yet.</b>"

    lines = ["<b>Your Trading Profile</b>", ""]

    for key, val in profile.items():
        if isinstance(val, dict):
            lines.append(f"<b>{key.replace('_', ' ').title()}:</b>")
            for k, v in val.items():
                lines.append(f"  {k.replace('_', ' ').title()}: {v}")
        elif isinstance(val, list):
            lines.append(f"<b>{key.replace('_', ' ').title()}:</b>")
            for item in val:
                lines.append(f"  \u2022 {item}")
        else:
            lines.append(f"<b>{key.replace('_', ' ').title()}:</b> {val}")

    return "\n".join(lines)
