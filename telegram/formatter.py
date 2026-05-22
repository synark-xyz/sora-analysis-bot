def _html(text):
    if not isinstance(text, str):
        text = str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


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
    symbol = _html(signal.get("symbol", "?"))
    verdict = _html(signal.get("verdict", "HOLD"))
    confidence = signal.get("confidence", 0)
    label = _confidence_label(confidence)
    strategy = _html(signal.get("strategy", "—"))
    regime = _html(signal.get("regime", "—"))
    entry_low = signal.get("entry_low")
    entry_high = signal.get("entry_high")
    exit_target = signal.get("exit_target")
    stop_loss = signal.get("stop_loss")
    rr = signal.get("rr_ratio")
    reason = _html(signal.get("reason", ""))
    timeframe = signal.get("timeframe", "Swing (5\u201312 days)")
    is_full = signal.get("llm_report", False)

    tf_tag = "LONG-TERM" if "weeks" in str(timeframe) else ("FULL" if is_full else "SWING")

    entry_return = None
    if exit_target and entry_low:
        entry_return = ((exit_target - entry_low) / entry_low) * 100
    stop_return = None
    if stop_loss and entry_low:
        stop_return = ((stop_loss - entry_low) / entry_low) * 100

    lines = [
        f"<b>{'📊'} {symbol}  ·  {verdict} SIGNAL  [{tf_tag}]</b>",
        f"Confidence  {confidence:.0f} / 100  [{label}]",
        f"Strategy    {strategy}",
        f"Regime      {regime}",
        "",
    ]

    if entry_low is not None and entry_high is not None:
        lines.append(f"{'📍'} ENTRY ZONE    {_dollar(entry_low)} \u2013 {_dollar(entry_high)}")
        anchor = signal.get("entry_anchor")
        if anchor:
            lines.append(f"   Anchor: {_html(anchor)}")
    if exit_target is not None:
        lines.append(f"{'🎯'} EXIT TARGET   {_dollar(exit_target)}  ({_pct_str(entry_return)})")
        anchor = signal.get("exit_anchor")
        if anchor:
            lines.append(f"   Anchor: {_html(anchor)}")
    if stop_loss is not None:
        lines.append(f"{'🛑'} STOP LOSS     {_dollar(stop_loss)}  ({_pct_str(stop_return)})")
        anchor = signal.get("stop_anchor")
        if anchor:
            lines.append(f"   Anchor: {_html(anchor)}")
    if rr is not None:
        lines.append(f"{'⚖️'}  RISK / REWARD   1 : {rr:.1f}")
    lines.append(f"{'⏱'}  Timeframe        {_html(timeframe)}")

    tc = signal.get("tech_conditions")
    if tc:
        lines.append("")
        lines.append("TECHNICAL CONDITIONS")
        tc_map = {"rsi": "RSI", "stoch": "Stoch", "williams_r": "W%R", "bb": "BBands"}
        for key, label in tc_map.items():
            val = tc.get(key, "neutral")
            emoji = {"severely-oversold": "🔴", "oversold": "🟠", "overbought": "🟠", "severely-overbought": "🔴", "neutral": "🟢"}.get(val, "⚪")
            lines.append(f"  {label:<8} {emoji} {val}")
        overall = tc.get("overall", "")
        if overall and overall != "neutral":
            emoji = {"extreme": "🔥", "oversold": "📉", "overbought": "📈", "mixed": "⚡"}.get(overall, "⚪")
            lines.append(f"  {'Overall':<8} {emoji} {overall}")

    conf_breakdown = signal.get("confidence_breakdown") or signal.get("breakdown")
    if conf_breakdown:
        lines.append("")
        lines.append("CONFIDENCE BREAKDOWN")
        if isinstance(conf_breakdown, dict):
            for key, value in conf_breakdown.items():
                score = value if isinstance(value, (int, float)) else value.get("score", 0)
                name = key.replace("_", " ").title()
                lines.append(f"  {name:<20} {format_confidence_bar(score)}  {score:.0f}%")
        elif isinstance(conf_breakdown, list):
            for dim in conf_breakdown:
                if isinstance(dim, dict):
                    name = dim.get("name", "?")
                    score = dim.get("score", 0)
                    lines.append(f"  {name:<20} {format_confidence_bar(score)}  {score:.0f}%")
                elif isinstance(dim, (list, tuple)):
                    lines.append(f"  {dim[0]:<20} {format_confidence_bar(dim[1])}  {dim[1]:.0f}%")

    gate_scorecard = signal.get("gate_scorecard")
    gate_passed = signal.get("gate_passed")
    if gate_scorecard:
        lines.append("")
        header = "SIGNAL GATE  \u2713 PASSED" if gate_passed else "SIGNAL GATE  \u2717 BLOCKED"
        lines.append(f"<b>{header}</b>")
        for line in gate_scorecard.splitlines():
            lines.append(f"  {_html(line)}")

    rules = signal.get("rules_check") or signal.get("rules")
    if rules and rules not in ("all passed", "all passed or violations"):
        lines.append("")
        lines.append(f"Your rules: {_html(rules)}")

    if not is_full and "long" in str(timeframe).lower():
        try:
            from analysis.fundamental import get_fundamentals
            f = get_fundamentals(symbol)
            if f:
                pe = f.get("pe_ratio", f.get("P/E", ""))
                rev = f.get("revenue_growth", f.get("revGrowth", ""))
                insider = f.get("insider_transactions", "")
                parts = []
                if rev:
                    parts.append(f"Rev growth {_html(str(rev))}")
                if pe:
                    parts.append(f"P/E {_html(str(pe))}")
                if insider:
                    parts.append(f"Insider: {_html(str(insider))}")
                if parts:
                    lines.append("")
                    lines.append("Fundamentals: " + " \u00b7 ".join(parts))
        except Exception:
            pass

    if is_full:
        bull = signal.get("bull_thesis", "")
        bear = signal.get("bear_thesis", "")
        catalysts = signal.get("key_catalysts", [])
        risks = signal.get("key_risks", [])
        if bull:
            lines.append("")
            lines.append(f"{'🤖'} <b>Bull Case:</b> {_html(bull[:300])}")
        if bear:
            lines.append("")
            lines.append(f"{'🐻'} <b>Bear Case:</b> {_html(bear[:300])}")
        if catalysts:
            items = [_html(str(c)[:80]) for c in catalysts[:3]]
            lines.append("")
            lines.append(f"{'🔥'} Catalysts: {' | '.join(items)}")
        if risks:
            items = [_html(str(r)[:80]) for r in risks[:3]]
            lines.append("")
            lines.append(f"{'⚠️'} Risks: {' | '.join(items)}")

    is_moomoo = signal.get("moomoo_report", False)
    if is_moomoo:
        es = signal.get("executive_summary", "")
        if es:
            lines.append("")
            lines.append(f"{'📋'} <b>Executive Summary</b>")
            lines.append(f"  {_html(es)}")

        va = signal.get("valuation_assessment", {})
        if va:
            verdict = va.get("verdict", "")
            metrics = va.get("key_metrics", "")
            fve = va.get("fair_value_estimate", "")
            lines.append("")
            lines.append(f"{'💰'} <b>Valuation Assessment</b>")
            if verdict:
                emoji = {"undervalued": "🟢", "fair": "🟡", "overvalued": "🔴"}.get(verdict, "⚪")
                lines.append(f"  Verdict: {emoji} {verdict}")
            if metrics:
                lines.append(f"  {_html(metrics[:200])}")
            if fve:
                lines.append(f"  Fair Value: {_html(fve[:100])}")

        entry_strat = signal.get("entry_strategy", {})
        if entry_strat:
            lines.append("")
            lines.append(f"{'🎯'} <b>Entry Strategy</b>")
            tz = entry_strat.get("tactical_zone", {})
            vz = entry_strat.get("value_zone", {})
            scale = entry_strat.get("scale_in_plan", "")
            if tz and tz.get("price"):
                lines.append(f"  Tactical: ${tz['price']:.2f} — {_html(tz.get('reason', '')[:100])}")
            if vz and vz.get("price"):
                lines.append(f"  Value:    ${vz['price']:.2f} — {_html(vz.get('reason', '')[:100])}")
            if scale:
                lines.append(f"  Scale: {_html(scale[:150])}")

        rm = signal.get("risk_management", {})
        if rm:
            lines.append("")
            lines.append(f"{'🛡️'} <b>Risk Management</b>")
            stop_type = rm.get("stop_loss_type", "")
            pos_size = rm.get("position_sizing", "")
            mos = rm.get("margin_of_safety_pct", 0)
            if stop_type:
                lines.append(f"  Stop Type: {stop_type}")
            if mos:
                lines.append(f"  Margin of Safety: {mos:.0f}%")
            if pos_size:
                lines.append(f"  Sizing: {_html(pos_size[:150])}")

        catalysts = signal.get("monitoring_catalysts", [])
        if catalysts:
            items = [_html(str(c)[:80]) for c in catalysts[:4]]
            lines.append("")
            lines.append(f"{'📅'} Catalysts to Watch: {' | '.join(items)}")

        fb = signal.get("moomoo_framework_breakdown", {})
        if fb:
            lines.append("")
            lines.append(f"{'🧠'} <b>Framework Breakdown</b>")
            for step_key, step_label in [
                ("step1_objective", "Objective"),
                ("step3_fundamental_verdict", "Fundamental"),
                ("step3_valuation_verdict", "Valuation"),
                ("step3_technical_verdict", "Technical"),
                ("step4_synthesis", "Synthesis"),
            ]:
                val = fb.get(step_key, "")
                if val:
                    lines.append(f"  {step_label}: {_html(val[:150])}")

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
    return """<b>Sora Bot v2 — Commands</b>

<b>Analysis</b>
  /analyze SYMBOL        Quick signal (technical, ~30s)
  /analyze SYMBOL -full  Deep report (~90s)
  /analyze SYMBOL -mm    Moomoo framework (5-step methodology)
  /analyze SYMBOL -swing Force swing timeframe
  /analyze SYMBOL -long  Force long-term

<b>Watchlist</b>
  /watchlist -add SYMBOL    Add symbol
  /watchlist -remove SYMBOL Remove symbol
  /watchlist -ls            List all

<b>Positions</b>
  /position -add SYMBOL PRICE [QTY] [sl:X] [tp:X]
  /position -ls             List open positions
  /position -close SYMBOL   Close position

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


def format_positions(positions):
    if not positions:
        return "<b>No open positions.</b>\n\nAdd one: /position -add SYMBOL PRICE [sl:X] [tp:X]"

    lines = [f"<b>Open Positions ({len(positions)})</b>", ""]
    for p in positions:
        sym = _html(p["symbol"])
        entry = p.get("entry_price", 0)
        sl = p.get("stop_loss")
        tp = p.get("take_profit")
        qty = p.get("qty")
        taken = (p.get("taken_at") or "")[:10]

        header = f"<b>{sym}</b>"
        if qty:
            header += f"  ×{qty}"
        lines.append(header)
        lines.append(f"  Entry:  ${entry:.2f}  [{taken}]")
        if sl:
            pct_sl = (sl - entry) / entry * 100
            lines.append(f"  SL:     ${sl:.2f}  ({_pct_str(pct_sl)})")
        if tp:
            pct_tp = (tp - entry) / entry * 100
            lines.append(f"  TP:     ${tp:.2f}  ({_pct_str(pct_tp)})")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_sl_alert(position, current_price: float, pct_from_sl: float, hit: bool = False):
    sym = _html(position["symbol"])
    entry = position.get("entry_price", 0)
    sl = position.get("stop_loss", 0)
    pct_entry = (current_price - entry) / entry * 100 if entry else 0

    if hit:
        return (
            f"🛑 <b>STOP LOSS HIT: {sym}</b>\n"
            f"Price: ${current_price:.2f}  |  SL: ${sl:.2f}\n"
            f"P&L from entry: {_pct_str(pct_entry)}\n"
            f"Position auto-closed."
        )
    return (
        f"⚠️ <b>SL WARNING: {sym}</b>\n"
        f"Price ${current_price:.2f} is {pct_from_sl:.1f}% above SL ${sl:.2f}\n"
        f"P&L from entry: {_pct_str(pct_entry)}"
    )


def format_news_alert(symbol: str, title: str, url: str = ""):
    sym = _html(symbol)
    headline = _html(title)
    if url:
        return f"📰 <b>{sym}</b>: {headline}\n<a href=\"{url}\">Read more</a>"
    return f"📰 <b>{sym}</b>: {headline}"


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
