"""向量化日序列构建 — IC 序列 + 分层日收益/换手/基准序列。

替代对象式 ``ICCalculator``/``LayerBacktester`` 内的逐日 Python 循环, 以 pandas
groupby 一次性产出与对象式逐位等价的中间序列(设计 §6 E5/E7/E8/E9), 再复用
``LayerBacktester`` 的纯归约静态方法(``_top_excess_net`` 等)算最终记分牌。
"""

import numpy as np
import pandas as pd

from src.domain.strategy.factor_test.panel import FactorPanel


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
