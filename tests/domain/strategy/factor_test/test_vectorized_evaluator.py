"""VectorizedEvaluator golden 等价测试 — 对照对象式 FactorExpressionEvaluator。

每个表达式: 同一组数据建 DataFrame(列式) 与 list[StockSnapshot](对象式),
断言向量化求值产出的 {symbol: value} 与对象式逐位一致(含缺失/除零/log<=0 的丢弃语义)。
"""

from datetime import datetime

import pandas as pd
import pytest

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.evaluator import FactorExpressionEvaluator
from src.domain.strategy.factor_test.lexer import tokenize
from src.domain.strategy.factor_test.parser import FactorExpressionParser
from src.domain.strategy.factor_test.vectorized_evaluator import VectorizedEvaluator


def _parse(expr_str: str):
    return FactorExpressionParser().parse(tokenize(expr_str))


# symbol, market_cap, pe_ratio, earnings_growth, return_20d, pb_ratio, roe_ttm
_ROWS = [
    ("A", 1.0e10, 10.0, 0.10, 0.05, 2.0, 0.15),
    ("B", 5.0e9, 20.0, 0.20, -0.03, 1.0, 0.08),
    ("C", 2.0e10, 0.0, 0.30, 0.01, 4.0, 0.20),    # pe=0 → 除零丢弃
    ("D", 8.0e9, 15.0, None, 0.02, None, 0.12),   # eg/pb 缺失
    ("E", 3.0e10, -8.0, 0.05, -0.10, 0.5, 0.05),  # pe<0
]

_DATE = "2024-01-02"


def _make_df(rows: list, date: str = _DATE) -> pd.DataFrame:
    recs = []
    for sym, mc, pe, eg, r20, pb, roe in rows:
        recs.append({
            "date": pd.Timestamp(date), "symbol": sym,
            "market_cap": mc, "pe_ratio": pe, "earnings_growth": eg,
            "return_20d": r20, "pb_ratio": pb, "roe_ttm": roe,
        })
    return pd.DataFrame(recs)


def _make_snaps(rows: list, date: str = _DATE) -> list[StockSnapshot]:
    dt = datetime.fromisoformat(date)
    snaps = []
    for sym, mc, pe, eg, r20, pb, roe in rows:
        snaps.append(StockSnapshot(
            symbol=sym, date=dt, open=10, high=10, low=10, close=10, volume=1000,
            name=sym, list_date=datetime(2020, 1, 1),
            market_cap=mc, pe_ratio=pe, earnings_growth=eg, return_20d=r20,
            pb_ratio=pb, roe_ttm=roe,
        ))
    return snaps


_EXPRESSIONS = [
    "pe_ratio",
    "0 - log(market_cap)",
    "earnings_growth / pe_ratio",   # 除零(C) + 缺失(D)
    "abs(return_20d)",
    "sign(return_20d)",
    "log(market_cap)",
    "pe_ratio * 2 + 1",
    "earnings_growth - return_20d",
]


@pytest.mark.parametrize("expr_str", _EXPRESSIONS)
def test_elementwise_matches_object_evaluator(expr_str: str):
    expr = _parse(expr_str)
    obj_out = FactorExpressionEvaluator().evaluate(expr, _make_snaps(_ROWS))

    df = _make_df(_ROWS)
    series = VectorizedEvaluator().evaluate(expr, df)
    vec_out = VectorizedEvaluator.as_dict(series, df)

    assert set(vec_out) == set(obj_out), f"{expr_str}: 股票集不一致"
    for sym in obj_out:
        assert vec_out[sym] == pytest.approx(obj_out[sym], abs=1e-12), f"{expr_str}@{sym}"


def test_missing_column_yields_empty():
    """字段在 DataFrame 中缺列 → 全 NaN → 空 dict(与对象式全跳过一致)。"""
    df = _make_df(_ROWS).drop(columns=["roe_ttm"])
    series = VectorizedEvaluator().evaluate(_parse("roe_ttm"), df)
    assert VectorizedEvaluator.as_dict(series, df) == {}


# ---- Task 2: 截面 rank/zscore 等价(E1/E2: 并列按位次/全等→0.5/单股, ddof=0) ----

# date -> [(symbol, pe_ratio, pb_ratio, roe_ttm), ...]
_PANEL: dict[str, list] = {
    "2024-01-02": [   # 含并列: pe 10,10 与 30,30; pb 含并列
        ("A", 10.0, 2.0, 0.15), ("B", 10.0, 2.0, 0.15),
        ("C", 20.0, 1.0, 0.20), ("D", 30.0, 4.0, 0.10), ("E", 30.0, 0.5, 0.05),
    ],
    "2024-01-03": [   # 全相等 → rank 全 0.5, zscore 全 0
        ("A", 15.0, 3.0, 0.12), ("B", 15.0, 3.0, 0.12), ("C", 15.0, 3.0, 0.12),
        ("D", 15.0, 3.0, 0.12), ("E", 15.0, 3.0, 0.12),
    ],
    "2024-01-04": [   # 仅 A 有值, 其余缺失 → 单股
        ("A", 12.0, 2.5, 0.18), ("B", None, None, None), ("C", None, None, None),
        ("D", None, None, None), ("E", None, None, None),
    ],
}


def _panel_df() -> pd.DataFrame:
    recs = []
    for date, rows in _PANEL.items():
        for sym, pe, pb, roe in rows:
            recs.append({
                "date": pd.Timestamp(date), "symbol": sym,
                "pe_ratio": pe, "pb_ratio": pb, "roe_ttm": roe,
            })
    return pd.DataFrame(recs)


def _panel_snaps(date: str) -> list[StockSnapshot]:
    dt = datetime.fromisoformat(date)
    snaps = []
    for sym, pe, pb, roe in _PANEL[date]:
        snaps.append(StockSnapshot(
            symbol=sym, date=dt, open=10, high=10, low=10, close=10, volume=1000,
            name=sym, list_date=datetime(2020, 1, 1),
            market_cap=1e10, pe_ratio=pe, pb_ratio=pb, roe_ttm=roe,
        ))
    return snaps


@pytest.mark.parametrize("expr_str", [
    "rank(pe_ratio)",
    "zscore(pe_ratio)",
    "rank(1 / pb_ratio) * rank(roe_ttm)",
    "zscore(roe_ttm) + rank(pe_ratio)",
])
def test_cross_section_matches_object_evaluator(expr_str: str):
    expr = _parse(expr_str)
    df = _panel_df()
    series = VectorizedEvaluator().evaluate(expr, df)

    obj_eval = FactorExpressionEvaluator()
    for date in _PANEL:
        mask = df["date"] == pd.Timestamp(date)
        sub = df[mask]
        vec_out = VectorizedEvaluator.as_dict(series[mask], sub)
        obj_out = obj_eval.evaluate(expr, _panel_snaps(date))
        assert set(vec_out) == set(obj_out), f"{expr_str}@{date}: 股票集不一致"
        for sym in obj_out:
            assert vec_out[sym] == pytest.approx(obj_out[sym], abs=1e-12), f"{expr_str}@{date}@{sym}"


class TestVectorizedEvaluatorUnknownField:
    """F10 教训回归测试: 向量化路径与对象式路径对未知字段名一致报错(而非静默全 NaN)。"""

    def test_unknown_field_raises(self):
        from src.domain.strategy.factor_test.field_mapping import UnknownFactorFieldError

        df = _panel_df()
        expr = _parse("gross_margni")  # 拼写错误, 非真实字段
        with pytest.raises(UnknownFactorFieldError, match="gross_margni"):
            VectorizedEvaluator().evaluate(expr, df)

    def test_known_field_missing_from_this_panel_returns_nan(self):
        """已知字段名但本次面板未含该列(窄面板)——非 F10 式错误, 保持 NaN 兜底。"""
        df = _panel_df()
        expr = _parse("rsi_14")  # 合法字段, 但 _panel_df() 未建此列
        series = VectorizedEvaluator().evaluate(expr, df)
        assert series.isna().all()
