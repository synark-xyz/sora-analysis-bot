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
