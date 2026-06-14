"""FactorPanel — 列式全市场面板。

替代对象式 ``load_cross_sections`` 物化 580 万 StockSnapshot 的路径: 持一张列式
DataFrame(date/symbol/特征/价格), 前向收益与 IS/OOS 切分均在列上向量化完成。
前向收益严格复刻对象式 ``_compute_forward_returns`` 的全局 next_date 语义(设计 §6 E6)。
"""

from __future__ import annotations

import pandas as pd


class FactorPanel:
    """列式面板。df 须含 ``date``(Timestamp)、``symbol`` 及价格列(默认 exec_close)。"""

    def __init__(self, df: pd.DataFrame, price_col: str = "exec_close") -> None:
        self._df = df
        self._price_col = price_col

    @property
    def df(self) -> pd.DataFrame:
        return self._df

    @property
    def price_col(self) -> str:
        return self._price_col

    def forward_returns(self) -> dict[str, dict[str, float]]:
        """前向收益, 按【实现日】键入: returns[cur][sym] = price[cur]/price[prev] − 1。

        全局 next_date: prev/cur 为相邻全局交易日, 该股两日都需在场且 price[prev]>0。
        与 ``_compute_forward_returns`` 逐位等价(含为每个实现日保留键, 即便当日无收益)。
        """
        df = self._df[["date", "symbol", self._price_col]]
        dates = sorted(df["date"].unique())
        if len(dates) < 2:
            return {}
        date_idx = {dt: i for i, dt in enumerate(dates)}

        d = df.assign(di=df["date"].map(date_idx)).sort_values(["symbol", "di"])
        d["p_prev"] = d.groupby("symbol", sort=False)[self._price_col].shift(1)
        d["di_prev"] = d.groupby("symbol", sort=False)["di"].shift(1)
        # 仅相邻全局日(di == di_prev+1) 且 prev>0
        valid = d[(d["di"] == d["di_prev"] + 1) & (d["p_prev"] > 0)].copy()
        # 与对象式同一算术形 (p_cur - p_prev)/p_prev, 保证浮点逐位一致
        valid["ret"] = (valid[self._price_col] - valid["p_prev"]) / valid["p_prev"]

        # 为每个实现日(dates[1:]) 预置空 dict, 再填充(保留无收益日的键)
        returns: dict[str, dict[str, float]] = {
            dt.strftime("%Y-%m-%d"): {} for dt in dates[1:]
        }
        for cur_date, grp in valid.groupby("date", sort=True):
            returns[cur_date.strftime("%Y-%m-%d")] = dict(
                zip(grp["symbol"], grp["ret"].astype(float), strict=True)
            )
        return returns

    def slice_is(self, split_date: str) -> FactorPanel:
        """样本内: date <= split_date。"""
        sub = self._df[self._df["date"] <= pd.Timestamp(split_date)]
        return FactorPanel(sub, self._price_col)

    def slice_oos(self, split_date: str) -> FactorPanel:
        """样本外: date > split_date。"""
        sub = self._df[self._df["date"] > pd.Timestamp(split_date)]
        return FactorPanel(sub, self._price_col)
