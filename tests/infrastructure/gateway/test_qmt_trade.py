import pytest
from unittest.mock import MagicMock, patch
from src.infrastructure.gateway.qmt_trade import QmtTradeGateway
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.domain.trade.value_objects.order_status import OrderStatus
from src.infrastructure.libs.xtquant import xtconstant
from src.infrastructure.libs.xtquant.xttype import XtAsset, XtPosition

class TestQmtTradeGateway:
    @pytest.fixture
    def mock_xt_trader(self):
        with patch("src.infrastructure.gateway.qmt_trade.XtQuantTrader") as mock:
            yield mock

    @pytest.fixture
    def mock_stock_account(self):
        with patch("src.infrastructure.gateway.qmt_trade.StockAccount") as mock:
            yield mock

    def test_init_should_connect_and_subscribe(self, mock_xt_trader, mock_stock_account):
        # Arrange
        path = "path/to/userdata"
        session_id = 123
        account_id = "test_acc"
        
        mock_trader_instance = mock_xt_trader.return_value
        mock_trader_instance.connect.return_value = 0
        mock_trader_instance.subscribe.return_value = 0

        # Act
        gateway = QmtTradeGateway(path, session_id, account_id)

        # Assert
        mock_xt_trader.assert_called_with(path, session_id)
        mock_stock_account.assert_called_with(account_id, "STOCK")
        mock_trader_instance.start.assert_called_once()
        mock_trader_instance.connect.assert_called_once()
        mock_trader_instance.subscribe.assert_called_once()

    def test_get_asset_should_return_mapped_asset(self, mock_xt_trader, mock_stock_account):
        # Arrange
        mock_trader_instance = mock_xt_trader.return_value
        gateway = QmtTradeGateway("path", 123, "acc")
        
        # Mock XtAsset return
        xt_asset = XtAsset(
            account_id="acc",
            cash=10000.0,
            frozen_cash=2000.0,
            market_value=50000.0,
            total_asset=62000.0,
            fetch_balance=10000.0
        )
        mock_trader_instance.query_stock_asset.return_value = xt_asset

        # Act
        asset = gateway.get_asset()

        # Assert
        assert asset is not None
        assert asset.account_id == "acc"
        assert asset.total_asset == 62000.0
        assert asset.available_cash == 10000.0
        assert asset.frozen_cash == 2000.0

    def test_get_positions_should_return_mapped_positions(self, mock_xt_trader, mock_stock_account):
        # Arrange
        mock_trader_instance = mock_xt_trader.return_value
        gateway = QmtTradeGateway("path", 123, "acc")
        
        # Mock XtPosition return
        xt_pos = XtPosition(
            account_id="acc",
            stock_code="600000.SH",
            volume=100,
            can_use_volume=100,
            open_price=10.0,
            market_value=1000.0,
            frozen_volume=0,
            on_road_volume=0,
            yesterday_volume=100,
            avg_price=10.0,
            direction=0,
            last_price=10.0,
            profit_rate=0.0,
            secu_account="sec",
            instrument_name="name"
        )
        mock_trader_instance.query_stock_positions.return_value = [xt_pos]

        # Act
        positions = gateway.get_positions()

        # Assert
        assert len(positions) == 1
        pos = positions[0]
        assert pos.account_id == "acc"
        assert pos.ticker == "600000.SH"
        assert pos.total_volume == 100
        assert pos.available_volume == 100
        assert pos.average_cost == 10.0

    def test_place_order_should_call_xt_order_stock(self, mock_xt_trader, mock_stock_account):
        # Arrange
        mock_trader_instance = mock_xt_trader.return_value
        gateway = QmtTradeGateway("path", 123, "acc")
        mock_trader_instance.order_stock.return_value = 1001
        
        order = Order(
            order_id="1", 
            account_id="acc", 
            ticker="600000.SH", 
            direction=OrderDirection.BUY, 
            price=10.0, 
            volume=100
        )

        # Act
        order_id = gateway.place_order(order)

        # Assert
        assert order_id == "1001"
        mock_trader_instance.order_stock.assert_called_once()
        args, _ = mock_trader_instance.order_stock.call_args
        # Check args: account, stock_code, order_type, order_volume, price_type, price, strategy_name, order_remark
        assert args[1] == "600000.SH"
        assert args[2] == xtconstant.STOCK_BUY
        assert args[3] == 100
        assert args[4] == xtconstant.FIX_PRICE
        assert args[5] == 10.0
