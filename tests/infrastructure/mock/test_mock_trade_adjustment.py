from datetime import datetime

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway


def test_exec_price_follows_order_price_not_unadjusted_close():
    """成交价应使用 order.price (前复权) 而非 bar.unadjusted_close。"""
    market = MockMarketGateway()
    # 前复权 open/close = 10, 但 unadjusted_close = 20 (模拟回测后段有除权)
    bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 3),
              open=10.0, high=10.5, low=9.5, close=10.0, volume=1_000_000, unadjusted_close=20.0)
    market.add_bars("000001.SZ", [bar])
    market.set_current_time(datetime(2024, 1, 3))
    gateway = MockTradeGateway(market, initial_capital=1_000_000.0)

    order = Order(order_id="B1", account_id=MockTradeGateway.DEFAULT_ACCOUNT_ID, ticker="000001.SZ",
                  direction=OrderDirection.BUY, price=10.0, volume=100, type=OrderType.LIMIT)
    gateway.place_order(order)

    pos = gateway.get_position("000001.SZ")
    # 成交价应约 = order.price * 1.001 = 10.01 (前复权), 而非 unadjusted_close 20 * 1.001 = 20.02
    assert pos.average_cost < 11.0, f"成交价疑似用了不复权价: average_cost={pos.average_cost}"
