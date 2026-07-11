"""VectorizedRunner golden 等价测试 — 对照对象式 FactorTestRunner 全报告+评分。"""

from datetime import datetime

import pandas as pd
import pytest

from src.application.factor_test_app import _compute_forward_returns
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.panel import FactorPanel
from src.infrastructure.factor_test.test_runner import FactorTestRunner
from src.infrastructure.factor_test.vectorized_runner import VectorizedRunner

# date -> [(symbol, pe_ratio, pb_ratio, roe_ttm, exec_close), ...]
_DATA: dict[str, list] = {
    "2024-01-02": [("A", 10.0, 2.0, 0.15, 10.0), ("B", 10.0, 1.0, 0.15, 20.0),
                   ("C", 20.0, 4.0, 0.20, 30.0), ("D", 30.0, 0.5, 0.10, 40.0),
                   ("E", 40.0, 3.0, 0.05, 50.0), ("F", 25.0, 2.5, 0.12, 15.0)],
    "2024-01-03": [("A", 11.0, 2.1, 0.16, 11.0), ("B", 12.0, 1.1, 0.14, 22.0),
                   ("C", 19.0, 4.1, 0.21, 31.0), ("D", 31.0, 0.6, 0.11, 38.0),
                   ("E", 41.0, 3.1, 0.06, 52.0), ("F", 26.0, 2.6, 0.13, 16.0)],
    "2024-01-04": [("A", 12.0, 2.2, 0.17, 12.0), ("B", 13.0, 1.2, 0.13, 21.0),
                   ("C", 18.0, 4.2, 0.22, 33.0), ("D", 32.0, 0.7, 0.12, 39.0),
                   ("E", 42.0, 3.2, 0.07, 49.0), ("F", 27.0, 2.7, 0.14, 17.0)],
    "2024-01-05": [("A", 13.0, 2.3, 0.18, 13.0), ("B", 14.0, 1.3, 0.12, 23.0),
                   ("C", 17.0, 4.3, 0.23, 34.0), ("D", 33.0, 0.8, 0.13, 41.0),
                   ("E", 43.0, 3.3, 0.08, 48.0), ("F", 28.0, 2.8, 0.15, 18.0)],
    "2024-01-08": [("A", 14.0, 2.4, 0.19, 14.0), ("B", 15.0, 1.4, 0.11, 24.0),
                   ("C", 16.0, 4.4, 0.24, 36.0), ("D", 34.0, 0.9, 0.14, 43.0),
                   ("E", 44.0, 3.4, 0.09, 47.0), ("F", 29.0, 2.9, 0.16, 19.0)],
}


def _build():
    recs, snaps_by_date, prices_by_date = [], {}, {}
    for date, rows in _DATA.items():
        dt = datetime.fromisoformat(date)
        snaps, px = [], {}
        for sym, pe, pb, roe, close in rows:
            recs.append({"date": pd.Timestamp(date), "symbol": sym,
                         "pe_ratio": pe, "pb_ratio": pb, "roe_ttm": roe, "exec_close": close})
            snaps.append(StockSnapshot(
                symbol=sym, date=dt, open=10, high=10, low=10, close=close, volume=1000,
                name=sym, list_date=datetime(2020, 1, 1),
                market_cap=1e10, pe_ratio=pe, pb_ratio=pb, roe_ttm=roe))
            px[sym] = close
        snaps_by_date[date] = snaps
        prices_by_date[date] = px
    panel = FactorPanel(pd.DataFrame(recs))
    return panel, snaps_by_date, _compute_forward_returns(prices_by_date), prices_by_date


_SCALAR_FIELDS = [
    "expression", "test_period", "universe_count", "ic_mean", "ic_std", "ir",
    "ic_positive_rate", "layer_count", "rebalance_days", "long_short_return",
    "top_layer_return", "benchmark_return", "top_excess_return", "excess_ir",
    "excess_positive_rate", "monotonicity_score",
]


@pytest.mark.parametrize("objective", ["long_short", "long_only"])
@pytest.mark.parametrize("expr_str", ["0 - pe_ratio", "rank(1 / pb_ratio) * rank(roe_ttm)"])
def test_runner_matches_object(expr_str: str, objective: str):
    panel, snaps, returns, prices = _build()

    obj = FactorTestRunner().run(
        expr_str, snaps, returns, prices, test_period=("2024-01-02", "2024-01-08"),
        num_layers=3, rebalance_days=1, objective=objective, cost_rate=0.003,
    )
    vec = VectorizedRunner().run(
        expr_str, panel, test_period=("2024-01-02", "2024-01-08"),
        num_layers=3, rebalance_days=1, objective=objective, cost_rate=0.003,
    )

    ctx = f"{expr_str}|{objective}"
    assert vec.score == pytest.approx(obj.score, abs=1e-9), f"{ctx}.score"
    assert vec.grade == obj.grade, f"{ctx}.grade"
    assert vec.grade_reasons == obj.grade_reasons, f"{ctx}.reasons"

    for f in _SCALAR_FIELDS:
        ov, vv = getattr(obj.report, f), getattr(vec.report, f)
        if isinstance(ov, float):
            assert vv == pytest.approx(ov, abs=1e-12), f"{ctx}.{f}"
        else:
            assert vv == ov, f"{ctx}.{f}"

    # IC 序列 + 衰减 + 分层年化 + 累计
    assert [d for d, _ in vec.report.ic_series] == [d for d, _ in obj.report.ic_series]
    for (_, a), (_, b) in zip(obj.report.ic_series, vec.report.ic_series, strict=True):
        assert b == pytest.approx(a, abs=1e-12), f"{ctx}.ic_series"
    assert vec.report.decay_periods == obj.report.decay_periods
    for a, b in zip(obj.report.decay_ics, vec.report.decay_ics, strict=True):
        assert b == pytest.approx(a, abs=1e-12), f"{ctx}.decay_ics"
    for a, b in zip(obj.report.layer_returns, vec.report.layer_returns, strict=True):
        assert b == pytest.approx(a, abs=1e-12), f"{ctx}.layer_returns"
