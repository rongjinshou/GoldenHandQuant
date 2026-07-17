"""precomputed_series 研究口子: 与表达式路径逐位等价(0712 E9)。"""
import pandas as pd

from src.domain.strategy.factor_test.panel import FactorPanel
from src.domain.strategy.factor_test.vectorized_neutralizer import VectorizedNeutralizer
from src.domain.strategy.factor_test.vectorized_runner import VectorizedRunner


def _panel() -> FactorPanel:
    rows = []
    for i, d in enumerate(pd.date_range("2024-01-02", periods=6, freq="B")):
        for j, sym in enumerate(("600000.SH", "000001.SZ", "000002.SZ", "600004.SH")):
            px = 10 + i * (j + 1) * 0.1
            rows.append({
                "date": d, "symbol": sym, "exec_close": px, "close": px,
                "market_cap": 1e9 * (j + 1), "return_20d": 0.01 * (j - 1.5),
            })
    return FactorPanel(pd.DataFrame(rows))


def test_runner_precomputed_equals_expression_path():
    panel = _panel()
    runner = VectorizedRunner()
    via_expr = runner.run("close", panel, num_layers=2)
    via_pre = runner.run("研究列:close", panel, num_layers=2,
                         precomputed_series=panel.df["close"])
    assert via_pre.report.ic_mean == via_expr.report.ic_mean
    assert via_pre.report.long_short_return == via_expr.report.long_short_return
    assert via_pre.report.monotonicity_score == via_expr.report.monotonicity_score


def test_neutralizer_precomputed_equals_expression_path():
    panel = _panel()
    n = VectorizedNeutralizer()
    a = n.mean_neutralized_ic("close", panel)
    b = n.mean_neutralized_ic("研究列:close", panel, precomputed_series=panel.df["close"])
    assert a == b
