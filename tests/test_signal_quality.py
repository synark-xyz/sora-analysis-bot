import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# ── Task 2: R:R pre-gate ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rr_pregate_skips_llm_on_flatline():
    """When ATR/price < 0.003, _run_full_analysis returns HOLD without LLM call."""
    flat_indicators = {
        "price": 100.0,
        "atr_14": 0.2,          # 0.2% ATR — flatline
        "rsi_14": 50,
        "bb_upper": 100.5,
        "bb_lower": 99.5,
        "volume": 1000000,
        "avg_volume": 1000000,
        "vol_ratio_21d": 1.0,
        "adx": 15,
    }
    mock_regime = MagicMock()
    mock_regime.regime = "NEUTRAL"
    mock_regime.adx = 15

    with patch("engine.orchestrator._fetch_bars", return_value=[{"close": 100}] * 30), \
         patch("engine.orchestrator._compute_indicators", return_value=flat_indicators), \
         patch("engine.orchestrator.detect_regime", return_value=mock_regime), \
         patch("llm.analyst.analyze_full", new_callable=AsyncMock) as mock_llm:

        from engine.orchestrator import _run_full_analysis
        result = await _run_full_analysis("AAPL", "us")

    mock_llm.assert_not_called()
    assert result.get("verdict") == "HOLD"
    assert "LOW_ATR" in result.get("reason", "")

# ── Task 3: Volume 21-day ratio ───────────────────────────────────────────────

def _make_bars(n=60, price=100.0, volume=1_000_000):
    return [{"open": price, "high": price*1.01, "low": price*0.99,
             "close": price, "volume": volume} for _ in range(n)]

def test_volume_signal_strong_on_spike():
    """volume 3x average → volume_signal == 'strong'"""
    from engine.orchestrator import _compute_indicators
    bars = _make_bars(60, volume=1_000_000)
    bars[-1]["volume"] = 3_000_000  # 3x spike on last bar
    ind = _compute_indicators("AAPL", bars)
    assert ind["vol_ratio_21d"] >= 2.5
    assert ind["volume_signal"] == "strong"

def test_volume_signal_weak_on_low_volume():
    """volume 0.4x average → volume_signal == 'weak'"""
    from engine.orchestrator import _compute_indicators
    bars = _make_bars(60, volume=1_000_000)
    bars[-1]["volume"] = 400_000
    ind = _compute_indicators("AAPL", bars)
    assert ind["vol_ratio_21d"] < 0.6
    assert ind["volume_signal"] == "weak"

def test_volume_signal_neutral_on_normal():
    """volume ~1x average → volume_signal == 'neutral'"""
    from engine.orchestrator import _compute_indicators
    bars = _make_bars(60, volume=1_000_000)
    ind = _compute_indicators("AAPL", bars)
    assert ind["volume_signal"] == "neutral"

# ── Task 5: Historical signal injection ───────────────────────────────────────

def test_get_recent_signals_for_symbol_returns_list():
    """get_recent_signals_for_symbol returns list of dicts with required keys."""
    import db.store as store
    import tempfile, os
    # Use temp DB
    orig = store.DB_PATH
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp_path = f.name
    store.DB_PATH = tmp_path
    try:
        store.init_db()
        # Save a test signal
        store.save_signal({
            "symbol": "AAPL", "verdict": "BUY", "confidence": 80,
            "entry_low": 150.0, "entry_high": 152.0,
            "exit_target": 160.0, "stop_loss": 146.0,
            "rr_ratio": 2.0, "strategy": "test", "regime": "BULL",
            "reason": "test", "summary": "test signal",
        })
        results = store.get_recent_signals_for_symbol("AAPL", limit=5)
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["verdict"] == "BUY"
    finally:
        store.DB_PATH = orig
        os.unlink(tmp_path)


def test_format_signal_history_string():
    """format_signal_history returns a formatted string from signal list."""
    from db.store import format_signal_history
    signals = [
        {"verdict": "BUY", "confidence": 80, "created_at": "2026-05-20T10:00:00Z",
         "return_3d": 8.2, "return_7d": 12.1},
        {"verdict": "BUY", "confidence": 75, "created_at": "2026-05-10T10:00:00Z",
         "return_3d": -4.1, "return_7d": None},
    ]
    result = format_signal_history(signals)
    assert "BUY" in result
    assert "8.2%" in result
    assert "-4.1%" in result

# ── Task 6: Earnings guard wire-up ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_earnings_high_risk_forces_wait():
    """If earnings_risk == HIGH, synthesis prompt must include WAIT bias."""
    indicators = {
        "price": 150.0, "atr_14": 2.0, "rsi_14": 55,
        "bb_upper": 158.0, "bb_lower": 142.0,
        "volume": 5_000_000, "avg_volume": 4_000_000,
        "vol_ratio_21d": 1.25, "volume_signal": "neutral", "adx": 28,
    }
    mock_regime = MagicMock()
    mock_regime.regime = "BULL"
    mock_regime.adx = 28

    captured_messages = []

    async def mock_analyze_full(*args, **kwargs):
        captured_messages.append(kwargs)
        return {"verdict": "BUY", "confidence": 80}

    with patch("engine.orchestrator._fetch_bars", return_value=[{"close": 150}] * 30), \
         patch("engine.orchestrator._compute_indicators", return_value=indicators), \
         patch("engine.orchestrator.detect_regime", return_value=mock_regime), \
         patch("analysis.earnings.earnings_risk_flag", return_value="HIGH"), \
         patch("llm.analyst.analyze_full", side_effect=mock_analyze_full):

        from engine.orchestrator import _run_full_analysis
        await _run_full_analysis("AAPL", "us")

    # Check that earnings risk was injected into wiki_context
    assert len(captured_messages) == 1
    all_context = str(captured_messages[0])
    assert "earnings" in all_context.lower() or "HIGH" in all_context
