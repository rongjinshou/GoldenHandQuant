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

