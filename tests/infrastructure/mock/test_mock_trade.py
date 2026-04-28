import pytest
from datetime import datetime
from src.infrastructure.mock.mock_trade import MockTradeGateway
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.domain.trade.value_objects.order_status import OrderStatus
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position

from src.domain.trade.exceptions import OrderSubmitError

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
        
        # Settle T+1 to make it available
        gateway.daily_settlement()
        
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
        # Actually my logic might mark it as PARTIAL_CANCELED if I implement it that way, or just PARTIAL_FILLED and let the rest hang?
        # The rule says "mark as PARTIAL_CANCELED" for the excess.
        # So status should be PARTIAL_CANCELED (if supported) or PARTIAL_FILLED with remaining canceled?
        # The enum has PARTIAL_CANCELED.
        
        assert order.traded_volume == 1000
        # Check position
        pos = gateway.get_position("600000.SH")
        assert pos.total_volume == 1000

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
        from src.domain.trade.value_objects.order_direction import OrderDirection
        from src.domain.trade.value_objects.order_type import OrderType
        from src.domain.trade.exceptions import OrderSubmitError
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
            order_id="TEST_001", account_id="MOCK_ACCOUNT", ticker="000001.SZ",
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

    def test_buy_partial_fill_overdraw_protection(self):
        """部分成交（容量限制）导致 diff 超过可用资金时，应触发熔断拒绝成交。"""
        from datetime import datetime
        from src.domain.market.value_objects.bar import Bar
        from src.domain.market.value_objects.timeframe import Timeframe
        from src.domain.trade.entities.order import Order
        from src.domain.trade.value_objects.order_direction import OrderDirection
        from src.domain.trade.value_objects.order_type import OrderType
        from src.domain.trade.exceptions import OrderSubmitError
        from src.infrastructure.mock.mock_market import MockMarketGateway
        from src.infrastructure.mock.mock_trade import MockTradeGateway

        market = MockMarketGateway()
        # 成交量只有 1000，容量限制 10% = 100 股
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 3),
                  open=10.0, high=10.0, low=10.0, close=10.0, volume=1000)
        market.add_bars("000001.SZ", [bar])
        market.set_current_time(datetime(2024, 1, 3))

        # 订单 500 股，但由于容量限制，只能成交 100 股
        # ratio = 100/500 = 0.2
        # exec_price = 10.0 * 1.001 = 10.01
        # total_cost for 100 shares: 1001 + 5 + 0.01 = 1006.01
        # 冻结: 1006.01
        # _simulate_fill: to_unfreeze = 1006.01 * 0.2 = 201.202
        # actual_cost = 1006.01
        # diff = 804.808
        # 如果初始资金刚好够 total_cost + 少量: available_cash after freeze = init - 1006.01
        # 需要: available_cash < diff 才能触发 overdraw
        # available_cash = 1500 - 1006.01 = 493.99 < 804.808 ✓
        gateway = MockTradeGateway(market, initial_capital=1500.0)

        order = Order(
            order_id="TEST_PARTIAL", account_id="MOCK_ACCOUNT", ticker="000001.SZ",
            direction=OrderDirection.BUY, price=10.0, volume=500, type=OrderType.LIMIT,
        )

        # 应该触发 OrderSubmitError 熔断
        with pytest.raises(OrderSubmitError, match="Overdraw prevented"):
            gateway.place_order(order)

        asset = gateway.get_asset()
        assert asset.available_cash >= 0, (
            f"Available cash is negative: {asset.available_cash}. Overdraw protection failed."
        )

    def test_limit_buy_below_low_should_be_rejected(self):
        """限价买单委托价低于当日最低价时，不应成交（市场从未交易到该价位）。"""
        from datetime import datetime
        from src.domain.market.value_objects.bar import Bar
        from src.domain.market.value_objects.timeframe import Timeframe
        from src.domain.trade.entities.order import Order
        from src.domain.trade.value_objects.order_direction import OrderDirection
        from src.domain.trade.value_objects.order_type import OrderType
        from src.domain.trade.value_objects.order_status import OrderStatus
        from src.domain.trade.exceptions import OrderSubmitError
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
            order_id="TEST_002", account_id="MOCK_ACCOUNT", ticker="000001.SZ",
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
        from src.domain.trade.value_objects.order_direction import OrderDirection
        from src.domain.trade.value_objects.order_type import OrderType
        from src.domain.trade.exceptions import OrderSubmitError
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
            order_id="TEST_003", account_id="MOCK_ACCOUNT", ticker="000001.SZ",
            direction=OrderDirection.SELL, price=60.0, volume=100, type=OrderType.LIMIT,
        )

        with pytest.raises(OrderSubmitError, match="limit price"):
            gateway.place_order(order)

