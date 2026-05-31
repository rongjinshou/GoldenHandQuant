from datetime import datetime
from typing import Any

from src.application.backtest_app import BacktestAppService
from src.domain.backtest.entities.comparison_report import ComparisonReport
from src.domain.backtest.services.comparison_report_service import ComparisonReportService
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.registry import create_strategy


class StrategyComparisonAppService:
    """策略对比应用服务。

    编排多策略回测 → 构建 ComparisonReport → 触发可视化。
    """

    def __init__(
        self,
        backtest_service: BacktestAppService,
        comparison_service: ComparisonReportService,
    ) -> None:
        self.backtest_service = backtest_service
        self.comparison_service = comparison_service

    def run_comparison(
        self,
        strategy_names: list[str],
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        base_timeframe: Timeframe = Timeframe.DAY_1,
        strategy_params: dict[str, dict[str, Any]] | None = None,
    ) -> ComparisonReport:
        """执行多策略对比回测，返回 ComparisonReport。"""
        strategies = [
            create_strategy(name, (strategy_params or {}).get(name))
            for name in strategy_names
        ]

        reports = self.backtest_service.run_backtest(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            base_timeframe=base_timeframe,
            strategies=strategies,
        )

        return self.comparison_service.build_comparison(reports)
