"""FactorPanel golden 等价测试 — 前向收益(E6 全局 next_date) + IS/OOS 切分。"""

import pandas as pd

from src.application.factor_test_app import _compute_forward_returns
from src.domain.strategy.factor_test.panel import FactorPanel

# date -> {symbol: exec_close}; C 在 d2 缺失(测全局 next_date 的"两端都需在场");
# D 在 d1 价=0(测 p_prev>0 过滤); A 在 d5 价=0(p_cur=0 仍计, ret=-1, 测口径一致)
_PRICES = {
    "2024-01-02": {"A": 10.0, "B": 20.0, "C": 30.0, "D": 0.0},
    "2024-01-03": {"A": 11.0, "B": 22.0, "D": 5.0},
    "2024-01-04": {"A": 12.0, "B": 21.0, "C": 33.0, "D": 5.5},
    "2024-01-05": {"A": 0.0, "B": 23.0, "C": 30.0, "D": 6.0},
}


def _panel() -> FactorPanel:
    recs = []
    for date, px in _PRICES.items():
        for sym, p in px.items():
            recs.append({"date": pd.Timestamp(date), "symbol": sym, "exec_close": p})
    return FactorPanel(pd.DataFrame(recs))


def test_forward_returns_matches_object():
    panel = _panel()
    got = panel.forward_returns()
    expected = _compute_forward_returns(_PRICES)

    assert set(got) == set(expected), "实现日键集不一致"
    for date in expected:
        assert set(got[date]) == set(expected[date]), f"{date}: 股票集不一致"
        for sym, ret in expected[date].items():
            assert got[date][sym] == ret


def test_slice_is_oos():
    panel = _panel()
    split = "2024-01-03"
    is_dates = {d.strftime("%Y-%m-%d") for d in panel.slice_is(split).df["date"].unique()}
    oos_dates = {d.strftime("%Y-%m-%d") for d in panel.slice_oos(split).df["date"].unique()}
    assert is_dates == {"2024-01-02", "2024-01-03"}
    assert oos_dates == {"2024-01-04", "2024-01-05"}
