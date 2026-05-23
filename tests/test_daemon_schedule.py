import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime
from zoneinfo import ZoneInfo
from scheduler.daemon import Daemon, ET


class _FixedDatetime:
    _fixed: datetime

    @classmethod
    def now(cls, tz=None):
        return cls._fixed


@pytest.fixture
def daemon():
    d = Daemon()
    d._run_us_scan = AsyncMock()
    d._run_crypto_scan = AsyncMock()
    d._run_position_scan = AsyncMock()
    d._run_news_scan = AsyncMock()
    d._run_weekly_review = AsyncMock()
    return d


async def tick_at(daemon, dt: datetime):
    _FixedDatetime._fixed = dt
    with patch("scheduler.daemon.datetime", _FixedDatetime):
        await daemon._tick()


async def test_preclose_fires_at_15_00(daemon):
    await tick_at(daemon, datetime(2026, 5, 26, 15, 0, 5, tzinfo=ET))
    daemon._run_us_scan.assert_called_once_with("us_preclose")


async def test_postopen_not_fired(daemon):
    await tick_at(daemon, datetime(2026, 5, 26, 9, 50, 5, tzinfo=ET))
    daemon._run_us_scan.assert_not_called()


async def test_midday_not_fired(daemon):
    await tick_at(daemon, datetime(2026, 5, 26, 11, 59, 5, tzinfo=ET))
    daemon._run_us_scan.assert_not_called()


async def test_premarket_still_fires(daemon):
    await tick_at(daemon, datetime(2026, 5, 26, 8, 30, 5, tzinfo=ET))
    daemon._run_us_scan.assert_called_once_with("us_premarket")


async def test_crypto_scan_blocked_on_weekend(daemon):
    await tick_at(daemon, datetime(2026, 5, 23, 0, 0, 5, tzinfo=ET))
    daemon._run_crypto_scan.assert_not_called()


async def test_crypto_scan_fires_on_weekday(daemon):
    await tick_at(daemon, datetime(2026, 5, 26, 0, 0, 5, tzinfo=ET))
    daemon._run_crypto_scan.assert_called_once()
