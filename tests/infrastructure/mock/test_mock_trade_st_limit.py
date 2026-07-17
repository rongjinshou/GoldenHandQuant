"""ST 日 ±5% 撮合闸(DD-6 主体): 带注册表拒 6% 买单, 无注册表按 ±10% 放行。"""
from datetime import datetime

import pytest

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.suspension import StockStatus, StockStatusRegistry
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.trade.entities.order import Order
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway

D1, D2 = datetime(2023, 1, 2), datetime(2023, 1, 3)


def _bar(ts, px):
    return Bar(symbol="000021.SZ", timeframe=Timeframe.DAY_1, timestamp=ts,
               open=px, high=px * 1.06, low=px * 0.95, close=px, volume=1_000_000.0)


@pytest.fixture
def market():
    gw = MockMarketGateway()
    gw.add_bars("000021.SZ", [_bar(D1, 10.0), _bar(D2, 10.6)])
    gw.set_current_time(D2)
    return gw


def _buy(price):
    return Order(order_id="t1", account_id="MOCK_ACCOUNT", ticker="000021.SZ",
                 direction=OrderDirection.BUY, price=price, volume=100,
                 type=OrderType.LIMIT)


def test_st_day_rejects_buy_beyond_5pct(market):
    registry = StockStatusRegistry()
    registry.add(StockStatus(symbol="000021.SZ", date=D2, is_st=True))
    gw = MockTradeGateway(market_gateway=market, initial_capital=1_000_000.0,
                          stock_status_registry=registry)
    # prev_close 10.0, ST 限 10.5, exec 10.6*1.001 超限
    with pytest.raises(OrderSubmitError, match="limit up"):
        gw.place_order(_buy(10.6))


def test_without_registry_same_order_passes_10pct(market):
    gw = MockTradeGateway(market_gateway=market, initial_capital=1_000_000.0)
    order_id = gw.place_order(_buy(10.6))  # 普通限 11.0, 放行
    assert order_id
