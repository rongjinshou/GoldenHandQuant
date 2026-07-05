"""表达式求值器测试。"""

from datetime import datetime

import pytest

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.evaluator import FactorExpressionEvaluator
from src.domain.strategy.factor_test.expressions import (
    BinOpExpr,
    FactorRefExpr,
    LiteralExpr,
    UnaryFuncExpr,
)
from src.domain.strategy.factor_test.lexer import tokenize
from src.domain.strategy.factor_test.parser import FactorExpressionParser


def _make_snapshot(symbol: str, **kwargs) -> StockSnapshot:
    defaults = dict(
        symbol=symbol, date=datetime(2024, 6, 15),
        open=10, high=10, low=10, close=10, volume=1000,
        name=f"stock_{symbol}", list_date=datetime(2020, 1, 1),
        market_cap=1e10,
    )
    defaults.update(kwargs)
    return StockSnapshot(**defaults)


def _parse_and_eval(expr_str: str, snapshots: list[StockSnapshot]) -> dict[str, float]:
    parser = FactorExpressionParser()
    evaluator = FactorExpressionEvaluator()
    tokens = tokenize(expr_str)
    ast = parser.parse(tokens)
    return evaluator.evaluate(ast, snapshots)


class TestEvaluatorLiteral:
    def test_literal_broadcasts(self):
        snapshots = [
            _make_snapshot("A"), _make_snapshot("B"), _make_snapshot("C"),
        ]
        result = _parse_and_eval("42", snapshots)
        assert result == {"A": 42.0, "B": 42.0, "C": 42.0}


class TestEvaluatorFactorRef:
    def test_field_extraction(self):
        snapshots = [
            _make_snapshot("A", pe_ratio=10.0),
            _make_snapshot("B", pe_ratio=20.0),
        ]
        result = _parse_and_eval("pe_ratio", snapshots)
        assert result == {"A": 10.0, "B": 20.0}

    def test_none_field_excluded(self):
        snapshots = [
            _make_snapshot("A", pe_ratio=10.0),
            _make_snapshot("B", pe_ratio=None),
        ]
        result = _parse_and_eval("pe_ratio", snapshots)
        assert "A" in result
        assert "B" not in result

    def test_mapped_field_name(self):
        """'roa' 应映射到 'roa_ttm'"""
        snapshots = [
            _make_snapshot("A", roa_ttm=0.05),
        ]
        result = _parse_and_eval("roa", snapshots)
        assert result == {"A": 0.05}


class TestEvaluatorBinOp:
    def test_addition(self):
        snapshots = [
            _make_snapshot("A", pe_ratio=10.0, pb_ratio=1.0),
        ]
        result = _parse_and_eval("pe_ratio + pb_ratio", snapshots)
        assert result["A"] == 11.0

    def test_subtraction(self):
        snapshots = [_make_snapshot("A", close=15.0, open=10.0)]
        result = _parse_and_eval("close - open", snapshots)
        assert result["A"] == 5.0

    def test_multiplication(self):
        snapshots = [_make_snapshot("A", roe_ttm=0.2, pe_ratio=10.0)]
        result = _parse_and_eval("roe_ttm * pe_ratio", snapshots)
        assert result["A"] == 2.0

    def test_division(self):
        snapshots = [_make_snapshot("A", earnings_growth=0.3, pe_ratio=15.0)]
        result = _parse_and_eval("earnings_growth / pe_ratio", snapshots)
        assert abs(result["A"] - 0.02) < 1e-10

    def test_division_by_zero_excluded(self):
        snapshots = [
            _make_snapshot("A", pe_ratio=10.0, pb_ratio=2.0),
            _make_snapshot("B", pe_ratio=0.0, pb_ratio=2.0),
        ]
        result = _parse_and_eval("pb_ratio / pe_ratio", snapshots)
        assert "A" in result
        assert "B" not in result


class TestEvaluatorFunctions:
    def test_abs(self):
        snapshots = [_make_snapshot("A", return_5d=-0.05)]
        result = _parse_and_eval("abs(return_5d)", snapshots)
        assert result["A"] == 0.05

    def test_log(self):
        snapshots = [_make_snapshot("A", market_cap=100.0)]
        result = _parse_and_eval("log(market_cap)", snapshots)
        import math
        assert abs(result["A"] - math.log(100.0)) < 1e-10

    def test_log_negative_excluded(self):
        snapshots = [_make_snapshot("A", pe_ratio=-5.0)]
        result = _parse_and_eval("log(pe_ratio)", snapshots)
        assert "A" not in result

    def test_sign(self):
        snapshots = [
            _make_snapshot("A", return_5d=0.05),
            _make_snapshot("B", return_5d=-0.03),
            _make_snapshot("C", return_5d=0.0),
        ]
        result = _parse_and_eval("sign(return_5d)", snapshots)
        assert result["A"] == 1.0
        assert result["B"] == -1.0
        assert result["C"] == 0.0

    def test_rank(self):
        snapshots = [
            _make_snapshot("A", pe_ratio=10.0),
            _make_snapshot("B", pe_ratio=20.0),
            _make_snapshot("C", pe_ratio=30.0),
        ]
        result = _parse_and_eval("rank(pe_ratio)", snapshots)
        assert result["A"] == 0.0
        assert result["B"] == 0.5
        assert result["C"] == 1.0

    def test_zscore(self):
        snapshots = [
            _make_snapshot("A", pe_ratio=10.0),
            _make_snapshot("B", pe_ratio=20.0),
            _make_snapshot("C", pe_ratio=30.0),
        ]
        result = _parse_and_eval("zscore(pe_ratio)", snapshots)
        # mean = 20, std = sqrt(200/3) ≈ 8.165
        import math
        std = math.sqrt((100 + 0 + 100) / 3)
        assert abs(result["A"] - (10 - 20) / std) < 1e-10
        assert abs(result["B"] - (20 - 20) / std) < 1e-10
        assert abs(result["C"] - (30 - 20) / std) < 1e-10


class TestEvaluatorEmpty:
    def test_empty_snapshots(self):
        result = _parse_and_eval("pe_ratio", [])
        assert result == {}


class TestEvaluatorUnknownField:
    """F10 教训回归测试: 未知字段名须在求值时立即报错，不能静默产出空结果。"""

    def test_unknown_field_raises(self):
        from src.domain.strategy.factor_test.field_mapping import UnknownFactorFieldError

        snapshots = [_make_snapshot("A", pe_ratio=10.0)]
        with pytest.raises(UnknownFactorFieldError, match="gross_margni"):
            _parse_and_eval("gross_margni", snapshots)  # 拼写错误, 非真实字段

    def test_known_but_all_none_field_still_returns_empty(self):
        """已知字段名但恰好全为 None(如未接入的技术指标)——非本次要校验的错误类, 保持原有跳过行为。"""
        snapshots = [_make_snapshot("A"), _make_snapshot("B")]
        result = _parse_and_eval("rsi_14", snapshots)
        assert result == {}
