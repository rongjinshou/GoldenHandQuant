"""VectorizedNeutralizer golden 等价测试 — 对照对象式 FactorNeutralizer。"""

from datetime import datetime

import pandas as pd
import pytest

from src.application.factor_test_app import _compute_forward_returns
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.neutralizer import FactorNeutralizer
from src.domain.strategy.factor_test.panel import FactorPanel
from src.domain.strategy.factor_test.vectorized_neutralizer import VectorizedNeutralizer

# date -> [(symbol, pe, market_cap, return_20d, exec_close), ...]
_DATA: dict[str, list] = {
    "2024-01-02": [("A", 10.0, 1e9, 0.05, 10.0), ("B", 20.0, 5e9, -0.03, 20.0),
                   ("C", 15.0, 2e10, 0.01, 30.0), ("D", 30.0, 8e9, 0.02, 40.0),
                   ("E", 25.0, 3e10, -0.10, 50.0), ("F", 12.0, 6e9, 0.07, 15.0)],
    "2024-01-03": [("A", 11.0, 1.1e9, 0.06, 11.0), ("B", 19.0, 5.1e9, -0.02, 22.0),
                   ("C", 16.0, 2.1e10, 0.02, 31.0), ("D", 31.0, 8.1e9, 0.03, 38.0),
                   ("E", 26.0, 3.1e10, -0.09, 52.0), ("F", 13.0, 6.1e9, 0.08, 16.0)],
    "2024-01-04": [("A", 12.0, 1.2e9, 0.07, 12.0), ("B", 18.0, 5.2e9, -0.01, 21.0),
                   ("C", 17.0, 2.2e10, 0.03, 33.0), ("D", 32.0, 8.2e9, 0.04, 39.0),
                   ("E", 27.0, 3.2e10, -0.08, 49.0), ("F", 14.0, 6.2e9, 0.09, 17.0)],
    "2024-01-05": [("A", 13.0, 1.3e9, 0.08, 13.0), ("B", 17.0, 5.3e9, 0.00, 23.0)],  # <3 → skip
    "2024-01-08": [("A", 14.0, 1.4e9, 0.09, 14.0), ("B", 16.0, 5.4e9, 0.01, 24.0),
                   ("C", 18.0, 2.3e10, 0.04, 36.0), ("D", 33.0, 8.3e9, 0.05, 43.0),
                   ("E", 28.0, 3.3e10, -0.07, 47.0), ("F", 15.0, 6.3e9, 0.10, 19.0)],
}


def _build():
    recs, snaps_by_date, prices_by_date = [], {}, {}
    for date, rows in _DATA.items():
        dt = datetime.fromisoformat(date)
        snaps, px = [], {}
        for sym, pe, mc, r20, close in rows:
            recs.append({"date": pd.Timestamp(date), "symbol": sym, "pe_ratio": pe,
                         "market_cap": mc, "return_20d": r20, "exec_close": close})
            snaps.append(StockSnapshot(
                symbol=sym, date=dt, open=10, high=10, low=10, close=close, volume=1000,
                name=sym, list_date=datetime(2020, 1, 1),
                market_cap=mc, pe_ratio=pe, return_20d=r20))
            px[sym] = close
        snaps_by_date[date] = snaps
        prices_by_date[date] = px
    panel = FactorPanel(pd.DataFrame(recs))
    return panel, snaps_by_date, _compute_forward_returns(prices_by_date)


@pytest.mark.parametrize("expr_str", [
    "pe_ratio",                 # 一般因子
    "rank(pe_ratio)",
    "0 - log(market_cap)",      # size 克隆 → 残差退化 → 中性化 IC 0
])
def test_neutralized_ic_matches_object(expr_str: str):
    panel, snaps, returns = _build()
    obj = FactorNeutralizer().mean_neutralized_ic(expr_str, snaps, returns)
    vec = VectorizedNeutralizer().mean_neutralized_ic(expr_str, panel)
    assert vec == pytest.approx(obj, abs=1e-12), expr_str
