from datetime import datetime

import pytest

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.strategy.pool.services.pool_manager import PoolManager
from src.domain.strategy.pool.value_objects.performance_snapshot import PerformanceSnapshot
from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating
from src.domain.strategy.services.strategy_lifecycle_manager import (
    StrategyLifecycleEntry,
    StrategyLifecycleManager,
)
from src.domain.strategy.value_objects.strategy_lifecycle_status import StrategyLifecycleStatus
from src.infrastructure.persistence.memory_strategy_pool_repo import MemoryStrategyPoolRepository


def _make_report(**kwargs):
    defaults = dict(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 12, 31),
        initial_capital=1_000_000,
        final_capital=1_100_000,
        total_return=0.10,
        annualized_return=0.10,
        max_drawdown=0.08,
        win_rate=0.60,
        profit_loss_ratio=1.5,
        trade_count=50,
        strategy_name="dual_ma",
    )
    defaults.update(kwargs)
    return BacktestReport(**defaults)


def _make_good_report():
    """创建高分报告（评级 A/B）。sharpe_ratio 是计算属性，需通过有波动的 daily_returns 控制。"""
    # 正均值 + 低波动 → 高夏普
    daily_returns = [0.001 + (i % 5 - 2) * 0.005 for i in range(252)]
    return _make_report(
        max_drawdown=0.05,
        win_rate=0.70,
        daily_returns=daily_returns,
    )


def _make_bad_report():
    """创建低分报告（评级 C/D）。"""
    # 负均值 + 高波动 → 低夏普
    daily_returns = [-0.001 + (i % 3 - 1) * 0.02 for i in range(252)]
    return _make_report(
        max_drawdown=0.30,
        win_rate=0.30,
        daily_returns=daily_returns,
    )


class TestStrategyLifecycleEntry:
    def test_default_status_is_candidate(self):
        entry = StrategyLifecycleEntry(strategy_name="test")
        assert entry.status == StrategyLifecycleStatus.CANDIDATE

    def test_valid_transition_candidate_to_backtesting(self):
        entry = StrategyLifecycleEntry(strategy_name="test")
        entry.transition_to(StrategyLifecycleStatus.BACKTESTING)
        assert entry.status == StrategyLifecycleStatus.BACKTESTING

    def test_valid_transition_backtesting_to_evaluating(self):
        entry = StrategyLifecycleEntry(strategy_name="test")
        entry.transition_to(StrategyLifecycleStatus.BACKTESTING)
        entry.transition_to(StrategyLifecycleStatus.EVALUATING)
        assert entry.status == StrategyLifecycleStatus.EVALUATING

    def test_valid_transition_evaluating_to_active(self):
        entry = StrategyLifecycleEntry(strategy_name="test")
        entry.transition_to(StrategyLifecycleStatus.BACKTESTING)
        entry.transition_to(StrategyLifecycleStatus.EVALUATING)
        entry.transition_to(StrategyLifecycleStatus.ACTIVE)
        assert entry.status == StrategyLifecycleStatus.ACTIVE

    def test_valid_transition_active_to_paused(self):
        entry = StrategyLifecycleEntry(strategy_name="test")
        entry.transition_to(StrategyLifecycleStatus.BACKTESTING)
        entry.transition_to(StrategyLifecycleStatus.EVALUATING)
        entry.transition_to(StrategyLifecycleStatus.ACTIVE)
        entry.transition_to(StrategyLifecycleStatus.PAUSED)
        assert entry.status == StrategyLifecycleStatus.PAUSED

    def test_valid_transition_paused_to_active(self):
        entry = StrategyLifecycleEntry(strategy_name="test")
        entry.transition_to(StrategyLifecycleStatus.BACKTESTING)
        entry.transition_to(StrategyLifecycleStatus.EVALUATING)
        entry.transition_to(StrategyLifecycleStatus.ACTIVE)
        entry.transition_to(StrategyLifecycleStatus.PAUSED)
        entry.transition_to(StrategyLifecycleStatus.ACTIVE)
        assert entry.status == StrategyLifecycleStatus.ACTIVE

    def test_invalid_transition_raises(self):
        entry = StrategyLifecycleEntry(strategy_name="test")
        with pytest.raises(ValueError, match="Invalid lifecycle transition"):
            entry.transition_to(StrategyLifecycleStatus.ACTIVE)

    def test_retired_is_terminal(self):
        entry = StrategyLifecycleEntry(strategy_name="test")
        entry.transition_to(StrategyLifecycleStatus.RETIRED)
        assert entry.status == StrategyLifecycleStatus.RETIRED
        with pytest.raises(ValueError, match="Invalid lifecycle transition"):
            entry.transition_to(StrategyLifecycleStatus.ACTIVE)

    def test_transition_sets_reason_and_timestamp(self):
        entry = StrategyLifecycleEntry(strategy_name="test")
        old_ts = entry.updated_at
        entry.transition_to(StrategyLifecycleStatus.BACKTESTING, reason="test reason")
        assert entry.reason == "test reason"
        assert entry.updated_at >= old_ts

    def test_update_rating(self):
        entry = StrategyLifecycleEntry(strategy_name="test")
        entry.update_rating(StrategyRating.A, reason="good performance")
        assert entry.rating == StrategyRating.A
        assert entry.reason == "good performance"


class TestStrategyLifecycleManager:
    def setup_method(self):
        self.repo = MemoryStrategyPoolRepository()
        self.pool_mgr = PoolManager(repo=self.repo)
        self.mgr = StrategyLifecycleManager(pool_manager=self.pool_mgr)

    def test_register_and_backtest(self):
        entry = self.mgr.register_and_backtest(
            name="dual_ma",
            strategy_type="bar",
            description="Dual MA strategy",
        )
        assert entry.status == StrategyLifecycleStatus.BACKTESTING
        assert entry.strategy_name == "dual_ma"
        # 同步注册到策略池
        pool_entry = self.repo.find_by_name("dual_ma")
        assert pool_entry is not None

    def test_register_unknown_strategy_raises(self):
        with pytest.raises(KeyError, match="Unknown strategy"):
            self.mgr.register_and_backtest(
                name="nonexistent",
                strategy_type="bar",
                description="does not exist",
            )

    def test_process_evaluation_activates_when_rating_meets_threshold(self):
        self.mgr.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        report = _make_good_report()
        entry = self.mgr.process_evaluation(
            name="dual_ma",
            report=report,
            min_rating=StrategyRating.B,
        )
        # 评级应为 A 或 B（高分参数），应激活
        assert entry.status == StrategyLifecycleStatus.ACTIVE
        assert entry.rating in (StrategyRating.A, StrategyRating.B)

    def test_process_evaluation_pauses_when_rating_below_threshold(self):
        self.mgr.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        report = _make_bad_report()
        entry = self.mgr.process_evaluation(
            name="dual_ma",
            report=report,
            min_rating=StrategyRating.B,
        )
        # 低分参数，评级应为 C 或 D，应暂停
        assert entry.status == StrategyLifecycleStatus.PAUSED
        assert entry.rating in (StrategyRating.C, StrategyRating.D)

    def test_process_evaluation_unknown_strategy_raises(self):
        report = _make_report()
        with pytest.raises(KeyError, match="Strategy not in lifecycle"):
            self.mgr.process_evaluation(name="nonexistent", report=report)

    def test_check_performance_no_active_entries(self):
        result = self.mgr.check_performance()
        assert result == {"paused": [], "retired": []}

    def test_check_performance_auto_pause_on_d_rating(self):
        self.mgr.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        # 先上线
        report = _make_good_report()
        self.mgr.process_evaluation(name="dual_ma", report=report, min_rating=StrategyRating.D)
        assert self.mgr.get_entry("dual_ma").status == StrategyLifecycleStatus.ACTIVE

        # 提供 D 级报告
        bad_report = _make_bad_report()
        result = self.mgr.check_performance(
            active_entries=[("dual_ma", bad_report)],
        )
        entry = self.mgr.get_entry("dual_ma")
        if entry.status == StrategyLifecycleStatus.PAUSED:
            assert "dual_ma" in result["paused"]

    def test_check_performance_auto_retire_on_consecutive_d(self):
        self.mgr.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        # 先上线
        report = _make_good_report()
        self.mgr.process_evaluation(name="dual_ma", report=report, min_rating=StrategyRating.D)

        # 手动在策略池中累积 4 次 D 级快照以触发 auto_retire
        pool_entry = self.repo.find_by_name("dual_ma")
        for _ in range(4):
            pool_entry.add_snapshot(PerformanceSnapshot(
                evaluated_at=datetime(2026, 1, 1),
                period_start=datetime(2025, 12, 1),
                period_end=datetime(2025, 12, 31),
                total_return=0.01,
                annualized_return=0.05,
                sharpe_ratio=0.1,
                max_drawdown=0.35,
                win_rate=0.20,
                trade_count=10,
                composite_score=15.0,
                rating=StrategyRating.D,
                underperform_weeks=4,
            ))
        self.repo.save(pool_entry)

        result = self.mgr.check_performance()
        assert "dual_ma" in result["retired"]
        assert self.mgr.get_entry("dual_ma").status == StrategyLifecycleStatus.RETIRED

    def test_reactivate(self):
        self.mgr.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        report = _make_good_report()
        self.mgr.process_evaluation(name="dual_ma", report=report, min_rating=StrategyRating.D)
        # 暂停
        entry = self.mgr.get_entry("dual_ma")
        entry.transition_to(StrategyLifecycleStatus.PAUSED)

        # 重新激活
        entry = self.mgr.reactivate("dual_ma")
        assert entry.status == StrategyLifecycleStatus.ACTIVE

    def test_retire(self):
        self.mgr.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        entry = self.mgr.retire("dual_ma", reason="manual decision")
        assert entry.status == StrategyLifecycleStatus.RETIRED
        assert entry.reason == "manual decision"

    def test_get_entry_returns_none_for_unknown(self):
        assert self.mgr.get_entry("nonexistent") is None

    def test_get_entries_by_status(self):
        self.mgr.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        backtesting = self.mgr.get_entries_by_status(StrategyLifecycleStatus.BACKTESTING)
        assert len(backtesting) == 1

    def test_get_active_strategies(self):
        self.mgr.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        report = _make_good_report()
        self.mgr.process_evaluation(name="dual_ma", report=report, min_rating=StrategyRating.D)
        active = self.mgr.get_active_strategies()
        assert len(active) == 1

    def test_get_summary(self):
        self.mgr.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        summary = self.mgr.get_summary()
        assert summary["total"] == 1
        assert summary["by_status"]["BACKTESTING"] == 1
