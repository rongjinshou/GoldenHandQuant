from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.strategy.pool.entities.strategy_pool_entry import StrategyPoolEntry
from src.domain.strategy.pool.interfaces.strategy_pool_repository import IStrategyPoolRepository
from src.domain.strategy.pool.services.rating_engine import RatingEngine
from src.domain.strategy.pool.value_objects.strategy_status import StrategyStatus


class PoolManager:
    """策略池管理器 -- 协调策略生命周期。"""

    def __init__(
        self,
        repo: IStrategyPoolRepository,
        rating_engine: RatingEngine | None = None,
    ) -> None:
        self._repo = repo
        self._engine = rating_engine or RatingEngine()

    def register(
        self,
        name: str,
        strategy_type: str,
        description: str,
        params: dict[str, object] | None = None,
    ) -> StrategyPoolEntry:
        """注册新策略到策略池。

        Args:
            name: 策略名称（需已在 registry 中注册）。
            strategy_type: 策略类型。
            description: 策略描述。
            params: 策略参数。

        Returns:
            创建的策略池条目。
        """
        from src.domain.strategy.registry import get_strategy

        get_strategy(name)  # 不存在则抛 KeyError

        entry = StrategyPoolEntry(
            strategy_name=name,
            strategy_type=strategy_type,
            description=description,
            registered_at=datetime.now(),
            params=params or {},
        )
        self._repo.save(entry)
        return entry

    def evaluate_strategy(
        self,
        name: str,
        report: BacktestReport,
        benchmark_return: float = 0.0,
        underperform_weeks: int = 0,
    ) -> StrategyPoolEntry:
        """评估策略并更新评级。"""
        entry = self._repo.find_by_name(name)
        if entry is None:
            raise KeyError(f"Strategy not in pool: {name}")

        snapshot = self._engine.evaluate(
            report=report,
            benchmark_return=benchmark_return,
            underperform_weeks=underperform_weeks,
        )
        entry.add_snapshot(snapshot)
        entry.update_rating(snapshot.rating)
        self._repo.save(entry)
        return entry

    def check_auto_retire(self) -> list[StrategyPoolEntry]:
        """检查所有 ACTIVE 策略，返回应自动下线的策略列表。"""
        active = self._repo.find_by_status(StrategyStatus.ACTIVE)
        return [e for e in active if e.should_auto_retire]

    def get_active_strategies(self) -> list[StrategyPoolEntry]:
        """获取所有上线策略。"""
        return self._repo.find_by_status(StrategyStatus.ACTIVE)

    def get_pool_summary(self) -> dict[str, object]:
        """获取策略池汇总信息。"""
        all_entries = self._repo.find_all()
        by_status: dict[str, int] = {}
        by_rating: dict[str, int] = {}
        for e in all_entries:
            by_status[e.status] = by_status.get(e.status, 0) + 1
            by_rating[e.rating] = by_rating.get(e.rating, 0) + 1
        return {
            "total": len(all_entries),
            "by_status": by_status,
            "by_rating": by_rating,
            "tradeable": sum(1 for e in all_entries if e.is_tradeable),
            "should_retire": sum(1 for e in all_entries if e.should_auto_retire),
        }
