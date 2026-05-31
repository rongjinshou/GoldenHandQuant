from datetime import datetime
from unittest.mock import MagicMock

from src.domain.account.entities.asset import Asset
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.domain.risk.services.circuit_breaker import CircuitBreaker
from src.domain.risk.value_objects.circuit_breaker_state import BreakerStatus
from src.domain.risk.value_objects.risk_event import RiskEventType


def test_initial_state_is_normal():
    breaker = CircuitBreaker()
    assert breaker.state.is_normal
    assert breaker.state.status == BreakerStatus.NORMAL


def test_daily_loss_triggers_breaker():
    breaker = CircuitBreaker(max_daily_loss=0.03)
    breaker.set_initial_capital(1_000_000)
    breaker.reset_daily(datetime(2026, 1, 1), day_open_asset=1_000_000)

    asset = Asset(account_id="test", total_asset=965_000)  # -3.5%
    breaker.evaluate(asset, [])

    assert breaker.state.status == BreakerStatus.TRIGGERED
    assert breaker.state.blocks_all_trading
    assert "3.50%" in breaker.state.trigger_reason


def test_total_drawdown_triggers_breaker():
    breaker = CircuitBreaker(max_daily_loss=0.10, max_total_drawdown=0.20)
    breaker.set_initial_capital(1_000_000)
    breaker.reset_daily(datetime(2026, 1, 1), day_open_asset=1_000_000)

    # Create snapshots showing a peak at 1,000,000 then dropping
    snapshots = [
        DailySnapshot(date=datetime(2026, 1, 2), total_asset=1_000_000,
                       available_cash=500_000, market_value=500_000),
        DailySnapshot(date=datetime(2026, 1, 3), total_asset=900_000,
                       available_cash=500_000, market_value=400_000),
    ]

    asset = Asset(account_id="test", total_asset=790_000)  # 21% drawdown
    breaker.evaluate(asset, snapshots)

    assert breaker.state.status == BreakerStatus.TRIGGERED
    assert "21.00%" in breaker.state.trigger_reason


def test_triggered_next_day_becomes_cooldown():
    breaker = CircuitBreaker(max_daily_loss=0.03)
    breaker.set_initial_capital(1_000_000)
    breaker.reset_daily(datetime(2026, 1, 1), day_open_asset=1_000_000)

    asset = Asset(account_id="test", total_asset=965_000)
    breaker.evaluate(asset, [])
    assert breaker.state.status == BreakerStatus.TRIGGERED

    # Next day
    breaker.reset_daily(datetime(2026, 1, 2), day_open_asset=965_000)
    assert breaker.state.status == BreakerStatus.COOLDOWN
    assert breaker.state.allows_sell_only


def test_cooldown_next_day_becomes_normal():
    breaker = CircuitBreaker(max_daily_loss=0.03)
    breaker.set_initial_capital(1_000_000)
    breaker.reset_daily(datetime(2026, 1, 1), day_open_asset=1_000_000)

    asset = Asset(account_id="test", total_asset=965_000)
    breaker.evaluate(asset, [])

    breaker.reset_daily(datetime(2026, 1, 2), day_open_asset=965_000)
    assert breaker.state.status == BreakerStatus.COOLDOWN

    breaker.reset_daily(datetime(2026, 1, 3), day_open_asset=965_000)
    assert breaker.state.status == BreakerStatus.NORMAL
    assert breaker.state.is_normal


def test_no_double_trigger():
    breaker = CircuitBreaker(max_daily_loss=0.03)
    breaker.set_initial_capital(1_000_000)
    breaker.reset_daily(datetime(2026, 1, 1), day_open_asset=1_000_000)

    asset = Asset(account_id="test", total_asset=965_000)
    breaker.evaluate(asset, [])
    assert breaker.state.status == BreakerStatus.TRIGGERED

    # Second evaluate should not change state
    asset2 = Asset(account_id="test", total_asset=900_000)
    state = breaker.evaluate(asset2, [])
    assert state.status == BreakerStatus.TRIGGERED


def test_events_emitted_on_trigger():
    breaker = CircuitBreaker(max_daily_loss=0.03)
    breaker.set_initial_capital(1_000_000)
    breaker.reset_daily(datetime(2026, 1, 1), day_open_asset=1_000_000)

    asset = Asset(account_id="test", total_asset=965_000)
    breaker.evaluate(asset, [])

    assert len(breaker.events) == 1
    assert breaker.events[0].event_type == RiskEventType.CIRCUIT_BREAKER_ON
    assert breaker.events[0].severity.value == "CRITICAL"


def test_events_emitted_on_recovery():
    breaker = CircuitBreaker(max_daily_loss=0.03)
    breaker.set_initial_capital(1_000_000)

    # Trigger
    breaker.reset_daily(datetime(2026, 1, 1), day_open_asset=1_000_000)
    asset = Asset(account_id="test", total_asset=965_000)
    breaker.evaluate(asset, [])

    # Cooldown
    breaker.reset_daily(datetime(2026, 1, 2), day_open_asset=965_000)

    # Recovery
    breaker.reset_daily(datetime(2026, 1, 3), day_open_asset=965_000)
    assert len(breaker.events) == 1
    assert breaker.events[0].event_type == RiskEventType.CIRCUIT_BREAKER_OFF
    assert breaker.events[0].severity.value == "INFO"


def test_normal_within_limits_no_trigger():
    breaker = CircuitBreaker(max_daily_loss=0.03)
    breaker.set_initial_capital(1_000_000)
    breaker.reset_daily(datetime(2026, 1, 1), day_open_asset=1_000_000)

    asset = Asset(account_id="test", total_asset=980_000)  # -2%, within limit
    breaker.evaluate(asset, [])

    assert breaker.state.status == BreakerStatus.NORMAL
    assert len(breaker.events) == 0


def test_zero_open_asset_skips_daily_check():
    breaker = CircuitBreaker(max_daily_loss=0.03)
    breaker.set_initial_capital(1_000_000)
    breaker.reset_daily(datetime(2026, 1, 1), day_open_asset=0)

    asset = Asset(account_id="test", total_asset=0)
    breaker.evaluate(asset, [])

    assert breaker.state.status == BreakerStatus.NORMAL
