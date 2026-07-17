"""CircuitBreaker 领域事件测试。"""

from datetime import datetime

from src.domain.account.entities.asset import Asset
from src.domain.risk.services.circuit_breaker import CircuitBreaker
from src.domain.risk.value_objects.circuit_breaker_state import BreakerStatus


class TestCircuitBreakerDomainEvents:
    def test_new_breaker_has_no_pending_events(self):
        breaker = CircuitBreaker()
        events = breaker.collect_pending_events()
        assert events == []

    def test_trigger_emits_circuit_breaker_triggered_event(self):
        # Arrange
        breaker = CircuitBreaker(max_daily_loss=0.03)
        breaker.set_initial_capital(100000.0)
        breaker.reset_daily(datetime(2025, 1, 2), day_open_asset=100000.0)

        asset = Asset(account_id="test", total_asset=96000.0)  # 4% loss

        # Act
        breaker.evaluate(asset, [])
        events = breaker.collect_pending_events()

        # Assert
        assert len(events) == 1
        assert events[0].event_type == "CircuitBreakerTriggered"
        assert events[0].aggregate_id == "circuit_breaker"
        assert events[0].aggregate_type == "CircuitBreaker"
        assert "Daily loss" in events[0].payload["reason"]

    def test_cooldown_transition_emits_cooldown_event(self):
        # Arrange
        breaker = CircuitBreaker(max_daily_loss=0.03)
        breaker.set_initial_capital(100000.0)
        breaker.reset_daily(datetime(2025, 1, 2), day_open_asset=100000.0)

        asset = Asset(account_id="test", total_asset=96000.0)
        breaker.evaluate(asset, [])
        breaker.collect_pending_events()

        # Act — next day, TRIGGERED -> COOLDOWN
        breaker.reset_daily(datetime(2025, 1, 3), day_open_asset=96000.0)
        events = breaker.collect_pending_events()

        # Assert
        assert breaker.state.status == BreakerStatus.COOLDOWN
        assert len(events) == 1
        assert events[0].event_type == "CircuitBreakerCooldownEntered"

    def test_recovery_emits_circuit_breaker_recovered_event(self):
        # Arrange
        breaker = CircuitBreaker(max_daily_loss=0.03)
        breaker.set_initial_capital(100000.0)
        breaker.reset_daily(datetime(2025, 1, 2), day_open_asset=100000.0)

        asset = Asset(account_id="test", total_asset=96000.0)
        breaker.evaluate(asset, [])
        breaker.reset_daily(datetime(2025, 1, 3), day_open_asset=96000.0)
        breaker.collect_pending_events()

        # Act — next day, COOLDOWN -> NORMAL
        breaker.reset_daily(datetime(2025, 1, 4), day_open_asset=96000.0)
        events = breaker.collect_pending_events()

        # Assert
        assert breaker.state.status == BreakerStatus.NORMAL
        assert len(events) == 1
        assert events[0].event_type == "CircuitBreakerRecovered"

    def test_collect_clears_buffer(self):
        breaker = CircuitBreaker(max_daily_loss=0.03)
        breaker.set_initial_capital(100000.0)
        breaker.reset_daily(datetime(2025, 1, 2), day_open_asset=100000.0)

        asset = Asset(account_id="test", total_asset=96000.0)
        breaker.evaluate(asset, [])

        first = breaker.collect_pending_events()
        second = breaker.collect_pending_events()

        assert len(first) == 1
        assert len(second) == 0
