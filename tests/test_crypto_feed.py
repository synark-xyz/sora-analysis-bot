from unittest.mock import patch, MagicMock
import pytest
from data.crypto_feed import fetch_bars, BINANCE_SYMBOLS


def _make_kline(open_time_ms, o, h, l, c, v):
    return [open_time_ms, str(o), str(h), str(l), str(c), str(v),
            open_time_ms + 86399999, "0", 100, "0", "0", "0"]


def test_fetch_bars_returns_ohlcv_dicts():
    mock_klines = [_make_kline(1716000000000, 67000.0, 68000.0, 66000.0, 67500.0, 1234.5)]
    with patch("data.crypto_feed.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_klines
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        bars = fetch_bars("BTC", days=1)
    assert len(bars) == 1
    assert bars[0]["open"] == 67000.0
    assert bars[0]["high"] == 68000.0
    assert bars[0]["low"] == 66000.0
    assert bars[0]["close"] == 67500.0
    assert bars[0]["volume"] == 1234.5
    assert bars[0]["time"] == 1716000000


def test_fetch_bars_calls_correct_binance_symbol():
    with patch("data.crypto_feed.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        fetch_bars("ETH", days=90)
        params = mock_get.call_args[1]["params"]
    assert params["symbol"] == "ETHUSDT"
    assert params["interval"] == "1d"
    assert params["limit"] == 90


def test_fetch_bars_uses_binance_endpoint():
    with patch("data.crypto_feed.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        fetch_bars("BTC", days=1)
        url = mock_get.call_args[0][0]
    assert "binance.com" in url
    assert "klines" in url


def test_fetch_bars_unknown_symbol_returns_empty():
    bars = fetch_bars("UNKNOWN", days=90)
    assert bars == []


def test_fetch_bars_api_error_returns_empty():
    with patch("data.crypto_feed.requests.get") as mock_get:
        mock_get.side_effect = Exception("network error")
        bars = fetch_bars("BTC", days=90)
    assert bars == []


def test_binance_symbols_has_ten_entries():
    assert len(BINANCE_SYMBOLS) == 10
    assert BINANCE_SYMBOLS["BTC"] == "BTCUSDT"
    assert BINANCE_SYMBOLS["XRP"] == "XRPUSDT"
