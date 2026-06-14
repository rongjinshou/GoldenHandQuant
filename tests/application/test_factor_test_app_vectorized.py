"""判决级 golden 等价 — 对象式 run_batch vs 列式 run_batch_panel(IS/OOS + 中性化)。

20 股 × 40 交易日合成面板, 因子混控制类(F01 规模→不中性化)与非控制类(F20/F22→中性化),
两 objective + 样本内外切分。两路判决须逐字段一致(组件级 40 个 golden 已证, 此处证编排)。
"""

from datetime import datetime

import pandas as pd
import pytest

from src.application.factor_test_app import FactorTestAppService, _compute_forward_returns
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.factor_catalog import resolve_factors
from src.domain.strategy.factor_test.panel import FactorPanel

_N = 20
_DATES = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2024-01-01", periods=40)]


def _fields(i: int, t: int) -> dict:
    return {
        "market_cap": 1e9 * (i + 1) * (1 + 0.01 * t),
        "pe_ratio": 5.0 + i * 1.5 + 0.1 * t,
        "earnings_growth": -0.10 + 0.02 * i + 0.001 * t,
        "volatility_20d": 0.10 + 0.005 * i + 0.0001 * t,
        "roe_ttm": 0.02 + 0.008 * i,
        "return_20d": -0.05 + 0.004 * i + 0.0002 * t,
        "exec_close": 10.0 + i + 0.5 * t + ((i * 3 + t * 5) % 7) * 0.3,
    }


def _build():
    recs, snaps_by_date, prices_by_date = [], {}, {}
    for t, date_str in enumerate(_DATES):
        dt = datetime.fromisoformat(date_str)
        snaps, px = [], {}
        for i in range(_N):
            f = _fields(i, t)
            sym = f"S{i:02d}"
            recs.append({"date": pd.Timestamp(date_str), "symbol": sym, **f})
            snaps.append(StockSnapshot(
                symbol=sym, date=dt, open=10, high=10, low=10,
                close=f["exec_close"], volume=1000, name=sym,
                list_date=datetime(2020, 1, 1),
                market_cap=f["market_cap"], pe_ratio=f["pe_ratio"],
                earnings_growth=f["earnings_growth"], volatility_20d=f["volatility_20d"],
                roe_ttm=f["roe_ttm"], return_20d=f["return_20d"]))
            px[sym] = f["exec_close"]
        snaps_by_date[date_str] = snaps
        prices_by_date[date_str] = px
    panel = FactorPanel(pd.DataFrame(recs))
    return panel, snaps_by_date, _compute_forward_returns(prices_by_date), prices_by_date


_VERDICT_FLOATS = [
    "ic_mean", "ir", "ic_positive_rate", "monotonicity_score", "long_short_return",
    "score", "top_excess_return", "excess_ir", "excess_positive_rate",
]
_OOS_FLOATS = ["oos_ic_mean", "oos_ir", "oos_long_short_return", "oos_top_excess_return"]


@pytest.mark.parametrize("objective", ["long_short", "long_only"])
def test_run_batch_panel_matches_object(objective: str):
    panel, snaps, returns, prices = _build()
    hyps = resolve_factors("F01,F20,F22")
    split = _DATES[24]
    kw = dict(test_period=(_DATES[0], _DATES[-1]), split_date=split,
              num_layers=5, rebalance_days=1, objective=objective, cost_rate=0.003)

    svc = FactorTestAppService(history_fetcher=None, fundamental_fetcher=None)
    obj = svc.run_batch(hyps, snaps, returns, prices, **kw)
    vec = svc.run_batch_panel(hyps, panel, **kw)

    assert [r.verdict.factor_id for r in vec] == [r.verdict.factor_id for r in obj]
    for ro, rv in zip(obj, vec, strict=True):
        vo, vv = ro.verdict, rv.verdict
        ctx = f"{vo.factor_id}|{objective}"
        assert vv.passed == vo.passed, f"{ctx}.passed"
        assert vv.grade == vo.grade, f"{ctx}.grade"
        assert vv.reasons == vo.reasons, f"{ctx}.reasons"
        for f in _VERDICT_FLOATS:
            assert getattr(vv, f) == pytest.approx(getattr(vo, f), abs=1e-9), f"{ctx}.{f}"
        for f in _OOS_FLOATS:
            a, b = getattr(vo, f), getattr(vv, f)
            if a is None:
                assert b is None, f"{ctx}.{f}"
            else:
                assert b == pytest.approx(a, abs=1e-9), f"{ctx}.{f}"
