from datetime import datetime

import pytest

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.trade.entities.order import Order
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_status import OrderStatus
from src.domain.trade.value_objects.order_type import OrderType
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway


class TestMockTradeGatewayNewRules:

    @pytest.fixture
    def market(self):
        # Create a mock market with one bar
        gateway = MockMarketGateway()
        bar = Bar(
            symbol="600000.SH",
            timeframe=Timeframe.DAY_1,
            timestamp=datetime(2023, 1, 1),
            open=10.0,
            high=10.5,
            low=9.5,
            close=10.0,
            volume=10000.0  # Total volume
        )
        gateway.add_bars("600000.SH", [bar])
        gateway.set_current_time(datetime(2023, 1, 1))
        return gateway

    @pytest.fixture
    def gateway(self, market):
        initial_capital = 1_000_000.0
        return MockTradeGateway(market_gateway=market, initial_capital=initial_capital)

    def test_buy_cost_calculation(self, gateway, market):
        """Test buy cost: Price * 1.001 (slippage) + Commission + Transfer Fee"""
        # Arrange
        # Price 10.0 -> Exec Price 10.01
        # Volume 100
        # Amount = 1001.0
        # Commission = max(1001 * 0.00025, 5.0) = 5.0
        # Transfer Fee = 1001 * 0.00001 = 0.01001
        # Total Cost = 1001 + 5.0 + 0.01001 = 1006.01001

        order = Order(
            order_id="buy_1",
            account_id="test",
            ticker="600000.SH",
            direction=OrderDirection.BUY,
            type=OrderType.MARKET,
            volume=100,
            price=10.0  # Reference price
        )

        # Act
        gateway.place_order(order)

        # Assert
        assert order.status == OrderStatus.FILLED
        assert gateway.asset.available_cash < 1_000_000 - 1000
        # Check precise deduction
        expected_cost = 10.0 * 1.001 * 100 + 5.0 + (10.0 * 1.001 * 100 * 0.00001)
        assert abs((1_000_000 - gateway.asset.available_cash) - expected_cost) < 0.01

    def test_sell_cost_calculation(self, gateway, market):
        """Test sell cost: Price * 0.999 (slippage) - Commission - Transfer Fee - Stamp Duty"""
        # Arrange: Setup position
        # Buy 100 shares first
        buy_order = Order(
            order_id="buy_1",
            account_id="test",
            ticker="600000.SH",
            direction=OrderDirection.BUY,
            type=OrderType.MARKET,
            volume=100,
            price=10.0
        )
        gateway.place_order(buy_order)

        # Settle T+1 to make it available(桩方法已删, 生产走 DailySettlementService;
        # 此处直接对持仓做 T+1 释放, 语义等价)
        for pos in gateway.positions.values():
            pos.settle_t_plus_1()

        initial_cash = gateway.asset.available_cash

        # Sell 100 shares
        # Price 10.0 -> Exec Price 9.99
        # Amount = 999.0
        # Commission = max(999 * 0.00025, 5.0) = 5.0
        # Transfer Fee = 999 * 0.00001 = 0.00999
        # Stamp Duty = 999 * 0.0005 = 0.4995
        # Net Income = 999 - 5.0 - 0.00999 - 0.4995 = 993.49051

        sell_order = Order(
            order_id="sell_1",
            account_id="test",
            ticker="600000.SH",
            direction=OrderDirection.SELL,
            type=OrderType.MARKET,
            volume=100,
            price=10.0
        )

        # Act
        gateway.place_order(sell_order)

        # Assert
        assert sell_order.status == OrderStatus.FILLED
        expected_income = (10.0 * 0.999 * 100) - 5.0 - (10.0 * 0.999 * 100 * 0.00001) - (10.0 * 0.999 * 100 * 0.0005)
        assert abs((gateway.asset.available_cash - initial_cash) - expected_income) < 0.01

    def test_capacity_limit(self, gateway, market):
        """Test volume limit: max 10% of bar volume"""
        # Bar volume is 10000. Max order volume = 1000.
        # Order 1500 -> Should fill 1000, cancel 500

        order = Order(
            order_id="buy_cap",
            account_id="test",
            ticker="600000.SH",
            direction=OrderDirection.BUY,
            type=OrderType.MARKET,
            volume=1500,
            price=10.0
        )

        # Act
        gateway.place_order(order)

        # Assert
        assert order.status == OrderStatus.PARTIAL_CANCELED
        # Actually my logic might mark it as PARTIAL_CANCELED if I implement it that way,
        # or just PARTIAL_FILLED and let the rest hang?
        # The rule says "mark as PARTIAL_CANCELED" for the excess.
        # So status should be PARTIAL_CANCELED (if supported) or PARTIAL_FILLED with remaining canceled?
        # The enum has PARTIAL_CANCELED.

        assert order.traded_volume == 1000
        # Check position
        pos = gateway.get_position("600000.SH")
        assert pos.total_volume == 1000

        # 资金正确性回归(2026-07-05 confirmed-bug): 容量限制部分成交后, 冻结资金必须
        # 全额释放、不留残留——该订单终态是 PARTIAL_CANCELED, 不在任何后续撤单/日终解冻
        # 扫描范围内, 一旦有残留就永久卡死, 可用资金被永久低估。
        asset = gateway.asset
        assert asset.frozen_cash == pytest.approx(0.0), (
            f"部分成交后应无残留冻结资金, 实际 frozen_cash={asset.frozen_cash}"
        )

    def test_t_plus_1_rule(self, gateway, market):
        """Test T+1: Cannot sell on same day"""
        # Buy 100
        buy_order = Order(
            order_id="buy_t1",
            account_id="test",
            ticker="600000.SH",
            direction=OrderDirection.BUY,
            type=OrderType.MARKET,
            volume=100,
            price=10.0
        )
        gateway.place_order(buy_order)

        # Try to Sell immediately (without settlement)
        sell_order = Order(
            order_id="sell_t1",
            account_id="test",
            ticker="600000.SH",
            direction=OrderDirection.SELL,
            type=OrderType.MARKET,
            volume=100,
            price=10.0
        )

        # Act & Assert
        # Should raise OrderSubmitError
        with pytest.raises(OrderSubmitError):
            gateway.place_order(sell_order)

        assert sell_order.status == OrderStatus.REJECTED

    def test_buy_with_extreme_slippage_should_not_overdraw_cash(self):
        """极端滑点导致实际成本超过冻结资金时，不应导致可用资金为负。"""
        from datetime import datetime

        from src.domain.market.value_objects.bar import Bar
        from src.domain.market.value_objects.timeframe import Timeframe
        from src.domain.trade.entities.order import Order
        from src.domain.trade.exceptions import OrderSubmitError
        from src.domain.trade.value_objects.order_direction import OrderDirection
        from src.domain.trade.value_objects.order_type import OrderType
        from src.infrastructure.mock.mock_market import MockMarketGateway
        from src.infrastructure.mock.mock_trade import MockTradeGateway

        market = MockMarketGateway()
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 3),
                  open=10.0, high=10.0, low=10.0, close=10.0, volume=100000)
        market.add_bars("000001.SZ", [bar])
        market.set_current_time(datetime(2024, 1, 3))

        # 初始资金仅够刚好支付 (极度紧张)
        gateway = MockTradeGateway(market, initial_capital=10050.0)

        # 人工放大滑点率以模拟极端情况
        gateway.SLIPPAGE_BUY = 0.05  # 5% 滑点，远超正常水平

        order = Order(
            order_id="TEST_001", account_id=MockTradeGateway.DEFAULT_ACCOUNT_ID, ticker="000001.SZ",
            direction=OrderDirection.BUY, price=10.0, volume=1000, type=OrderType.LIMIT,
        )

        try:
            gateway.place_order(order)
        except OrderSubmitError:
            pass  # 若因资金不足拒单，这是正确行为

        asset = gateway.get_asset()
        assert asset.available_cash >= 0, (
            f"Available cash is negative: {asset.available_cash}. Overdraw protection failed."
        )

    def test_buy_partial_fill_with_tight_capital_settles_cleanly(self):
        """容量限制部分成交 + 资金紧张场景: 应干净成交, 不应误触发"Overdraw prevented"熔断。

        2026-07-05 confirmed-bug 回归测试(本测试此前名为
        test_buy_partial_fill_overdraw_protection, 断言过熔断*应该*触发——那其实是把
        双重折算 bug 的症状断言成了"期望行为"): _simulate_fill 里 frozen_amount 已经是
        按本次实际成交量(fill_volume)算出的成本, 之前代码又按 fill_volume/order.volume
        比例二次折算 to_unfreeze, 导致部分成交时只解冻了一小部分该解冻的资金, 从而人为
        制造出一个本不存在的 diff, 在资金本来够用的场景下错误拒单。修复后 diff 恒为 0,
        这个熔断分支在容量限制路径上已不可能触发(可用资金检查已在冻结前的 line 198 做过)。
        """
        from datetime import datetime

        from src.domain.market.value_objects.bar import Bar
        from src.domain.market.value_objects.timeframe import Timeframe
        from src.domain.trade.entities.order import Order
        from src.domain.trade.value_objects.order_direction import OrderDirection
        from src.domain.trade.value_objects.order_status import OrderStatus
        from src.domain.trade.value_objects.order_type import OrderType
        from src.infrastructure.mock.mock_market import MockMarketGateway
        from src.infrastructure.mock.mock_trade import MockTradeGateway

        market = MockMarketGateway()
        # 成交量只有 1000，容量限制 10% = 100 股
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 3),
                  open=10.0, high=10.0, low=10.0, close=10.0, volume=1000)
        market.add_bars("000001.SZ", [bar])
        market.set_current_time(datetime(2024, 1, 3))

        # 订单 500 股，但由于容量限制，只能成交 100 股
        # exec_price = 10.0 * 1.001 = 10.01
        # total_cost(100股) = 1001 + max(1001*0.00025, 5.0) + 1001*0.00001 = 1006.01001
        # 初始资金刚好紧巴巴够付这 100 股的真实成本 + 一点点余量
        # available_cash = 1500 - 1006.01001 = 493.98999 (>= 0, 真实可承受)
        gateway = MockTradeGateway(market, initial_capital=1500.0)

        order = Order(
            order_id="TEST_PARTIAL", account_id=MockTradeGateway.DEFAULT_ACCOUNT_ID, ticker="000001.SZ",
            direction=OrderDirection.BUY, price=10.0, volume=500, type=OrderType.LIMIT,
        )

        # 不应抛出任何异常——资金真实够付这 100 股
        gateway.place_order(order)

        assert order.status == OrderStatus.PARTIAL_CANCELED
        assert order.traded_volume == 100

        asset = gateway.get_asset()
        assert asset.available_cash == pytest.approx(1500.0 - 1006.01001, abs=0.01)
        assert asset.frozen_cash == pytest.approx(0.0), (
            f"部分成交后应无残留冻结资金, 实际 frozen_cash={asset.frozen_cash}"
        )
        assert asset.available_cash >= 0

    def test_limit_buy_below_low_should_be_rejected(self):
        """限价买单委托价低于当日最低价时，不应成交（市场从未交易到该价位）。"""
        from datetime import datetime

        from src.domain.market.value_objects.bar import Bar
        from src.domain.market.value_objects.timeframe import Timeframe
        from src.domain.trade.entities.order import Order
        from src.domain.trade.exceptions import OrderSubmitError
        from src.domain.trade.value_objects.order_direction import OrderDirection
        from src.domain.trade.value_objects.order_type import OrderType
        from src.infrastructure.mock.mock_market import MockMarketGateway
        from src.infrastructure.mock.mock_trade import MockTradeGateway

        market = MockMarketGateway()
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 3),
                  open=10.0, high=11.0, low=9.5, close=10.5, volume=100000)
        market.add_bars("000001.SZ", [bar])
        market.set_current_time(datetime(2024, 1, 3))

        gateway = MockTradeGateway(market, initial_capital=100000.0)

        # 限价 9.0 买入，但当日最低价 9.5 → 无法成交（市场从未跌到 9.0）
        order = Order(
            order_id="TEST_002", account_id=MockTradeGateway.DEFAULT_ACCOUNT_ID, ticker="000001.SZ",
            direction=OrderDirection.BUY, price=9.0, volume=100, type=OrderType.LIMIT,
        )

        with pytest.raises(OrderSubmitError, match="limit price"):
            gateway.place_order(order)

    def test_limit_sell_below_low_should_be_rejected(self):
        """限价卖单委托价低于当日最低价时，不应成交。"""
        from datetime import datetime

        from src.domain.market.value_objects.bar import Bar
        from src.domain.market.value_objects.timeframe import Timeframe
        from src.domain.trade.entities.order import Order
        from src.domain.trade.exceptions import OrderSubmitError
        from src.domain.trade.value_objects.order_direction import OrderDirection
        from src.domain.trade.value_objects.order_type import OrderType
        from src.infrastructure.mock.mock_market import MockMarketGateway
        from src.infrastructure.mock.mock_trade import MockTradeGateway

        market = MockMarketGateway()
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 3),
                  open=50.0, high=55.0, low=48.0, close=50.0, volume=100000)
        market.add_bars("000001.SZ", [bar])
        market.set_current_time(datetime(2024, 1, 3))

        gateway = MockTradeGateway(market, initial_capital=100000.0)
        from unittest.mock import MagicMock
        gateway.positions["000001.SZ"] = MagicMock()
        gateway.positions["000001.SZ"].available_volume = 200

        order = Order(
            order_id="TEST_003", account_id=MockTradeGateway.DEFAULT_ACCOUNT_ID, ticker="000001.SZ",
            direction=OrderDirection.SELL, price=60.0, volume=100, type=OrderType.LIMIT,
        )

        with pytest.raises(OrderSubmitError, match="limit price"):
            gateway.place_order(order)

    # --- R1: ITradeGateway 契约补全 (is_dry_run / query_order_status / cancel_order) ---

    @pytest.fixture
    def filled_order_id(self, gateway, market):
        """经 gateway.place_order 同步撮合成交后的订单 id。"""
        order = Order(
            order_id="filled_1",
            account_id="test",
            ticker="600000.SH",
            direction=OrderDirection.BUY,
            type=OrderType.MARKET,
            volume=100,
            price=10.0,
        )
        gateway.place_order(order)
        assert order.status == OrderStatus.FILLED
        return order.order_id

    def test_is_dry_run_true(self, gateway):
        assert gateway.is_dry_run is True

    def test_query_order_status_returns_status_of_known_order(self, filled_order_id, gateway):
        assert gateway.query_order_status(filled_order_id) == "FILLED"

    def test_query_order_status_unknown_returns_none(self, gateway):
        assert gateway.query_order_status("nonexistent") is None

    def test_cancel_order_returns_false_no_open_orders(self, filled_order_id, gateway):
        # Mock 同步撮合, 提交即终态, 无挂单可撤
        assert gateway.cancel_order(filled_order_id) is False

