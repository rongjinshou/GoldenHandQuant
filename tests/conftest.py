import pytest
from datetime import datetime
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position


@pytest.fixture
def sample_bar():
    return Bar(
        symbol="000001.SZ",
        timeframe=Timeframe.DAY_1,
        timestamp=datetime(2024, 1, 3),
        open=10.0, high=10.5, low=9.8, close=10.2, volume=50000,
        unadjusted_close=10.2,
    )


@pytest.fixture
def sample_asset():
    return Asset(
        account_id="TEST_ACCOUNT",
        total_asset=100000.0,
        available_cash=100000.0,
        frozen_cash=0.0,
    )


@pytest.fixture
def sample_position():
    return Position(
        account_id="TEST_ACCOUNT",
        ticker="000001.SZ",
        total_volume=500,
        available_volume=500,
        average_cost=10.0,
    )


@pytest.fixture
def multi_day_bars():
    """生成 20 根连续上涨的日线 Bar。"""
    bars = []
    for i in range(20):
        price = 10.0 + i * 0.1
        bars.append(Bar(
            symbol="000001.SZ",
            timeframe=Timeframe.DAY_1,
            timestamp=datetime(2024, 1, 2 + i),
            open=price, high=price + 0.1, low=price - 0.1, close=price + 0.05,
            volume=100000,
            unadjusted_close=price + 0.05,
        ))
    return bars
