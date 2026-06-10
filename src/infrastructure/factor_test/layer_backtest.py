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
        cost_rate: float = 0.003,
        rebalance_days: int = 1,
    ) -> LayerBacktestResult:
        """执行分层回测。

        Args:
            expression: 因子表达式 AST
            snapshots_by_date: {date_str: [StockSnapshot, ...]}
            returns_by_date: {date_str: {symbol: return_value}}
            num_layers: 分层数
            cost_rate: 单边换手往返成本率
            rebalance_days: 调仓间隔(交易日)。1=每日重排; N>1 时持有期内
                沿用既有成员、按日累积收益、不计换手成本。

        Returns:
            LayerBacktestResult
        """
        # 每日各层: 毛收益 + 换手率 (用于扣成本)
        layer_daily_gross: list[list[float]] = [[] for _ in range(num_layers)]
        layer_daily_turnover: list[list[float]] = [[] for _ in range(num_layers)]
        members: list[set[str]] = [set() for _ in range(num_layers)]
        has_membership = False
        days_held = 0

        for date_str in sorted(snapshots_by_date.keys()):
            next_date = self._next_date(date_str, returns_by_date)
            if next_date is None:
                continue

            next_returns = returns_by_date.get(next_date, {})
            day_turnover = [0.0] * num_layers

            if not has_membership or days_held >= rebalance_days:
                factor_values = self._evaluator.evaluate(
                    expression, snapshots_by_date[date_str]
                )
                # 过滤有因子值和下期收益的股票
                common = sorted(set(factor_values) & set(next_returns))
                if len(common) >= num_layers:
                    # 按因子值排序并重新分层
                    items = [(s, factor_values[s]) for s in common]
                    items.sort(key=lambda x: x[1])
                    group_size = len(items) // num_layers
                    for layer_idx in range(num_layers):
                        start = layer_idx * group_size
                        end = start + group_size if layer_idx < num_layers - 1 else len(items)
                        new_members = {sym for sym, _ in items[start:end]}
                        # 换手率: 相对上次调仓该层新进成员占比 (首次建仓=1.0)
                        if members[layer_idx]:
                            day_turnover[layer_idx] = (
                                len(new_members - members[layer_idx]) / len(new_members)
                            )
                        else:
                            day_turnover[layer_idx] = 1.0
                        members[layer_idx] = new_members
                    has_membership = True
                    days_held = 0
                elif not has_membership:
                    continue  # 尚无持仓且截面不足以建仓 → 跳过该日
                # else: 截面不足, 持有现有成员过渡, 下一日继续尝试调仓

            # 按日累积持有成员的收益 (持有期内成员可能停牌缺收益, 取有收益者均值)
            for layer_idx in range(num_layers):
                rets = [next_returns[s] for s in members[layer_idx] if s in next_returns]
                avg_ret = sum(rets) / len(rets) if rets else 0.0
                layer_daily_gross[layer_idx].append(avg_ret)
                layer_daily_turnover[layer_idx].append(day_turnover[layer_idx])
            days_held += 1

        # 各层净收益 (扣换手成本, 长仓口径) → 累计 → 年化
        trading_days_per_year = 244
        layer_cumulative: list[list[float]] = []
        layer_annual_returns: list[float] = []
        for layer_idx in range(num_layers):
            nets = [
                g - t * cost_rate
                for g, t in zip(layer_daily_gross[layer_idx], layer_daily_turnover[layer_idx])
            ]
            cum = [1.0]
            for r in nets:
                cum.append(cum[-1] * (1 + r))
            layer_cumulative.append(cum)
            n_days = len(nets)
            if n_days > 0:
                total_ret = cum[-1] / cum[0] - 1
                annual = (1 + total_ret) ** (trading_days_per_year / n_days) - 1
            else:
                annual = 0.0
            layer_annual_returns.append(annual)

        # 多空: 顶层做多 + 底层做空, 两腿均扣换手成本
        long_short = self._long_short_net(
            layer_daily_gross, layer_daily_turnover, num_layers,
            cost_rate, trading_days_per_year,
        )
        mono = self._monotonicity_score(layer_annual_returns)

        return LayerBacktestResult(
            layer_count=num_layers,
            layer_returns=layer_annual_returns,
            long_short_return=long_short,
            layer_cumulative=layer_cumulative,
            monotonicity_score=mono,
        )

    @staticmethod
    def _long_short_net(
        layer_daily_gross: list[list[float]],
        layer_daily_turnover: list[list[float]],
        num_layers: int,
        cost_rate: float,
        trading_days_per_year: int,
    ) -> float:
        """多空年化净收益: 顶层做多、底层做空, 两腿均按换手扣成本。"""
        top, bot = num_layers - 1, 0
        n = min(len(layer_daily_gross[top]), len(layer_daily_gross[bot]))
        if n == 0:
            return 0.0
        cum = 1.0
        for t in range(n):
            spread_gross = layer_daily_gross[top][t] - layer_daily_gross[bot][t]
            spread_cost = (layer_daily_turnover[top][t] + layer_daily_turnover[bot][t]) * cost_rate
            cum *= 1 + spread_gross - spread_cost
        if cum <= 0:
            return -1.0
        return cum ** (trading_days_per_year / n) - 1

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
