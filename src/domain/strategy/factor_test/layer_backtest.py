"""分层回测引擎：按因子值将股票分组，计算各组收益。"""

import math
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
    # --- long-only 记分牌 (默认 0.0, 向后兼容) ---
    top_layer_return: float = 0.0       # Top 层年化净收益(长仓口径, 已扣换手成本)
    benchmark_return: float = 0.0       # 等权覆盖池年化(L4: 已对称扣换手成本)
    top_excess_return: float = 0.0      # Top 层年化超额(两腿对称扣换手成本)
    excess_ir: float = 0.0              # 年化超额信息比(L3: 非重叠块 IR, 块=持有期)
    excess_positive_rate: float = 0.0   # Top 日超额>0 占比


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
        # 等权覆盖池基准腿: 成员=每次调仓的 common 全集, 与各层并行累积
        bench_daily: list[float] = []
        bench_daily_turnover: list[float] = []   # L4: 基准腿换手(对称扣成本)
        bench_members: set[str] = set()

        for date_str in sorted(snapshots_by_date.keys()):
            next_date = self._next_date(date_str, returns_by_date)
            if next_date is None:
                continue

            next_returns = returns_by_date.get(next_date, {})
            day_turnover = [0.0] * num_layers
            day_bench_turnover = 0.0   # L4: 当日基准换手(仅调仓日非零)

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
                    # L4: 基准腿(覆盖池)换手 = 新进成员占比, 与各层同口径
                    new_bench = set(common)
                    if bench_members and new_bench:
                        day_bench_turnover = len(new_bench - bench_members) / len(new_bench)
                    elif new_bench:
                        day_bench_turnover = 1.0
                    bench_members = new_bench
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
            # 基准腿: 持有 bench_members 等权累积; L4 换手成本在 _top_excess_net 对称扣
            b_rets = [next_returns[s] for s in bench_members if s in next_returns]
            bench_daily.append(sum(b_rets) / len(b_rets) if b_rets else 0.0)
            bench_daily_turnover.append(day_bench_turnover)
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

        # long-only: Top 层纯多头超额 vs 等权覆盖池基准 (L3 块IR / L4 基准对称成本)
        top_layer_ret, bench_ret, top_excess, excess_ir, excess_pos = self._top_excess_net(
            layer_daily_gross, layer_daily_turnover, bench_daily, bench_daily_turnover,
            num_layers, cost_rate, trading_days_per_year, layer_annual_returns, rebalance_days,
        )

        return LayerBacktestResult(
            layer_count=num_layers,
            layer_returns=layer_annual_returns,
            long_short_return=long_short,
            layer_cumulative=layer_cumulative,
            monotonicity_score=mono,
            top_layer_return=top_layer_ret,
            benchmark_return=bench_ret,
            top_excess_return=top_excess,
            excess_ir=excess_ir,
            excess_positive_rate=excess_pos,
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

    @staticmethod
    def _top_excess_net(
        layer_daily_gross: list[list[float]],
        layer_daily_turnover: list[list[float]],
        bench_daily: list[float],
        bench_daily_turnover: list[float],
        num_layers: int,
        cost_rate: float,
        trading_days_per_year: int,
        layer_annual_returns: list[float],
        rebalance_days: int = 1,
    ) -> tuple[float, float, float, float, float]:
        """Top 层纯多头超额 vs 等权覆盖池基准。

        L4: 基准腿对称扣换手成本(不再 costless)，消除"Top 扣成本/基准免成本"的不对称。
        L3: excess_ir 用非重叠块 IR(块=持有期 rebalance_days, 块内复利、跨块近似独立,
            年化用 √每年块数), 消除持有期内日超额自相关对 √244 年化的高估;
            rebalance_days=1 时退化为日 IR(无回归)。

        Returns:
            (top_layer_return, benchmark_return, top_excess_return,
             excess_ir, excess_positive_rate)
        """
        top = num_layers - 1
        n = min(len(layer_daily_gross[top]), len(bench_daily))
        if n == 0:
            return 0.0, 0.0, 0.0, 0.0, 0.0

        # Top 日净超额: (顶层毛收益-顶层换手成本) - (基准毛收益-基准换手成本)  ← L4 对称
        excess_series: list[float] = []
        cum_bench = 1.0
        cum_excess = 1.0
        for t in range(n):
            top_net = layer_daily_gross[top][t] - layer_daily_turnover[top][t] * cost_rate
            bench_net = bench_daily[t] - bench_daily_turnover[t] * cost_rate
            e = top_net - bench_net
            excess_series.append(e)
            cum_bench *= 1 + bench_net
            cum_excess *= 1 + e

        top_excess = (cum_excess ** (trading_days_per_year / n) - 1) if cum_excess > 0 else -1.0
        bench_ret = (cum_bench ** (trading_days_per_year / n) - 1) if cum_bench > 0 else -1.0
        top_layer_ret = layer_annual_returns[top]

        # L3: 非重叠块 IR — 日超额按持有期聚合成块, 跨块求 IR, 年化用每年块数 √
        rd = max(1, rebalance_days)
        blocks: list[float] = []
        for i in range(0, n, rd):
            cum_blk = 1.0
            for e in excess_series[i:i + rd]:
                cum_blk *= 1 + e
            blocks.append(cum_blk - 1.0)
        m = len(blocks)
        if m > 1:
            mean_b = sum(blocks) / m
            std_b = math.sqrt(sum((x - mean_b) ** 2 for x in blocks) / (m - 1))
            periods_per_year = trading_days_per_year / rd
            excess_ir = (mean_b / std_b * math.sqrt(periods_per_year)) if std_b > 0 else 0.0
        else:
            excess_ir = 0.0
        excess_pos = sum(1 for x in excess_series if x > 0) / n
        return top_layer_ret, bench_ret, top_excess, excess_ir, excess_pos

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
