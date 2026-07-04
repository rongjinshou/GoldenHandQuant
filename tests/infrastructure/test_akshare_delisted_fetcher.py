"""akshare 退市回填的纯计算函数(TTM/as-of/市值/归一) — 无网络, 进 golden。

放 tests/infrastructure/ 根(非 gateway/ 子目录): gateway/ 因 xtquant 被 golden ignore,
而本组纯函数零 akshare 依赖(延迟 import 设计), 必须纳入回归。
"""

from datetime import datetime

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.infrastructure.gateway.akshare_delisted_fetcher import (
    asof_report,
    build_ttm_fundamentals,
    df_to_bars,
    ttm_value,
)


def _d(y, m, d):
    return datetime(y, m, d)


class TestTtmValue:
    def test_annual_report_is_ttm_directly(self):
        cum = {_d(2022, 12, 31): 400.0}
        assert ttm_value(_d(2022, 12, 31), cum) == 400.0

    def test_quarterly_rolls_with_prev_fy_and_prev_same(self):
        # Q3 TTM = Q3累计 + 上年FY − 上年Q3累计 = 300 + 400 − 280 = 420
        cum = {_d(2023, 9, 30): 300.0, _d(2022, 12, 31): 400.0, _d(2022, 9, 30): 280.0}
        assert ttm_value(_d(2023, 9, 30), cum) == 420.0

    def test_missing_prev_same_falls_back_to_latest_fy(self):
        cum = {_d(2023, 9, 30): 300.0, _d(2022, 12, 31): 400.0}  # 缺上年 Q3
        assert ttm_value(_d(2023, 9, 30), cum) == 400.0  # 退化最近年报

    def test_no_fy_at_all_returns_none(self):
        cum = {_d(2023, 9, 30): 300.0}
        assert ttm_value(_d(2023, 9, 30), cum) is None

    def test_report_date_absent_returns_none(self):
        assert ttm_value(_d(2023, 9, 30), {}) is None


class TestAsofReport:
    def test_lag_boundary_exactly_90_days_effective(self):
        reports = [_d(2023, 3, 31)]
        assert asof_report(_d(2023, 6, 29), reports) == _d(2023, 3, 31)  # 3-31+90d=6-29
        assert asof_report(_d(2023, 6, 28), reports) is None

    def test_picks_latest_effective(self):
        reports = [_d(2022, 12, 31), _d(2023, 3, 31), _d(2023, 6, 30)]
        assert asof_report(_d(2023, 7, 15), reports) == _d(2023, 3, 31)  # 6-30 未满 90d


def _bars(symbol, days: list[datetime], price=10.0):
    return [Bar(symbol=symbol, timeframe=Timeframe.DAY_1, timestamp=d,
                open=price, high=price, low=price, close=price, volume=1000.0)
            for d in days]


class TestBuildTtmFundamentals:
    def _kw(self, **over):
        days = [_d(2023, 7, 3), _d(2023, 7, 4)]
        kw = dict(
            symbol="600068.SH", name="退市样例", list_date=_d(2000, 1, 1),
            bars=_bars("600068.SH", days),
            raw_close_by_date={_d(2023, 7, 3): 2.0, _d(2023, 7, 4): 1.8},
            profit_cum={_d(2022, 12, 31): 100.0},
            cashflow_cum={_d(2022, 12, 31): 50.0},
            equity_by_report={_d(2022, 12, 31): 1000.0},
            share_by_report={_d(2022, 12, 31): 3e8},
        )
        kw.update(over)
        return kw

    def test_one_row_per_bar_day_with_raw_close_mcap(self):
        snaps = build_ttm_fundamentals(**self._kw())
        assert [s.date for s in snaps] == [_d(2023, 7, 3), _d(2023, 7, 4)]
        assert snaps[0].market_cap == 2.0 * 3e8      # 不复权价 × 股本
        assert snaps[0].roe_ttm == 100.0 / 1000.0
        assert snaps[0].ocf_ttm == 50.0

    def test_missing_share_returns_empty(self):
        assert build_ttm_fundamentals(**self._kw(share_by_report={})) == []

    def test_missing_raw_close_falls_back_to_qfq(self):
        snaps = build_ttm_fundamentals(**self._kw(raw_close_by_date={}))
        assert snaps[0].market_cap == 10.0 * 3e8     # bar.close(qfq) 降级

    def test_bar_before_share_effective_skipped(self):
        kw = self._kw(share_by_report={_d(2023, 6, 30): 3e8})  # +90d → 9-28 生效
        assert build_ttm_fundamentals(**kw) == []

    def test_missing_profit_yields_none_roe_row_kept(self):
        snaps = build_ttm_fundamentals(**self._kw(profit_cum={}))
        assert snaps and snaps[0].roe_ttm is None    # 行保留, 交给 quality 闸剔


class TestDfToBars:
    def test_prev_close_chain_and_unadjusted(self):
        rows = [
            {"date": "2023-07-03", "open": 1, "high": 1, "low": 1, "close": 10.0, "volume": 5},
            {"date": "2023-07-04", "open": 1, "high": 1, "low": 1, "close": 11.0, "volume": 6},
        ]
        bars = df_to_bars("600068.SH", rows, {_d(2023, 7, 4): 1.9})
        assert bars[0].prev_close == 0.0 and bars[1].prev_close == 10.0
        assert bars[0].unadjusted_close == 0.0 and bars[1].unadjusted_close == 1.9
        assert bars[1].timestamp == _d(2023, 7, 4)
