"""分层回测引擎：按因子值将股票分组，计算各组收益。"""

from dataclasses import dataclass

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.evaluator import FactorExpressionEvaluator
from src.domain.strategy.factor_test.expressions import Expr


@dataclass(frozen=True, slots=True, kw_only=True)
class LayerBacktestResult:
    """分层回测结果。"""
    layer_count: int
    layer_returns: list[float]         # 各层年化收益率（从低到高）
    long_short_return: float           # 多空年化收益
    layer_cumulative: list[list[float]]  # 各层累计收益曲线
    monotonicity_score: float          # 0-1 单调性


class LayerBacktester:
    """分层回测器。"""

    def __init__(self) -> None:
        self._evaluator = FactorExpressionEvaluator()

    def run(
        self,
        expression: Expr,
        snapshots_by_date: dict[str, list[StockSnapshot]],
        returns_by_date: dict[str, dict[str, float]],
        num_layers: int = 5,
    ) -> LayerBacktestResult:
        """执行分层回测。

        Args:
            expression: 因子表达式 AST
            snapshots_by_date: {date_str: [StockSnapshot, ...]}
            returns_by_date: {date_str: {symbol: return_value}}
            num_layers: 分层数

        Returns:
            LayerBacktestResult
        """
        # 每日各层收益
        layer_daily_returns: list[list[float]] = [[] for _ in range(num_layers)]

        for date_str in sorted(snapshots_by_date.keys()):
            next_date = self._next_date(date_str, returns_by_date)
            if next_date is None:
                continue

            snapshots = snapshots_by_date[date_str]
            factor_values = self._evaluator.evaluate(expression, snapshots)
            next_returns = returns_by_date.get(next_date, {})

            # 过滤有因子值和下期收益的股票
            common = sorted(set(factor_values) & set(next_returns))
            if len(common) < num_layers:
                continue

            # 按因子值排序并分层
            items = [(s, factor_values[s], next_returns[s]) for s in common]
            items.sort(key=lambda x: x[1])

            group_size = len(items) // num_layers
            for layer_idx in range(num_layers):
                start = layer_idx * group_size
                end = start + group_size if layer_idx < num_layers - 1 else len(items)
                group_returns = [item[2] for item in items[start:end]]
                if group_returns:
                    avg_ret = sum(group_returns) / len(group_returns)
                    layer_daily_returns[layer_idx].append(avg_ret)

        # 计算各层累计收益
        layer_cumulative: list[list[float]] = []
        for layer_idx in range(num_layers):
            cum = [1.0]
            for r in layer_daily_returns[layer_idx]:
                cum.append(cum[-1] * (1 + r))
            layer_cumulative.append(cum)

        # 计算年化收益率
        trading_days_per_year = 244
        layer_annual_returns: list[float] = []
        for layer_idx in range(num_layers):
            n_days = len(layer_daily_returns[layer_idx])
            if n_days > 0:
                total_ret = layer_cumulative[layer_idx][-1] / layer_cumulative[layer_idx][0] - 1
                annual = (1 + total_ret) ** (trading_days_per_year / n_days) - 1
            else:
                annual = 0.0
            layer_annual_returns.append(annual)

        long_short = layer_annual_returns[-1] - layer_annual_returns[0] if layer_annual_returns else 0.0
        mono = self._monotonicity_score(layer_annual_returns)

        return LayerBacktestResult(
            layer_count=num_layers,
            layer_returns=layer_annual_returns,
            long_short_return=long_short,
            layer_cumulative=layer_cumulative,
            monotonicity_score=mono,
        )

    def _next_date(self, date_str: str, returns_by_date: dict[str, dict[str, float]]) -> str | None:
        sorted_dates = sorted(returns_by_date.keys())
        for d in sorted_dates:
            if d > date_str:
                return d
        return None

    @staticmethod
    def _monotonicity_score(returns: list[float]) -> float:
        """计算单调性得分 (0-1)。

        完美单调递增 = 1.0，完全无序 = 0.0。
        用相邻对的单调比例衡量。
        """
        n = len(returns)
        if n < 2:
            return 0.0
        monotone_count = sum(1 for i in range(n - 1) if returns[i + 1] >= returns[i])
        return monotone_count / (n - 1)
