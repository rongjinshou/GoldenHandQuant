"""DailySettlementService 测试。"""

from datetime import datetime

import pytest

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.services.settlement_service import DailySettlementService
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_status import OrderStatus
from src.domain.trade.value_objects.order_type import OrderType  # noqa: I001

FIXED_TIME = datetime(2026, 1, 1)


def _make_buy_order(
    order_id: str = "ORD_1",
    price: float = 10.0,
    volume: int = 100,
    traded_volume: int = 0,
    status: OrderStatus = OrderStatus.SUBMITTED,
) -> Order:
    order = Order(
        order_id=order_id,
        account_id="TEST",
        ticker="600000.SH",
        direction=OrderDirection.BUY,
        price=price,
        volume=volume,
        type=OrderType.LIMIT,
        status=status,
        traded_volume=traded_volume,
        created_at=FIXED_TIME,
    )
    return order


def _make_sell_order(
    order_id: str = "ORD_1",
    price: float = 10.0,
    volume: int = 100,
    traded_volume: int = 0,
    status: OrderStatus = OrderStatus.SUBMITTED,
) -> Order:
    order = Order(
        order_id=order_id,
        account_id="TEST",
        ticker="600000.SH",
        direction=OrderDirection.SELL,
        price=price,
        volume=volume,
        type=OrderType.LIMIT,
        status=status,
        traded_volume=traded_volume,
        created_at=FIXED_TIME,
    )
    return order


class TestDailySettlementService:
    def test_normal_settlement_with_positions_and_trades(self):
        """正常结算：有持仓、有已成交订单。"""
        service = DailySettlementService()

        # 有一笔已成交的买入单 (不需要撤销)
        filled_order = _make_buy_order(status=OrderStatus.FILLED, traded_volume=100)

        # 当日买入的持仓：total=100, available=0 (T+1)
        position = Position(
            account_id="TEST", ticker="600000.SH",
            total_volume=100, available_volume=0, average_cost=10.0,
        )
        asset = Asset(account_id="TEST", total_asset=100000.0, available_cash=50000.0, frozen_cash=0.0)

        service.process_daily_settlement([filled_order], [position], asset)

        # T+1 结算后，持仓应变为可用
        assert position.available_volume == 100
        assert position.total_volume == 100
        # 已成交单不受影响
        assert filled_order.status == OrderStatus.FILLED

    def test_t_plus_1_position_release(self):
        """T+1 持仓释放：当日买入不可卖 -> 次日可卖。"""
        service = DailySettlementService()

        # 昨日持仓 200 (available=200) + 今日买入 100 (available=0) = total 300, available 200
        position = Position(
            account_id="TEST", ticker="600000.SH",
            total_volume=300, available_volume=200, average_cost=10.0,
        )
        asset = Asset(account_id="TEST", total_asset=100000.0, available_cash=50000.0, frozen_cash=0.0)

        service.process_daily_settlement([], [position], asset)

        # 结算后全部可用
        assert position.available_volume == 300
        assert position.total_volume == 300

    def test_cancel_unfilled_orders(self):
        """未成交订单应被撤销。"""
        service = DailySettlementService()

        # 买入挂单：100股，未成交，冻结资金
        order = _make_buy_order(price=10.0, volume=100, traded_volume=0, status=OrderStatus.SUBMITTED)

        # 计算预期冻结金额
        amount = 100 * 10.0  # 1000
        commission = max(amount * 0.00025, 5.0)  # 5.0 (min)
        transfer_fee = amount * 0.00001  # 0.01
        frozen_amount = amount + commission + transfer_fee  # 1005.01

        asset = Asset(
            account_id="TEST", total_asset=100000.0,
            available_cash=98994.99, frozen_cash=frozen_amount,
        )

        service.process_daily_settlement([order], [], asset)

        # 订单应被撤销
        assert order.status == OrderStatus.CANCELED
        # 冻结资金应解冻
        assert asset.frozen_cash == pytest.approx(0.0, abs=0.01)
        assert asset.available_cash == pytest.approx(100000.0, abs=0.01)

    def test_cancel_partial_filled_orders(self):
        """部分成交订单应被撤销（部成部撤）。"""
        service = DailySettlementService()

        # 买入挂单：200股，已成交100股
        order = _make_buy_order(price=10.0, volume=200, traded_volume=100, status=OrderStatus.PARTIAL_FILLED)

        # 剩余 100 股的冻结金额
        remaining = 100
        amount = remaining * 10.0
        commission = max(amount * 0.00025, 5.0)
        transfer_fee = amount * 0.00001
        frozen_amount = amount + commission + transfer_fee

        asset = Asset(
            account_id="TEST", total_asset=100000.0,
            available_cash=98994.99, frozen_cash=frozen_amount,
        )

        service.process_daily_settlement([order], [], asset)

        # 订单应变为部成部撤
        assert order.status == OrderStatus.PARTIAL_CANCELED
        # 冻结资金应解冻
        assert asset.frozen_cash == pytest.approx(0.0, abs=0.01)

    def test_unfreeze_cash_for_buy_order(self):
        """冻结资金应被正确解冻。"""
        service = DailySettlementService()

        # 两笔未成交买入单
        order1 = _make_buy_order(order_id="ORD_1", price=10.0, volume=100, status=OrderStatus.SUBMITTED)
        order2 = _make_buy_order(order_id="ORD_2", price=20.0, volume=200, status=OrderStatus.SUBMITTED)

        # 计算冻结金额
        frozen1 = 100 * 10.0 + max(100 * 10.0 * 0.00025, 5.0) + 100 * 10.0 * 0.00001
        frozen2 = 200 * 20.0 + max(200 * 20.0 * 0.00025, 5.0) + 200 * 20.0 * 0.00001
        total_frozen = frozen1 + frozen2

        asset = Asset(
            account_id="TEST", total_asset=100000.0,
            available_cash=100000.0 - total_frozen, frozen_cash=total_frozen,
        )

        service.process_daily_settlement([order1, order2], [], asset)

        # 两笔订单都应被撤销
        assert order1.status == OrderStatus.CANCELED
        assert order2.status == OrderStatus.CANCELED
        # 冻结资金应全部解冻
        assert asset.frozen_cash == pytest.approx(0.0, abs=0.01)
        assert asset.available_cash == pytest.approx(100000.0, abs=0.01)

    def test_empty_account_settlement(self):
        """空账户结算不应报错。"""
        service = DailySettlementService()

        asset = Asset(account_id="TEST", total_asset=100000.0, available_cash=100000.0, frozen_cash=0.0)

        # 无订单、无持仓
        service.process_daily_settlement([], [], asset)

        # 资产不变
        assert asset.total_asset == 100000.0
        assert asset.available_cash == 100000.0
        assert asset.frozen_cash == 0.0

    def test_sell_order_cancel_does_not_unfreeze_cash(self):
        """卖出单撤销不应解冻资金（卖出不冻结资金）。"""
        service = DailySettlementService()

        order = _make_sell_order(price=10.0, volume=100, status=OrderStatus.SUBMITTED)
        asset = Asset(
            account_id="TEST", total_asset=100000.0,
            available_cash=100000.0, frozen_cash=0.0,
        )

        service.process_daily_settlement([order], [], asset)

        # 卖出单被撤销，但资金不变
        assert order.status == OrderStatus.CANCELED
        assert asset.frozen_cash == 0.0
        assert asset.available_cash == 100000.0

    def test_filled_order_not_canceled(self):
        """已成交订单不应被撤销。"""
        service = DailySettlementService()

        filled_order = _make_buy_order(status=OrderStatus.FILLED, traded_volume=100)
        asset = Asset(account_id="TEST", total_asset=100000.0, available_cash=50000.0, frozen_cash=0.0)

        service.process_daily_settlement([filled_order], [], asset)

        assert filled_order.status == OrderStatus.FILLED

    def test_canceled_order_not_affected(self):
        """已撤销订单不应被重复处理。"""
        service = DailySettlementService()

        canceled_order = _make_buy_order(status=OrderStatus.CANCELED, traded_volume=0)
        asset = Asset(account_id="TEST", total_asset=100000.0, available_cash=100000.0, frozen_cash=0.0)

        service.process_daily_settlement([canceled_order], [], asset)

        assert canceled_order.status == OrderStatus.CANCELED

    def test_multiple_positions_settle(self):
        """多个持仓应全部结算。"""
        service = DailySettlementService()

        pos1 = Position(account_id="TEST", ticker="600000.SH", total_volume=100, available_volume=0)
        pos2 = Position(account_id="TEST", ticker="000001.SZ", total_volume=200, available_volume=100)
        asset = Asset(account_id="TEST", total_asset=100000.0, available_cash=100000.0, frozen_cash=0.0)

        service.process_daily_settlement([], [pos1, pos2], asset)

        assert pos1.available_volume == 100
        assert pos2.available_volume == 200
