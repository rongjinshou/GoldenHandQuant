from datetime import datetime

from src.application.strategy_lifecycle_app import StrategyLifecycleAppService
from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.strategy.pool.services.pool_manager import PoolManager
from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating
from src.domain.strategy.services.strategy_lifecycle_manager import StrategyLifecycleManager
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
    daily_returns = [0.001 + (i % 5 - 2) * 0.005 for i in range(252)]
    return _make_report(
        max_drawdown=0.05,
        win_rate=0.70,
        daily_returns=daily_returns,
    )


def _make_bad_report():
    """创建低分报告（评级 C/D）。"""
    daily_returns = [-0.001 + (i % 3 - 1) * 0.02 for i in range(252)]
    return _make_report(
        max_drawdown=0.30,
        win_rate=0.30,
        daily_returns=daily_returns,
    )


class TestStrategyLifecycleAppService:
    def setup_method(self):
        self.repo = MemoryStrategyPoolRepository()
        self.pool_mgr = PoolManager(repo=self.repo)
        self.lifecycle_mgr = StrategyLifecycleManager(pool_manager=self.pool_mgr)
        self.app = StrategyLifecycleAppService(
            lifecycle_manager=self.lifecycle_mgr,
            min_active_rating=StrategyRating.B,
        )

    def test_register_and_backtest(self):
        entry = self.app.register_and_backtest(
            name="dual_ma",
            strategy_type="bar",
            description="Dual MA strategy",
        )
        assert entry.status == StrategyLifecycleStatus.BACKTESTING
        assert self.app.get_lifecycle_status("dual_ma") == StrategyLifecycleStatus.BACKTESTING

    def test_complete_backtest_activates_when_meets_threshold(self):
        self.app.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        report = _make_good_report()
        entry = self.app.complete_backtest(name="dual_ma", report=report)
        assert entry.status == StrategyLifecycleStatus.ACTIVE
        assert self.app.get_lifecycle_status("dual_ma") == StrategyLifecycleStatus.ACTIVE

    def test_complete_backtest_pauses_when_below_threshold(self):
        self.app.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        report = _make_bad_report()
        entry = self.app.complete_backtest(name="dual_ma", report=report)
        assert entry.status == StrategyLifecycleStatus.PAUSED
        assert self.app.get_lifecycle_status("dual_ma") == StrategyLifecycleStatus.PAUSED

    def test_check_performance_returns_actions(self):
        # 使用 D 级阈值以便高分报告能激活
        repo = MemoryStrategyPoolRepository()
        pool_mgr = PoolManager(repo=repo)
        lifecycle = StrategyLifecycleManager(pool_manager=pool_mgr)
        app = StrategyLifecycleAppService(
            lifecycle_manager=lifecycle,
            min_active_rating=StrategyRating.D,
        )

        app.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        # 先激活（用高分报告）
        good_report = _make_good_report()
        app.complete_backtest(name="dual_ma", report=good_report)
        assert app.get_lifecycle_status("dual_ma") == StrategyLifecycleStatus.ACTIVE

        # 用低分报告检查
        bad_report = _make_bad_report()
        result = app.check_performance(active_reports=[("dual_ma", bad_report)])
        assert "paused" in result
        assert "retired" in result

    def test_get_active_strategies(self):
        # 使用 D 级阈值以便高分报告能激活
        repo = MemoryStrategyPoolRepository()
        pool_mgr = PoolManager(repo=repo)
        lifecycle = StrategyLifecycleManager(pool_manager=pool_mgr)
        app = StrategyLifecycleAppService(
            lifecycle_manager=lifecycle,
            min_active_rating=StrategyRating.D,
        )

        app.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        report = _make_good_report()
        app.complete_backtest(name="dual_ma", report=report)
        active = app.get_active_strategies()
        assert len(active) == 1
        assert active[0].strategy_name == "dual_ma"

    def test_get_summary(self):
        self.app.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        summary = self.app.get_summary()
        assert summary["total"] == 1
        assert summary["by_status"]["BACKTESTING"] == 1

    def test_get_lifecycle_status_unknown_returns_none(self):
        assert self.app.get_lifecycle_status("nonexistent") is None

    def test_full_pipeline_candidate_to_active(self):
        """完整流水线: CANDIDATE → BACKTESTING → EVALUATING → ACTIVE。"""
        entry = self.app.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        assert entry.status == StrategyLifecycleStatus.BACKTESTING

        report = _make_good_report()
        entry = self.app.complete_backtest(name="dual_ma", report=report)
        assert entry.status == StrategyLifecycleStatus.ACTIVE

    def test_full_pipeline_candidate_to_paused(self):
        """完整流水线: CANDIDATE → BACKTESTING → EVALUATING → PAUSED。"""
        entry = self.app.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        assert entry.status == StrategyLifecycleStatus.BACKTESTING

        # 低分报告，app 默认阈值为 B，低分报告评级为 C/D → PAUSED
        report = _make_bad_report()
        entry = self.app.complete_backtest(name="dual_ma", report=report)
        assert entry.status == StrategyLifecycleStatus.PAUSED

    def test_with_capital_engine(self):
        """集成 CapitalAllocationEngine 的完整流程。"""
        from src.domain.portfolio.entities.strategy_allocation import StrategyAllocation

        class EqualWeightAlgorithm:
            def calculate(self, total_capital, performances, current=None):
                n = len(performances)
                w = 1.0 / n if n > 0 else 0
                now = datetime.now()
                return [
                    StrategyAllocation(
                        strategy_name=p.strategy_name,
                        allocated_capital=round(total_capital * w, 2),
                        weight=w,
                        allocated_at=now,
                        reason="equal_weight",
                    )
                    for p in performances
                ]

        class NeverTrigger:
            def should_rebalance(self, current_date, last_rebalance):
                return False
            def record_rebalance(self, date):
                pass

        from src.domain.portfolio.services.capital_allocation_engine import CapitalAllocationEngine
        capital_engine = CapitalAllocationEngine(
            algorithm=EqualWeightAlgorithm(),
            trigger=NeverTrigger(),
        )

        app = StrategyLifecycleAppService(
            lifecycle_manager=self.lifecycle_mgr,
            capital_engine=capital_engine,
            total_capital=1_000_000,
            min_active_rating=StrategyRating.D,
        )

        app.register_and_backtest(
            name="dual_ma", strategy_type="bar", description="test",
        )
        report = _make_good_report()
        entry = app.complete_backtest(name="dual_ma", report=report)
        assert entry.status == StrategyLifecycleStatus.ACTIVE
