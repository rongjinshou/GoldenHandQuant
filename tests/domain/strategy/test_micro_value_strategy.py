from datetime import datetime
from src.domain.account.entities.position import Position
from src.domain.strategy.services.strategies.micro_value_strategy import MicroValueStrategy
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.market.value_objects.stock_snapshot import StockSnapshot

def _snap(symbol, mcap, close=10.2, **kwargs):
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 6, 11),  # Tuesday
        open=10.0, high=10.5, low=9.8, close=close, volume=1e6,
        name="Normal Stock", list_date=datetime(2000, 1, 1),
        market_cap=mcap, roe_ttm=0.20, ocf_ttm=1e8, **kwargs
    )

class TestMicroValueStrategy:
    def test_calendar_circuit_breaker_january_returns_empty(self):
        strategy = MicroValueStrategy(top_n=5)
        universe = [_snap("A", 1e9), _snap("B", 2e9), _snap("C", 3e9), _snap("D", 4e9), _snap("E", 5e9)]
        jan_date = datetime(2024, 1, 9)  # Tuesday in January
        signals = strategy.generate_cross_sectional_signals(universe, [], jan_date)
        assert signals == []

    def test_calendar_circuit_breaker_april_returns_empty(self):
        strategy = MicroValueStrategy(top_n=5)
        universe = [_snap("A", 1e9) for _ in range(5)]
        apr_date = datetime(2024, 4, 9)  # Tuesday in April
        signals = strategy.generate_cross_sectional_signals(universe, [], apr_date)
        assert signals == []

    def test_non_tuesday_no_positions_returns_empty(self):
        # 非调仓日且无持仓 → 空(无可维持的持仓)
        strategy = MicroValueStrategy(top_n=5)
        universe = [_snap("A", 1e9) for _ in range(10)]
        monday = datetime(2024, 6, 10)  # Monday
        signals = strategy.generate_cross_sectional_signals(universe, [], monday)
        assert signals == []

    def test_non_tuesday_holds_existing_positions(self):
        # 非调仓日维持现有持仓(返回持仓为 BUY 目标), 而非空目标——
        # 否则等权 sizer 把空目标当清仓信号 → 买周二、卖周三的 1 日 churn。
        strategy = MicroValueStrategy(top_n=5)
        universe = [_snap("A", 1e9) for _ in range(10)]
        positions = [
            Position(account_id="BT", ticker="X", total_volume=100, available_volume=100),
            Position(account_id="BT", ticker="Y", total_volume=200, available_volume=200),
        ]
        monday = datetime(2024, 6, 10)  # Monday
        signals = strategy.generate_cross_sectional_signals(universe, positions, monday)
        assert {s.symbol for s in signals} == {"X", "Y"}
        assert all(s.direction == SignalDirection.BUY for s in signals)

    def test_non_tuesday_does_not_rebalance_to_smallest(self):
        # 非调仓日只维持现有持仓, 不切换到当前最小 top_n(只有周二才调仓)。
        strategy = MicroValueStrategy(top_n=2)
        universe = [_snap("A", 1e9), _snap("B", 2e9), _snap("C", 3e9)]  # 最小是 A,B
        positions = [Position(account_id="BT", ticker="C", total_volume=100, available_volume=100)]
        monday = datetime(2024, 6, 10)  # Monday
        signals = strategy.generate_cross_sectional_signals(universe, positions, monday)
        assert {s.symbol for s in signals} == {"C"}  # 维持 C, 不换成 A/B

    def test_tuesday_produces_top_n_buy_signals(self):
        strategy = MicroValueStrategy(top_n=3)
        universe = [
            _snap("B", 2e9), _snap("A", 1e9), _snap("D", 4e9),
            _snap("C", 3e9), _snap("E", 5e9),
        ]
        tuesday = datetime(2024, 6, 11)  # Tuesday
        signals = strategy.generate_cross_sectional_signals(universe, [], tuesday)
        assert len(signals) == 3
        # Should be A, B, C (mcap: 1e9, 2e9, 3e9)
        assert signals[0].symbol == "A"
        assert signals[1].symbol == "B"
        assert signals[2].symbol == "C"
        for s in signals:
            assert s.direction == SignalDirection.BUY
            assert s.strategy_name == "MicroValueStrategy"

    def test_filters_penny_stocks_before_ranking(self):
        strategy = MicroValueStrategy(top_n=3)
        universe = [
            _snap("Penny", 1e8, close=1.0),  # filtered out
            _snap("A", 1e9, close=10.0),
            _snap("B", 2e9, close=10.0),
            _snap("C", 3e9, close=10.0),
            _snap("D", 4e9, close=10.0),
        ]
        tuesday = datetime(2024, 6, 11)
        signals = strategy.generate_cross_sectional_signals(universe, [], tuesday)
        assert len(signals) == 3
        assert "Penny" not in {s.symbol for s in signals}

    def test_name_property(self):
        assert MicroValueStrategy().name == "MicroValueStrategy"

    def test_does_not_use_bar_history(self):
        # MicroValue 只用 market_cap + 过滤字段, 不需要技术指标 →
        # 声明 uses_bar_history=False, 让回测跳过逐股指标重算(避免 stock_features 已有的重复 O(n²) 计算)。
        assert MicroValueStrategy().uses_bar_history is False
