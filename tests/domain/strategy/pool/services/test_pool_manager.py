import pytest
from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.strategy.pool.services.pool_manager import PoolManager
from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating
from src.domain.strategy.pool.value_objects.strategy_status import StrategyStatus
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


class TestPoolManager:
    def setup_method(self):
        self.repo = MemoryStrategyPoolRepository()
        self.mgr = PoolManager(repo=self.repo)

    def test_register_creates_candidate(self):
        entry = self.mgr.register(
            name="dual_ma",
            strategy_type="bar",
            description="Dual MA strategy",
        )
        assert entry.status == StrategyStatus.CANDIDATE
        assert entry.strategy_name == "dual_ma"

    def test_register_unknown_strategy_raises(self):
        with pytest.raises(KeyError, match="Unknown strategy"):
            self.mgr.register(
                name="nonexistent",
                strategy_type="bar",
                description="does not exist",
            )

    def test_evaluate_strategy_updates_rating(self):
        self.mgr.register(
            name="dual_ma",
            strategy_type="bar",
            description="test",
        )
        report = _make_report()
        entry = self.mgr.evaluate_strategy("dual_ma", report)
        assert len(entry.snapshots) == 1
        assert entry.rating in (StrategyRating.A, StrategyRating.B, StrategyRating.C, StrategyRating.D)

    def test_evaluate_unknown_strategy_raises(self):
        report = _make_report()
        with pytest.raises(KeyError, match="Strategy not in pool"):
            self.mgr.evaluate_strategy("nonexistent", report)

    def test_check_auto_retire(self):
        self.mgr.register(name="dual_ma", strategy_type="bar", description="test")
        entry = self.repo.find_by_name("dual_ma")
        entry.status = StrategyStatus.ACTIVE
        self.repo.save(entry)

        from src.domain.strategy.pool.value_objects.performance_snapshot import PerformanceSnapshot
        for _ in range(4):
            entry.add_snapshot(PerformanceSnapshot(
                evaluated_at=datetime(2026, 1, 1),
                period_start=datetime(2025, 12, 1),
                period_end=datetime(2025, 12, 31),
                total_return=0.01,
                annualized_return=0.05,
                sharpe_ratio=0.3,
                max_drawdown=0.20,
                win_rate=0.35,
                trade_count=10,
                composite_score=20.0,
                rating=StrategyRating.D,
                underperform_weeks=4,
            ))
        self.repo.save(entry)

        candidates = self.mgr.check_auto_retire()
        assert len(candidates) == 1
        assert candidates[0].strategy_name == "dual_ma"

    def test_get_active_strategies(self):
        self.mgr.register(name="dual_ma", strategy_type="bar", description="test")
        entry = self.repo.find_by_name("dual_ma")
        entry.activate()
        self.repo.save(entry)

        active = self.mgr.get_active_strategies()
        assert len(active) == 1

    def test_get_pool_summary(self):
        self.mgr.register(name="dual_ma", strategy_type="bar", description="test")
        summary = self.mgr.get_pool_summary()
        assert summary["total"] == 1
        assert summary["by_status"]["CANDIDATE"] == 1
