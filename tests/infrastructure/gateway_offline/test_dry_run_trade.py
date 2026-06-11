"""DryRunTradeGateway 测试 — 离线可跑(不依赖 xtquant), 故放 gateway_offline 目录。"""
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.infrastructure.gateway.dry_run_trade import DryRunTradeGateway


class _FakeReal:
    def __init__(self):
        self.place_called = 0

    def place_order(self, order):
        self.place_called += 1
        return "real-1"

    def get_asset(self):
        return "ASSET"

    def get_positions(self):
        return ["POS"]


def _order() -> Order:
    return Order(order_id="x", account_id="", ticker="601006.SH",
                 direction=OrderDirection.BUY, price=5.0, volume=100,
                 type=OrderType.LIMIT)


class TestDryRunTradeGateway:
    def test_place_order_never_touches_real_gateway(self):
        real = _FakeReal()
        gw = DryRunTradeGateway(real)

        oid1, oid2 = gw.place_order(_order()), gw.place_order(_order())

        assert real.place_called == 0
        assert oid1.startswith("dry-") and oid1 != oid2

    def test_query_and_cancel_are_simulated(self):
        gw = DryRunTradeGateway(_FakeReal())
        oid = gw.place_order(_order())
        assert gw.query_order_status(oid) == "DRY_RUN"
        assert gw.cancel_order(oid) is True

    def test_reads_delegate_to_real(self):
        gw = DryRunTradeGateway(_FakeReal())
        assert gw.get_asset() == "ASSET"
        assert gw.get_positions() == ["POS"]

    def test_order_ids_unique_across_instances(self):
        """评审发现 #7: 进程重启(新实例)的单号不得与历史撞 PRIMARY KEY 覆盖留痕。"""
        gw1, gw2 = DryRunTradeGateway(_FakeReal()), DryRunTradeGateway(_FakeReal())
        assert gw1.place_order(_order()) != gw2.place_order(_order())

    def test_declares_dry_run_flag(self):
        assert DryRunTradeGateway(_FakeReal()).is_dry_run is True
