import pytest
from unittest.mock import MagicMock
from datetime import datetime
from src.application.trading_app import TradingAppService
from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway
from src.domain.trade.interfaces.gateways.trade_gateway import ITradeGateway
from src.domain.strategy.services.base_strategy import BaseStrategy
from src.domain.market.value_objects.bar import Bar
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection

class TestTradingAppService:
    @pytest.fixture
    def mock_market_gateway(self):
        return MagicMock(spec=IMarketGateway)

    @pytest.fixture
    def mock_account_gateway(self):
        return MagicMock(spec=IAccountGateway)

    @pytest.fixture
    def mock_trade_gateway(self):
        return MagicMock(spec=ITradeGateway)

    @pytest.fixture
    def mock_strategy(self):
        return MagicMock(spec=BaseStrategy)

    @pytest.fixture
    def app_service(self, mock_market_gateway, mock_account_gateway, mock_trade_gateway, mock_strategy):
        return TradingAppService(
            market_gateway=mock_market_gateway,
            account_gateway=mock_account_gateway,
            trade_gateway=mock_trade_gateway,
            strategy=mock_strategy
        )

    def test_run_cycle_should_place_order_when_signal_generated(
        self, app_service, mock_market_gateway, mock_account_gateway, mock_trade_gateway, mock_strategy
    ):
        # Arrange
        symbol = "600000.SH"
        
        # 1. Mock Market Data
        bar = Bar(
            symbol=symbol,
            timestamp=datetime.now(),
            open=10.0, high=11.0, low=9.0, close=10.0, volume=1000
        )
        mock_market_gateway.get_recent_bars.return_value = [bar]

        # 2. Mock Account Data
        asset = Asset(account_id="acc1", total_asset=100000.0, available_cash=50000.0)
        mock_account_gateway.get_asset.return_value = asset
        mock_account_gateway.get_positions.return_value = []

        # 3. Mock Strategy Signal
        signal = Signal(
            symbol=symbol,
            direction=SignalDirection.BUY,
            target_volume=100,
            strategy_name="TestStrategy"
        )
        mock_strategy.generate_signals.return_value = [signal]

        # 4. Mock Order Placement
        mock_trade_gateway.place_order.return_value = "order_123"

        # Act
        app_service.run_cycle([symbol])

        # Assert
        # Verify market data fetched
        mock_market_gateway.get_recent_bars.assert_called_with(symbol, timeframe="1d", limit=100)
        
        # Verify account data fetched
        mock_account_gateway.get_asset.assert_called_once()
        mock_account_gateway.get_positions.assert_called_once()
        
        # Verify strategy called
        mock_strategy.generate_signals.assert_called_once()
        
        # Verify order placed
        mock_trade_gateway.place_order.assert_called_once()
        args, _ = mock_trade_gateway.place_order.call_args
        order: Order = args[0]
        assert isinstance(order, Order)
        assert order.ticker == symbol
        assert order.direction == OrderDirection.BUY
        assert order.volume == 100
        assert order.price == 10.0  # Close price from bar

    def test_run_cycle_should_skip_if_no_market_data(
        self, app_service, mock_market_gateway, mock_account_gateway
    ):
        # Arrange
        symbol = "600000.SH"
        mock_market_gateway.get_recent_bars.return_value = []

        # Act
        app_service.run_cycle([symbol])

        # Assert
        mock_account_gateway.get_asset.assert_not_called()

    def test_run_cycle_should_skip_if_insufficient_funds(
        self, app_service, mock_market_gateway, mock_account_gateway, mock_trade_gateway, mock_strategy
    ):
        # Arrange
        symbol = "600000.SH"
        
        # 1. Market Data (Price 100.0)
        bar = Bar(
            symbol=symbol,
            timestamp=datetime.now(),
            open=100.0, high=110.0, low=90.0, close=100.0, volume=1000
        )
        mock_market_gateway.get_recent_bars.return_value = [bar]

        # 2. Account Data (Only 50.0 cash)
        asset = Asset(account_id="acc1", total_asset=100.0, available_cash=50.0)
        mock_account_gateway.get_asset.return_value = asset
        mock_account_gateway.get_positions.return_value = []

        # 3. Strategy Signal (Buy 100 shares at 100.0 = 10000.0 cost)
        signal = Signal(
            symbol=symbol,
            direction=SignalDirection.BUY,
            target_volume=100,
            strategy_name="TestStrategy"
        )
        mock_strategy.generate_signals.return_value = [signal]

        # Act
        app_service.run_cycle([symbol])

        # Assert
        mock_trade_gateway.place_order.assert_not_called()

    def test_run_cycle_should_skip_if_asset_retrieval_fails(
        self, app_service, mock_market_gateway, mock_account_gateway, mock_strategy
    ):
        # Arrange
        symbol = "600000.SH"
        mock_market_gateway.get_recent_bars.return_value = [MagicMock()]
        mock_account_gateway.get_asset.return_value = None

        # Act
        app_service.run_cycle([symbol])

        # Assert
        mock_strategy.generate_signals.assert_not_called()
