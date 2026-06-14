"""VectorizedSeriesBuilder golden 等价测试 — IC 序列 + 分层日序列(对照对象式)。"""

from datetime import datetime

import pandas as pd
import pytest

from src.application.factor_test_app import _compute_forward_returns
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.lexer import tokenize
from src.domain.strategy.factor_test.panel import FactorPanel
from src.domain.strategy.factor_test.parser import FactorExpressionParser
from src.domain.strategy.factor_test.vectorized_evaluator import VectorizedEvaluator
from src.infrastructure.factor_test.ic_calculator import ICCalculator
from src.infrastructure.factor_test.layer_backtest import LayerBacktester
from src.infrastructure.factor_test.vectorized_series import VectorizedSeriesBuilder


def _parse(expr_str: str):
    return FactorExpressionParser().parse(tokenize(expr_str))


# date -> [(symbol, pe_ratio, pb_ratio, roe_ttm, exec_close), ...]
# 含: 并列(spearman 平均秩)、缺失股、某日<3 有效(IC=0)
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
    "2024-01-05": [("A", 13.0, 2.3, 0.18, 13.0), ("B", 14.0, 1.3, 0.12, 23.0)],  # <3 → IC 0
    "2024-01-08": [("A", 14.0, 2.4, 0.19, 14.0), ("B", 15.0, 1.4, 0.11, 24.0),
                   ("C", 17.0, 4.3, 0.23, 34.0), ("D", 33.0, 0.8, 0.13, 41.0),
                   ("E", 43.0, 3.3, 0.08, 48.0), ("F", 28.0, 2.8, 0.15, 18.0)],
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
    returns_by_date = _compute_forward_returns(prices_by_date)
    return panel, snaps_by_date, returns_by_date


@pytest.mark.parametrize("expr_str", ["pe_ratio", "rank(pe_ratio)", "rank(1 / pb_ratio) * rank(roe_ttm)"])
def test_ic_series_matches_object(expr_str: str):
    panel, snaps_by_date, returns_by_date = _build()
    expr = _parse(expr_str)

    obj_ic = ICCalculator().calculate_ic_series(expr, snaps_by_date, returns_by_date)
    factor_series = VectorizedEvaluator().evaluate(expr, panel.df)
    vec_ic = VectorizedSeriesBuilder().ic_series(panel, factor_series)

    assert [d for d, _ in vec_ic] == [d for d, _ in obj_ic], f"{expr_str}: 日期序列不一致"
    for (d, v), (_, o) in zip(vec_ic, obj_ic, strict=True):
        assert v == pytest.approx(o, abs=1e-12), f"{expr_str}@{d}"
