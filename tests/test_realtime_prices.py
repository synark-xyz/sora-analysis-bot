from unittest.mock import patch, MagicMock
import pytest
from scheduler.daemon import _get_current_price


def test_us_price_calls_finnhub(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test_key")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"c": 178.5, "o": 177.0, "h": 179.0, "l": 177.0, "pc": 177.3}
        mock_get.return_value = mock_resp
        price = _get_current_price("AAPL", "us")
    assert price == 178.5
    url = mock_get.call_args[0][0]
    params = mock_get.call_args[1]["params"]
    assert "finnhub.io" in url
    assert params["symbol"] == "AAPL"
    assert params["token"] == "test_key"


def test_us_price_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    price = _get_current_price("AAPL", "us")
    assert price is None


def test_us_price_returns_none_when_finnhub_returns_zero(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test_key")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"c": 0, "o": 0}
        mock_get.return_value = mock_resp
        price = _get_current_price("AAPL", "us")
    assert price is None


def test_us_price_returns_none_on_exception(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test_key")
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("timeout")
        price = _get_current_price("AAPL", "us")
    assert price is None


def test_crypto_price_calls_binance():
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"symbol": "BTCUSDT", "price": "67234.56"}
        mock_get.return_value = mock_resp
        price = _get_current_price("BTC", "crypto")
    assert price == 67234.56
    url = mock_get.call_args[0][0]
    params = mock_get.call_args[1]["params"]
    assert "binance.com" in url
    assert params["symbol"] == "BTCUSDT"


def test_crypto_price_unknown_symbol_returns_none():
    price = _get_current_price("UNKNOWN", "crypto")
    assert price is None


def test_crypto_price_returns_none_on_exception():
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("timeout")
        price = _get_current_price("BTC", "crypto")
    assert price is None
