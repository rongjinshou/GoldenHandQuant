from datetime import datetime

from src.domain.risk.services.circuit_breaker import CircuitBreaker
from src.domain.risk.services.risk_policies.daily_loss_policy import DailyLossPolicy
from src.domain.risk.value_objects.circuit_breaker_state import BreakerStatus, CircuitBreakerState
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection


def _make_order(direction: OrderDirection) -> Order:
    return Order(
        order_id="TEST_ORD",
        account_id="TEST",
        ticker="600000.SH",
        direction=direction,
        price=10.0,
        volume=100 if direction == OrderDirection.BUY else 100,
        created_at=datetime(2026, 1, 1),
    )


def test_normal_state_passes_all_orders():
    breaker = CircuitBreaker()
    policy = DailyLossPolicy(breaker)

    buy = _make_order(OrderDirection.BUY)
    sell = _make_order(OrderDirection.SELL)

    assert policy.check(buy).passed is True
    assert policy.check(sell).passed is True


def test_triggered_state_rejects_all_orders():
    breaker = CircuitBreaker()
    # Force TRIGGERED state
    breaker._state = CircuitBreakerState(
        status=BreakerStatus.TRIGGERED,
        trigger_reason="test trigger",
    )
    policy = DailyLossPolicy(breaker)

    buy = _make_order(OrderDirection.BUY)
    sell = _make_order(OrderDirection.SELL)

    assert policy.check(buy).passed is False
    assert policy.check(sell).passed is False
    assert "Circuit breaker active" in policy.check(buy).reason


def test_cooldown_state_rejects_buy_allows_sell():
    breaker = CircuitBreaker()
    breaker._state = CircuitBreakerState(
        status=BreakerStatus.COOLDOWN,
        trigger_reason="test cooldown",
    )
    policy = DailyLossPolicy(breaker)

    buy = _make_order(OrderDirection.BUY)
    sell = _make_order(OrderDirection.SELL)

    assert policy.check(buy).passed is False
    assert "Cooldown period" in policy.check(buy).reason
    assert policy.check(sell).passed is True
