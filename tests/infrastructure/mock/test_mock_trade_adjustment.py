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


def test_chinext_allows_15pct_move():
    market = MockMarketGateway()
    # 创业板,前一日收盘 10,当日买入价 11.5(涨 15%)。主板 10% 会拒,创业板 20% 应放行。
    market.add_bars("300750.SZ", [
        Bar(symbol="300750.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 2),
            open=10.0, high=10.0, low=10.0, close=10.0, volume=1_000_000),
        Bar(symbol="300750.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 3),
            open=11.5, high=12.0, low=11.0, close=11.5, volume=1_000_000),
    ])
    market.set_current_time(datetime(2024, 1, 3))
    gateway = MockTradeGateway(market, initial_capital=1_000_000.0)

    order = Order(order_id="B2", account_id=MockTradeGateway.DEFAULT_ACCOUNT_ID, ticker="300750.SZ",
                  direction=OrderDirection.BUY, price=11.5, volume=100, type=OrderType.LIMIT)
    gateway.place_order(order)  # 不应抛出涨停拒单
    assert gateway.get_position("300750.SZ").total_volume == 100


def test_no_phantom_pnl_from_adjustment_mismatch():
    """复权一致性金标准: 建仓时市值与成本差异仅限滑点+费用(<2%),无虚假浮亏。"""
    market = MockMarketGateway()
    # 前复权 close=10(用于估值),unadjusted_close=20(若误用则建仓即虚假浮亏 50%)
    bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 3),
              open=10.0, high=10.5, low=9.5, close=10.0, volume=1_000_000, unadjusted_close=20.0)
    market.add_bars("000001.SZ", [bar])
    market.set_current_time(datetime(2024, 1, 3))
    gateway = MockTradeGateway(market, initial_capital=1_000_000.0)

    order = Order(order_id="B3", account_id=MockTradeGateway.DEFAULT_ACCOUNT_ID, ticker="000001.SZ",
                  direction=OrderDirection.BUY, price=10.0, volume=100, type=OrderType.LIMIT)
    gateway.place_order(order)

    pos = gateway.get_position("000001.SZ")
    market_value = pos.total_volume * bar.close          # 前复权估值
    cost_basis = pos.total_volume * pos.average_cost     # 成交成本
    # 同口径下,二者差异仅滑点+费用(<2%);若成交用了 unadjusted_close 则差异约 50%
    assert abs(market_value - cost_basis) < market_value * 0.02
