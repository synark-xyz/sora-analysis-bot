from unittest.mock import patch, MagicMock
from analysis.breadth import get_market_breadth, breadth_context_str


def test_breadth_returns_dict_with_required_keys():
    with patch("analysis.breadth._fetch_spx_breadth_pct", return_value=42.5):
        result = get_market_breadth()
    assert "breadth_pct" in result
    assert "signal" in result


def test_breadth_signal_weak_below_40():
    with patch("analysis.breadth._fetch_spx_breadth_pct", return_value=35.0):
        result = get_market_breadth()
    assert result["signal"] == "weak"


def test_breadth_signal_strong_above_60():
    with patch("analysis.breadth._fetch_spx_breadth_pct", return_value=65.0):
        result = get_market_breadth()
    assert result["signal"] == "strong"


def test_breadth_signal_neutral_between():
    with patch("analysis.breadth._fetch_spx_breadth_pct", return_value=52.0):
        result = get_market_breadth()
    assert result["signal"] == "neutral"


def test_breadth_context_str_weak():
    b = {"breadth_pct": 35.0, "signal": "weak"}
    s = breadth_context_str(b)
    assert "35.0%" in s
    assert "weak" in s.lower()


def test_breadth_returns_none_signal_on_fetch_failure():
    with patch("analysis.breadth._fetch_spx_breadth_pct", return_value=None):
        result = get_market_breadth()
    assert result["breadth_pct"] is None
    assert result["signal"] == "unknown"
