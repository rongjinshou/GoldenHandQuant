from datetime import datetime, timedelta
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.risk.services.system_risk_gate import SystemRiskGate, GateResult
from src.domain.risk.services.risk_policies.limit_up_break_policy import LimitUpBreakPolicy
from src.domain.account.entities.position import Position
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.risk.services.risk_policies.hard_stop_loss_policy import HardStopLossPolicy
from src.domain.risk.services.risk_signal_generator import RiskSignalGenerator
from src.domain.risk.services.base_risk_signal_policy import BaseRiskSignalPolicy
from src.domain.strategy.value_objects.signal import Signal

def _index_bar(dt, close):
    return Bar(symbol="000852.SH", timeframe=Timeframe.DAY_1, timestamp=dt,
               open=close, high=close, low=close, close=close, volume=1e6)

class TestSystemRiskGate:
    def test_passes_when_above_ma20(self):
        bars = [_index_bar(datetime(2024, 6, 1) + timedelta(days=i), 6000) for i in range(25)]
        gate = SystemRiskGate(bars)
        result = gate.check_gate(datetime(2024, 6, 25))
        assert result.pass_buy is True

    def test_blocks_when_below_ma20(self):
        dt = datetime(2024, 6, 1)
        # 19 bars at 6000, then 5 bars dropping to 5000
        bars = [_index_bar(dt + timedelta(days=i), 6000) for i in range(20)]
        bars += [_index_bar(dt + timedelta(days=20 + i), 5000) for i in range(5)]
        gate = SystemRiskGate(bars)
        result = gate.check_gate(datetime(2024, 6, 25))
        assert result.pass_buy is False
        assert "MA20" in result.reason

    def test_passes_with_insufficient_data(self):
        bars = [_index_bar(datetime(2024, 6, 1) + timedelta(days=i), 6000) for i in range(10)]
        gate = SystemRiskGate(bars)
        result = gate.check_gate(datetime(2024, 6, 10))
        assert result.pass_buy is True

    def test_set_index_data_updates_bars(self):
        gate = SystemRiskGate()
        gate.set_index_data([_index_bar(datetime(2024, 6, 1) + timedelta(days=i), 6000) for i in range(20)])
        assert len(gate._index_bars) == 20

class TestLimitUpBreakPolicy:
    def test_triggers_sell_when_limit_up_broken(self):
        policy = LimitUpBreakPolicy()
        pos = Position(account_id="A", ticker="000001.SZ", total_volume=1000, available_volume=1000, average_cost=10.0)
        # prev_close=10.0, limit_up=11.00, high hits 11.00 but close 10.80 < 11.00
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime.now(),
                  open=10.5, high=11.00, low=10.5, close=10.80, volume=1e6, prev_close=10.0)
        signals = policy.evaluate_positions([pos], {"000001.SZ": bar})
        assert len(signals) == 1
        assert signals[0].direction == SignalDirection.SELL
        assert "涨停破板" in signals[0].reason

    def test_no_trigger_when_close_at_limit_up(self):
        policy = LimitUpBreakPolicy()
        pos = Position(account_id="A", ticker="000001.SZ", total_volume=1000, available_volume=1000, average_cost=10.0)
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime.now(),
                  open=10.5, high=11.00, low=10.5, close=11.00, volume=1e6, prev_close=10.0)
        signals = policy.evaluate_positions([pos], {"000001.SZ": bar})
        assert len(signals) == 0

    def test_no_trigger_when_not_touching_limit_up(self):
        policy = LimitUpBreakPolicy()
        pos = Position(account_id="A", ticker="000001.SZ", total_volume=1000, available_volume=1000, average_cost=10.0)
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime.now(),
                  open=10.5, high=10.90, low=10.5, close=10.80, volume=1e6, prev_close=10.0)
        signals = policy.evaluate_positions([pos], {"000001.SZ": bar})
        assert len(signals) == 0

class TestHardStopLossPolicy:
    def test_triggers_sell_when_loss_exceeds_threshold(self):
        policy = HardStopLossPolicy(max_loss_ratio=0.03)
        pos = Position(account_id="A", ticker="000001.SZ", total_volume=1000, available_volume=1000, average_cost=10.0)
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime.now(),
                  open=9.0, high=9.0, low=9.0, close=9.50, volume=1e6)
        # loss = (9.50 - 10.0) / 10.0 = -5% > -3%
        signals = policy.evaluate_positions([pos], {"000001.SZ": bar})
        assert len(signals) == 1
        assert signals[0].direction == SignalDirection.SELL

    def test_no_trigger_when_loss_within_threshold(self):
        policy = HardStopLossPolicy(max_loss_ratio=0.03)
        pos = Position(account_id="A", ticker="000001.SZ", total_volume=1000, available_volume=1000, average_cost=10.0)
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime.now(),
                  open=9.8, high=9.8, low=9.8, close=9.80, volume=1e6)
        # loss = (9.80 - 10.0) / 10.0 = -2% > -3%, no trigger
        signals = policy.evaluate_positions([pos], {"000001.SZ": bar})
        assert len(signals) == 0

    def test_no_trigger_when_profitable(self):
        policy = HardStopLossPolicy(max_loss_ratio=0.03)
        pos = Position(account_id="A", ticker="000001.SZ", total_volume=1000, available_volume=1000, average_cost=10.0)
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime.now(),
                  open=11.0, high=11.0, low=11.0, close=11.0, volume=1e6)
        signals = policy.evaluate_positions([pos], {"000001.SZ": bar})
        assert len(signals) == 0

class _FakePolicy(BaseRiskSignalPolicy):
    def __init__(self, signals):
        self.signals = signals
    def evaluate_positions(self, positions, bars):
        return self.signals

class TestRiskSignalGenerator:
    def test_aggregates_all_policy_signals(self):
        p1 = _FakePolicy([Signal(symbol="A", direction=SignalDirection.SELL, confidence_score=1.0, strategy_name="P1")])
        p2 = _FakePolicy([Signal(symbol="B", direction=SignalDirection.SELL, confidence_score=1.0, strategy_name="P2")])
        gen = RiskSignalGenerator([p1, p2])
        signals = gen.evaluate([], {})
        assert len(signals) == 2

    def test_empty_policies_returns_empty(self):
        gen = RiskSignalGenerator()
        assert gen.evaluate([], {}) == []
