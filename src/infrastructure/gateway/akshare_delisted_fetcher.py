"""akshare 退市股静态回填源(B1) — 清单/日线/退市财报 → bars + fundamental_snapshots。

akshare 仅在网络方法内部延迟 import(纯计算函数零依赖, 可进 golden 单测);
东财接口有限流(RemoteDisconnected), 节流/退避由调用方 scripts/backfill_delisted_akshare.py
负责。口径决策(市值=不复权价×股本 fallback 链 / 财报 as-of=报告期+90天 / TTM 滚动)见
docs/feat/0704-b1-delisted-backfill/2026-07-04-b1-delisted-backfill-design.md DD-3/DD-4。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
from src.domain.market.value_objects.timeframe import Timeframe

logger = logging.getLogger(__name__)

REPORT_LAG_DAYS = 90  # 财报生效滞后: 报告期 + 90 天(防用未披露财报选股, DD-4)


# --------------------------------------------------------------------------- #
# 纯计算(单测覆盖, 无网络)
# --------------------------------------------------------------------------- #
def ttm_value(report_date: datetime, cumulative: dict[datetime, float]) -> float | None:
    """A 股财报累计值 → TTM: 最新累计 + 上年年报 − 上年同期累计。

    年报(12-31)累计即 TTM; 缺上年数据时退化为 ≤report_date 的最近年报值(近似, DD-4);
    再缺 → None(交由 filter_quality 诚实剔除)。
    """
    value = cumulative.get(report_date)
    if value is None:
        return None
    if report_date.month == 12:
        return value
    prev_fy = datetime(report_date.year - 1, 12, 31)
    prev_same = datetime(report_date.year - 1, report_date.month, report_date.day)
    if prev_fy in cumulative and prev_same in cumulative:
        return value + cumulative[prev_fy] - cumulative[prev_same]
    fy_dates = [d for d in cumulative if d.month == 12 and d <= report_date]
    return cumulative[max(fy_dates)] if fy_dates else None


def asof_report(
    bar_date: datetime, report_dates: list[datetime], lag_days: int = REPORT_LAG_DAYS,
) -> datetime | None:
    """生效报告期 = max{r : r + lag_days ≤ bar_date}; 无则 None。"""
    lag = timedelta(days=lag_days)
    effective = [r for r in report_dates if r + lag <= bar_date]
    return max(effective) if effective else None


def build_ttm_fundamentals(
    *,
    symbol: str,
    name: str,
    list_date: datetime,
    bars: list[Bar],
    raw_close_by_date: dict[datetime, float],
    profit_cum: dict[datetime, float],
    cashflow_cum: dict[datetime, float],
    equity_by_report: dict[datetime, float],
    share_by_report: dict[datetime, float],
) -> list[FundamentalSnapshot]:
    """按该股 bars 日历产出每日基本面快照(DD-5)。

    market_cap = 不复权收盘 × as-of 股本(缺不复权价时降级 bar.close=qfq, 调用方统计口径);
    股本全程不可得 → 返回 [](市值不可算, 半残行会被 market_cap>0 查询静默过滤, 不如显式缺席)。
    """
    if not share_by_report:
        return []
    share_dates = sorted(share_by_report)
    profit_dates = sorted(profit_cum)
    cf_dates = sorted(cashflow_cum)
    equity_dates = sorted(equity_by_report)

    snaps: list[FundamentalSnapshot] = []
    for bar in bars:
        day = bar.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        share_r = asof_report(day, share_dates)
        if share_r is None:
            continue  # 股本尚未生效(上市极早期), 无法算市值
        close = raw_close_by_date.get(day, bar.close)
        market_cap = close * share_by_report[share_r]

        roe = None
        profit_r = asof_report(day, profit_dates)
        equity_r = asof_report(day, equity_dates)
        if profit_r is not None and equity_r is not None:
            profit_ttm = ttm_value(profit_r, profit_cum)
            equity = equity_by_report.get(equity_r)
            if profit_ttm is not None and equity is not None and equity > 0:
                roe = profit_ttm / equity

        ocf = None
        cf_r = asof_report(day, cf_dates)
        if cf_r is not None:
            ocf = ttm_value(cf_r, cashflow_cum)

        snaps.append(FundamentalSnapshot(
            symbol=symbol, date=day, name=name, list_date=list_date,
            market_cap=market_cap, roe_ttm=roe, ocf_ttm=ocf,
        ))
    return snaps


def df_to_bars(
    symbol: str,
    rows: list[dict],
    raw_close_by_date: dict[datetime, float] | None = None,
) -> list[Bar]:
    """归一化日线行(dict: date/open/high/low/close/volume) → Bar(qfq 口径)。

    prev_close = 序列内前根 close(与 QMT/DuckDB 前复权口径自洽);
    unadjusted_close = 不复权收盘(可得时), 供真实账本结算口径。
    """
    bars: list[Bar] = []
    raw_map = raw_close_by_date or {}
    for row in rows:
        day = row["date"]
        if not isinstance(day, datetime):
            day = datetime.fromisoformat(str(day))
        day = day.replace(hour=0, minute=0, second=0, microsecond=0)
        bars.append(Bar(
            symbol=symbol, timeframe=Timeframe.DAY_1, timestamp=day,
            open=float(row["open"]), high=float(row["high"]),
            low=float(row["low"]), close=float(row["close"]),
            volume=float(row["volume"]),
            unadjusted_close=float(raw_map.get(day, 0.0)),
            prev_close=bars[-1].close if bars else 0.0,
        ))
    return bars


# --------------------------------------------------------------------------- #
# 网络层(akshare 延迟 import; 节流/重试由回填脚本负责)
# --------------------------------------------------------------------------- #
class AkshareDelistedFetcher:
    """退市股清单 / 日线(东财 qfq + 不复权 fallback 链) / 退市财报三表。"""

    def fetch_delist_list(self, since: str = "2021-01-01") -> list[dict]:
        """沪深退市清单并集: [{symbol, name, list_date, delist_date}], delist_date >= since。"""
        import akshare as ak
        import pandas as pd

        out: list[dict] = []
        sh = ak.stock_info_sh_delist()
        for _, row in sh.iterrows():
            delist = pd.to_datetime(row["暂停上市日期"], errors="coerce")
            if pd.isna(delist) or delist < pd.Timestamp(since):
                continue
            out.append({
                "symbol": f"{str(row['公司代码']).zfill(6)}.SH",
                "name": str(row["公司简称"]),
                "list_date": pd.to_datetime(row["上市日期"], errors="coerce"),
                "delist_date": delist,
            })
        sz = ak.stock_info_sz_delist()
        for _, row in sz.iterrows():
            delist = pd.to_datetime(row["终止上市日期"], errors="coerce")
            if pd.isna(delist) or delist < pd.Timestamp(since):
                continue
            out.append({
                "symbol": f"{str(row['证券代码']).zfill(6)}.SZ",
                "name": str(row["证券简称"]),
                "list_date": pd.to_datetime(row["上市日期"], errors="coerce"),
                "delist_date": delist,
            })
        # 去重(两所清单理论不重叠, 防御性)
        seen: set[str] = set()
        return [d for d in out if not (d["symbol"] in seen or seen.add(d["symbol"]))]

    def fetch_daily_qfq(self, symbol: str, start: str = "20200101") -> list[dict]:
        """前复权日线 → 归一行 [{date,open,high,low,close,volume}](升序)。

        腾讯主源(实测退市股全覆盖且不限流), 东财 fallback(限流窗口内 RemoteDisconnected)。
        """
        import akshare as ak

        code, _, market = symbol.partition(".")
        try:
            df = ak.stock_zh_a_hist_tx(symbol=f"{market.lower()}{code}",
                                       start_date=start, end_date="20991231", adjust="qfq")
            if df is not None and not df.empty:
                return [{
                    "date": row["date"], "open": row["open"], "high": row["high"],
                    "low": row["low"], "close": row["close"], "volume": row["amount"],
                } for _, row in df.iterrows()]
        except Exception as e:
            logger.debug("腾讯 qfq 失败 %s: %s", symbol, e)
        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                start_date=start, end_date="20991231", adjust="qfq")
        if df is None or df.empty:
            return []
        return [{
            "date": row["日期"], "open": row["开盘"], "high": row["最高"],
            "low": row["最低"], "close": row["收盘"], "volume": row["成交量"],
        } for _, row in df.iterrows()]

    def fetch_raw_close(self, symbol: str, start: str = "20200101") -> tuple[dict[datetime, float], str]:
        """不复权收盘价 fallback 链(DD-3): 东财 raw → 腾讯 raw → 空(调用方降级 qfq)。

        Returns: ({date: raw_close}, 口径标签 'tx-raw' | 'em-raw' | 'qfq-approx')
        """
        import akshare as ak
        import pandas as pd

        code, _, market = symbol.partition(".")
        try:
            df = ak.stock_zh_a_hist_tx(symbol=f"{market.lower()}{code}",
                                       start_date=start, end_date="20991231", adjust="")
            if df is not None and not df.empty:
                return ({pd.Timestamp(d).to_pydatetime(): float(c)
                         for d, c in zip(df["date"], df["close"], strict=True)}, "tx-raw")
        except Exception as e:
            logger.debug("腾讯 raw 失败 %s: %s", symbol, e)
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                    start_date=start, end_date="20991231", adjust="")
            if df is not None and not df.empty:
                return ({pd.Timestamp(d).to_pydatetime(): float(c)
                         for d, c in zip(df["日期"], df["收盘"], strict=True)}, "em-raw")
        except Exception as e:
            logger.debug("东财 raw 失败 %s: %s", symbol, e)
        return {}, "qfq-approx"

    def fetch_reports(self, symbol: str) -> dict[str, dict[datetime, float]]:
        """退市财报三表关键科目, 均为 {REPORT_DATE: 值}。

        profit_cum=归母净利润(累计) / cashflow_cum=经营现金流净额(累计)
        / equity=归母净资产(期末) / share=股本(期末)。
        """
        import akshare as ak
        import pandas as pd

        code, _, market = symbol.partition(".")
        em_symbol = f"{market}{code}"

        def _col(df, name) -> dict[datetime, float]:
            if df is None or df.empty or name not in df.columns:
                return {}
            out = {}
            for _, row in df.iterrows():
                d = pd.to_datetime(row["REPORT_DATE"], errors="coerce")
                v = row[name]
                if pd.isna(d) or v is None or pd.isna(v):
                    continue
                out[d.to_pydatetime().replace(hour=0, minute=0, second=0, microsecond=0)] = float(v)
            return out

        bs = ak.stock_balance_sheet_by_report_delisted_em(symbol=em_symbol)
        pf = ak.stock_profit_sheet_by_report_delisted_em(symbol=em_symbol)
        cf = ak.stock_cash_flow_sheet_by_report_delisted_em(symbol=em_symbol)
        return {
            "profit_cum": _col(pf, "PARENT_NETPROFIT"),
            "cashflow_cum": _col(cf, "NETCASH_OPERATE"),
            "equity_by_report": _col(bs, "TOTAL_PARENT_EQUITY"),
            "share_by_report": _col(bs, "SHARE_CAPITAL"),
        }
