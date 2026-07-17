"""RiskChain 测试。

2026-07-10 六西格玛体检 D6: 原版用 MagicMock 造策略与领域上下文, 违反
testing.md「domain 层测试禁 mock, 用手写 Fake + 真实领域对象」。
"""

from src.domain.risk.services.risk_chain import RiskChain
from src.domain.risk.value_objects.risk_check_result import RiskCheckResult
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection


class FakePolicy:
    """记录被检订单的风控策略替身。"""

    def __init__(self, result: RiskCheckResult):
        self._result = result
        self.checked: list[Order] = []

    def check(self, order: Order) -> RiskCheckResult:
        self.checked.append(order)
        return self._result


def _order() -> Order:
    return Order(order_id="o-1", account_id="t", ticker="600000.SH",
                 direction=OrderDirection.BUY, price=10.0, volume=100)


def test_risk_chain_passes_when_all_policies_pass():
    p1 = FakePolicy(RiskCheckResult.pass_check())
    p2 = FakePolicy(RiskCheckResult.pass_check())

    chain = RiskChain([p1, p2])
    result = chain.check(_order())

    assert result.passed is True
    assert len(p1.checked) == 1 and len(p2.checked) == 1


def test_risk_chain_stops_at_first_rejection():
    p1 = FakePolicy(RiskCheckResult.reject("blocked by p1"))
    p2 = FakePolicy(RiskCheckResult.pass_check())

    chain = RiskChain([p1, p2])
    result = chain.check(_order())

    assert result.passed is False
    assert "blocked by p1" in result.reason
    assert p2.checked == []  # 责任链短路, 后续策略不再执行


def test_risk_chain_empty_passes():
    chain = RiskChain()

    result = chain.check(_order())

    assert result.passed is True


def test_risk_chain_add_policy():
    chain = RiskChain()
    p1 = FakePolicy(RiskCheckResult.pass_check())
    chain.add_policy(p1)

    result = chain.check(_order())

    assert result.passed is True
    assert len(p1.checked) == 1
