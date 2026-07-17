from unittest.mock import MagicMock, patch

import pytest

from src.domain.trade.entities.order import Order
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.infrastructure.gateway.qmt_trade import (
    QmtTradeGateway,
    derive_session_id,
    xtconstant,
)


@pytest.fixture
def mock_xt_trader():
    with patch("src.infrastructure.gateway.qmt_trade.XtQuantTrader") as mock:
        # 默认连接/订阅成功(0); 失败场景由用例显式覆盖
        mock.return_value.connect.return_value = 0
        mock.return_value.subscribe.return_value = 0
        yield mock


@pytest.fixture
def mock_stock_account():
    with patch("src.infrastructure.gateway.qmt_trade.StockAccount") as mock:
        yield mock


class TestQmtTradeGateway:
    def test_init_should_connect_and_subscribe(self, mock_xt_trader, mock_stock_account):
        # Arrange
        path = "path/to/userdata"
        session_id = 123
        account_id = "test_acc"

        mock_trader_instance = mock_xt_trader.return_value

        # Act
        gw = QmtTradeGateway(path, session_id, account_id)

        # Assert: 传给 XtQuantTrader 的是派生 session(进程唯一), 非配置基值
        mock_xt_trader.assert_called_with(path, gw.session_id)
        mock_stock_account.assert_called_with(account_id, "STOCK")
        mock_trader_instance.start.assert_called_once()
        mock_trader_instance.connect.assert_called_once()
        mock_trader_instance.subscribe.assert_called_once()

    def test_init_should_fail_fast_when_connect_fails(self, mock_xt_trader, mock_stock_account):
        """confirmed-bug(2026-07-10 六西格玛体检 H2): connect() 非 0 曾只记日志、
        照样 _initialized=True——半死网关进入下单路径, get_asset 返 None 还会触发
        下游日亏闸 fail-open。runbook(0611-closed-loop) 实录过 connect != 0。"""
        mock_trader_instance = mock_xt_trader.return_value
        mock_trader_instance.connect.return_value = -1

        with pytest.raises(RuntimeError, match="connect"):
            QmtTradeGateway("path", 123, "acc")

    def test_init_should_fail_fast_when_subscribe_fails(self, mock_xt_trader, mock_stock_account):
        """订阅失败与连接失败同款处理: 立即抛错, 不留半初始化网关。"""
        mock_trader_instance = mock_xt_trader.return_value
        mock_trader_instance.subscribe.return_value = -1

        with pytest.raises(RuntimeError, match="subscribe"):
            QmtTradeGateway("path", 123, "acc")

    def test_get_asset_should_return_mapped_asset(self, mock_xt_trader, mock_stock_account):
        # Arrange
        mock_trader_instance = mock_xt_trader.return_value
        gateway = QmtTradeGateway("path", 123, "acc")

        # Mock XtAsset return
        xt_asset = MagicMock()
        xt_asset.total_asset = 62000.0
        xt_asset.cash = 10000.0
        xt_asset.frozen_cash = 2000.0
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
        xt_pos = MagicMock()
        xt_pos.stock_code = "600000.SH"
        xt_pos.volume = 100
        xt_pos.can_use_volume = 100
        xt_pos.open_price = 10.0
        xt_pos.avg_price = 10.0
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


class TestDeriveSessionId:
    """固定 session 复用会被 QMT 中上一进程的残留注册占用(0713 watch / 0714
    auto-trade 两日 connect != 0 实证) → 每进程派生唯一 session。"""

    def test_deterministic_formula(self):
        sid = derive_session_id(123464, stamp=1_000_000, pid=42)
        assert sid == 123464 + 300_000 + (1_000_000 * 31 + 42) % 100_000

    def test_same_second_different_pid_do_not_collide(self):
        a = derive_session_id(123464, stamp=1_000_000, pid=41)
        b = derive_session_id(123464, stamp=1_000_000, pid=42)
        assert a != b

    def test_band_disjoint_from_sync_live_account(self):
        # sync_live_account 频段 = base+500k+[0,100k); 网关频段 = base+300k+[0,100k)
        sid = derive_session_id(123464, stamp=987_654_321, pid=99)
        assert 123464 + 300_000 <= sid < 123464 + 400_000

    def test_gateway_uses_derived_not_base(self, mock_xt_trader, mock_stock_account):
        gw = QmtTradeGateway("path", 123, "acc")
        assert gw.session_id != 123
        assert mock_xt_trader.call_args[0] == ("path", gw.session_id)


class TestDisconnectProtectionM3:
    """M3 断线防护保守版（2026-07-10 六西格玛体检, 决策项 Q4 获批-保守实现）。

    此前 register_callback 注册的是 SDK 基类空实现: 断线事件无人处理,
    断开后订单照样打向失效 session。保守版: on_disconnected 置不可用标志
    + place_order 拒单 + 告警; 不做自动重连(待真实环境验证后另立)。
    """

    def test_place_order_rejected_after_disconnect(self, mock_xt_trader, mock_stock_account):
        gateway = QmtTradeGateway("path", 123, "acc")

        gateway.callback.on_disconnected()

        order = Order(order_id="1", account_id="acc", ticker="600000.SH",
                      direction=OrderDirection.BUY, price=10.0, volume=100)
        with pytest.raises(OrderSubmitError, match="断开"):
            gateway.place_order(order)

    def test_order_error_callback_logs_without_raising(self, mock_xt_trader, mock_stock_account):
        gateway = QmtTradeGateway("path", 123, "acc")

        err = MagicMock()
        err.order_id, err.error_id, err.error_msg = 1001, -1, "资金不足"
        gateway.callback.on_order_error(err)  # 只告警, 不得抛

    def test_connected_gateway_places_normally(self, mock_xt_trader, mock_stock_account):
        mock_xt_trader.return_value.order_stock.return_value = 7
        gateway = QmtTradeGateway("path", 123, "acc")

        order = Order(order_id="1", account_id="acc", ticker="600000.SH",
                      direction=OrderDirection.BUY, price=10.0, volume=100)

        assert gateway.place_order(order) == "7"
