from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from analysis.earnings import days_to_earnings, earnings_risk_flag


def test_days_to_earnings_returns_int_when_date_available():
    future = datetime.now(timezone.utc) + timedelta(days=3, hours=6)
    with patch("analysis.earnings._fetch_earnings_date", return_value=future):
        result = days_to_earnings("AAPL")
    assert result == 3  # days=3 + hours=6 ensures floor(days) == 3


def test_days_to_earnings_returns_none_when_no_date():
    with patch("analysis.earnings._fetch_earnings_date", return_value=None):
        result = days_to_earnings("AAPL")
    assert result is None


def test_earnings_risk_flag_high_within_5_days():
    with patch("analysis.earnings.days_to_earnings", return_value=3):
        assert earnings_risk_flag("AAPL") == "HIGH"


def test_earnings_risk_flag_low_beyond_5_days():
    with patch("analysis.earnings.days_to_earnings", return_value=10):
        assert earnings_risk_flag("AAPL") == "LOW"


def test_earnings_risk_flag_low_when_no_date():
    with patch("analysis.earnings.days_to_earnings", return_value=None):
        assert earnings_risk_flag("AAPL") == "LOW"
