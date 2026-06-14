"""向量化日序列构建 — IC 序列 + 分层日收益/换手/基准序列。

替代对象式 ``ICCalculator``/``LayerBacktester`` 内的逐日 Python 循环, 以 pandas
groupby 一次性产出与对象式逐位等价的中间序列(设计 §6 E5/E7/E8/E9), 再复用
``LayerBacktester`` 的纯归约静态方法(``_top_excess_net`` 等)算最终记分牌。
"""

import bisect

import numpy as np
import pandas as pd

from src.domain.strategy.factor_test.panel import FactorPanel
from src.infrastructure.factor_test.layer_backtest import (
    LayerBacktester,
    LayerBacktestResult,
)


class VectorizedSeriesBuilder:
    """从列式面板 + 因子值 Series 构建 IC / 分层日序列。"""

    def ic_series(
        self, panel: FactorPanel, factor_series: pd.Series
    ) -> list[tuple[str, float]]:
        """逐日 Spearman IC, 键入快照日。与 ``ICCalculator.calculate_ic_series`` 等价。

        factor@snapshot_date 与 returns@next_date(全局下一交易日) 配对; 共同股 <3 → IC 0;
        除末日外每个快照日都产出一项(无配对 → 0)。
        """
        df = panel.df
        dates = sorted(df["date"].unique())
        if len(dates) < 2:
            return []
        next_map = {dates[i]: dates[i + 1] for i in range(len(dates) - 1)}

        fac = pd.DataFrame({
            "date": df["date"].to_numpy(),
            "symbol": df["symbol"].to_numpy(),
            "factor": factor_series.to_numpy(),
        }).dropna(subset=["factor"])
        fac["ret_date"] = fac["date"].map(next_map)

        ret_df = self._returns_long(panel)
        merged = fac.merge(ret_df, on=["ret_date", "symbol"], how="inner")

        ic_by_date: dict[pd.Timestamp, float] = {}
        for sdate, g in merged.groupby("date", sort=True):
            ic_by_date[sdate] = self._spearman(g["factor"], g["ret"])

        return [
            (d.strftime("%Y-%m-%d"), float(ic_by_date.get(d, 0.0)))
            for d in dates[:-1]
        ]

    def layer_series(
        self,
        panel: FactorPanel,
        factor_series: pd.Series,
        num_layers: int = 5,
        cost_rate: float = 0.003,
        rebalance_days: int = 1,
    ) -> LayerBacktestResult:
        """分层日序列 + 复用 L3/L4 归约, 与 ``LayerBacktester.run`` 逐位等价。

        因子求值已向量化(传入 factor_series); 成员/换手/调仓状态机仍按对象式逐日推进
        (轻量纯 set 运算, 无对象物化、无逐日 AST walk —— 即原瓶颈), 故结果逐位一致。
        """
        df = panel.df
        dates = [pd.Timestamp(d) for d in sorted(df["date"].unique())]
        returns_by_date = panel.forward_returns()
        ret_keys = sorted(returns_by_date.keys())
        factor_by_date = self._factor_by_date(df, factor_series)

        layer_daily_gross: list[list[float]] = [[] for _ in range(num_layers)]
        layer_daily_turnover: list[list[float]] = [[] for _ in range(num_layers)]
        members: list[set[str]] = [set() for _ in range(num_layers)]
        has_membership = False
        days_held = 0
        bench_daily: list[float] = []
        bench_daily_turnover: list[float] = []
        bench_members: set[str] = set()

        for dt in dates:
            date_str = dt.strftime("%Y-%m-%d")
            j = bisect.bisect_right(ret_keys, date_str)
            next_date = ret_keys[j] if j < len(ret_keys) else None
            if next_date is None:
                continue
            next_returns = returns_by_date.get(next_date, {})
            day_turnover = [0.0] * num_layers
            day_bench_turnover = 0.0

            if not has_membership or days_held >= rebalance_days:
                factor_values = factor_by_date.get(dt, {})
                common = sorted(set(factor_values) & set(next_returns))
                if len(common) >= num_layers:
                    items = [(s, factor_values[s]) for s in common]
                    items.sort(key=lambda x: x[1])
                    group_size = len(items) // num_layers
                    for layer_idx in range(num_layers):
                        start = layer_idx * group_size
                        end = start + group_size if layer_idx < num_layers - 1 else len(items)
                        new_members = {sym for sym, _ in items[start:end]}
                        if members[layer_idx]:
                            day_turnover[layer_idx] = (
                                len(new_members - members[layer_idx]) / len(new_members)
                            )
                        else:
                            day_turnover[layer_idx] = 1.0
                        members[layer_idx] = new_members
                    new_bench = set(common)
                    if bench_members and new_bench:
                        day_bench_turnover = len(new_bench - bench_members) / len(new_bench)
                    elif new_bench:
                        day_bench_turnover = 1.0
                    bench_members = new_bench
                    has_membership = True
                    days_held = 0
                elif not has_membership:
                    continue

            for layer_idx in range(num_layers):
                rets = [next_returns[s] for s in members[layer_idx] if s in next_returns]
                avg_ret = sum(rets) / len(rets) if rets else 0.0
                layer_daily_gross[layer_idx].append(avg_ret)
                layer_daily_turnover[layer_idx].append(day_turnover[layer_idx])
            b_rets = [next_returns[s] for s in bench_members if s in next_returns]
            bench_daily.append(sum(b_rets) / len(b_rets) if b_rets else 0.0)
            bench_daily_turnover.append(day_bench_turnover)
            days_held += 1

        # 归约: 各层累计/年化 (与 LayerBacktester.run 同算术形) + 复用静态归约方法
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

        long_short = LayerBacktester._long_short_net(
            layer_daily_gross, layer_daily_turnover, num_layers,
            cost_rate, trading_days_per_year,
        )
        mono = LayerBacktester._monotonicity_score(layer_annual_returns)
        top_layer_ret, bench_ret, top_excess, excess_ir, excess_pos = (
            LayerBacktester._top_excess_net(
                layer_daily_gross, layer_daily_turnover, bench_daily, bench_daily_turnover,
                num_layers, cost_rate, trading_days_per_year, layer_annual_returns,
                rebalance_days,
            )
        )

        result = LayerBacktestResult(
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
        return result

    @staticmethod
    def _factor_by_date(
        df: pd.DataFrame, factor_series: pd.Series
    ) -> dict[pd.Timestamp, dict[str, float]]:
        """{Timestamp: {symbol: factor_value}}，丢弃 NaN。"""
        fac = pd.DataFrame({
            "date": df["date"].to_numpy(),
            "symbol": df["symbol"].to_numpy(),
            "factor": factor_series.to_numpy(),
        }).dropna(subset=["factor"])
        return {
            pd.Timestamp(d): dict(zip(g["symbol"], g["factor"].astype(float), strict=True))
            for d, g in fac.groupby("date", sort=False)
        }

    @staticmethod
    def _returns_long(panel: FactorPanel) -> pd.DataFrame:
        """前向收益 dict → 长表 [ret_date(实现日), symbol, ret]。"""
        returns = panel.forward_returns()
        rows = [
            (pd.Timestamp(rdate), sym, r)
            for rdate, day in returns.items()
            for sym, r in day.items()
        ]
        return pd.DataFrame(rows, columns=["ret_date", "symbol", "ret"])

    @staticmethod
    def _spearman(x: pd.Series, y: pd.Series) -> float:
        """Spearman 秩相关(平均并列秩, 共同股 <3 → 0)。复刻对象式 _spearman_rank_correlation。"""
        n = len(x)
        if n < 3:
            return 0.0
        xr = x.rank(method="average").to_numpy()
        yr = y.rank(method="average").to_numpy()
        xm, ym = xr.mean(), yr.mean()
        cov = float(((xr - xm) * (yr - ym)).sum())
        xs = float(np.sqrt(((xr - xm) ** 2).sum()))
        ys = float(np.sqrt(((yr - ym) ** 2).sum()))
        if xs == 0 or ys == 0:
            return 0.0
        return cov / (xs * ys)
