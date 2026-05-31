from unittest.mock import MagicMock

from src.application.order_executor import OrderExecutor
from src.domain.portfolio.entities.order_target import OrderTarget
from src.domain.risk.services.risk_chain import RiskChain
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.trade.value_objects.execution_status import ExecutionStatus
from src.domain.trade.value_objects.order_direction import OrderDirection


def _make_target(
    symbol: str = "600000.SH",
    direction: OrderDirection = OrderDirection.BUY,
    volume: int = 100,
    price: float = 10.0,
) -> OrderTarget:
    return OrderTarget(
        symbol=symbol,
        direction=direction,
        volume=volume,
        price=price,
        strategy_name="test",
    )


class TestOrderExecutor:
    def test_execute_buy_order_success(self):
        gateway = MagicMock()
        gateway.place_order.return_value = "order-123"
        risk_chain = RiskChain()
        executor = OrderExecutor(gateway, risk_chain)

        targets = [_make_target()]
        records = executor.execute(targets)

        assert len(records) == 1
        assert records[0].status == ExecutionStatus.SUBMITTED
        assert records[0].order_id == "order-123"
        gateway.place_order.assert_called_once()

    def test_execute_sell_first(self):
        gateway = MagicMock()
        gateway.place_order.return_value = "order-1"
        risk_chain = RiskChain()
        executor = OrderExecutor(gateway, risk_chain)

        targets = [
            _make_target(direction=OrderDirection.BUY),
            _make_target(symbol="000001.SZ", direction=OrderDirection.SELL),
        ]
        records = executor.execute(targets)

        assert len(records) == 2
        # Sell should be first
        assert records[0].direction == OrderDirection.SELL
        assert records[1].direction == OrderDirection.BUY

    def test_execute_rejected_by_risk(self):
        gateway = MagicMock()
        from src.domain.risk.services.base_risk_policy import BaseRiskPolicy
        from src.domain.risk.value_objects.risk_check_result import RiskCheckResult

        class RejectPolicy(BaseRiskPolicy):
            def check(self, order):
                return RiskCheckResult.reject("测试拒绝")

        risk_chain = RiskChain([RejectPolicy()])
        executor = OrderExecutor(gateway, risk_chain)

        targets = [_make_target()]
        records = executor.execute(targets)

        assert len(records) == 1
        assert records[0].status == ExecutionStatus.REJECTED
        assert "测试拒绝" in records[0].error_message
        gateway.place_order.assert_not_called()

    def test_execute_order_submit_error(self):
        gateway = MagicMock()
        gateway.place_order.side_effect = OrderSubmitError("提交失败")
        risk_chain = RiskChain()
        executor = OrderExecutor(gateway, risk_chain)

        targets = [_make_target()]
        records = executor.execute(targets)

        assert len(records) == 1
        assert records[0].status == ExecutionStatus.FAILED
        assert "提交失败" in records[0].error_message

    def test_execute_multiple_targets(self):
        gateway = MagicMock()
        gateway.place_order.return_value = "order-x"
        risk_chain = RiskChain()
        executor = OrderExecutor(gateway, risk_chain)

        targets = [
            _make_target(symbol="600000.SH"),
            _make_target(symbol="000001.SZ"),
            _make_target(symbol="000002.SZ"),
        ]
        records = executor.execute(targets)

        assert len(records) == 3
        assert gateway.place_order.call_count == 3
