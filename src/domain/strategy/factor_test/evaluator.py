"""表达式求值器：对 AST 求值，输出每只股票的因子值。"""

import math

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.expressions import (
    BinOpExpr,
    Expr,
    FactorRefExpr,
    LiteralExpr,
    UnaryFuncExpr,
)
from src.domain.strategy.factor_test.field_mapping import resolve_and_validate_field_name


class EvaluationError(Exception):
    """表达式求值错误。"""


class FactorExpressionEvaluator:
    """对 AST 求值，返回每只股票的因子值。

    普通算术和 abs/log/sign 逐股票计算。
    rank/zscore 是截面函数，需要所有股票的值。
    """

    def evaluate(self, expr: Expr, snapshots: list[StockSnapshot]) -> dict[str, float]:
        """返回 {symbol: factor_value}。"""
        if not snapshots:
            return {}
        return self._eval(expr, snapshots)

    def _eval(self, expr: Expr, snapshots: list[StockSnapshot]) -> dict[str, float]:
        match expr:
            case LiteralExpr(value=v):
                return {s.symbol: v for s in snapshots}

            case FactorRefExpr(field_name=name):
                resolved = resolve_and_validate_field_name(name)
                result: dict[str, float] = {}
                for s in snapshots:
                    val = getattr(s, resolved, None)
                    if val is not None:
                        result[s.symbol] = float(val)
                return result

            case BinOpExpr(op=op, left=left, right=right):
                left_vals = self._eval(left, snapshots)
                right_vals = self._eval(right, snapshots)
                return self._apply_binop(op, left_vals, right_vals)

            case UnaryFuncExpr(func=func, operand=operand):
                vals = self._eval(operand, snapshots)
                return self._apply_func(func, vals, snapshots)

        raise EvaluationError(f"Unknown expression type: {type(expr)}")

    def _apply_binop(
        self, op: str, left: dict[str, float], right: dict[str, float]
    ) -> dict[str, float]:
        result: dict[str, float] = {}
        for symbol in left:
            if symbol not in right:
                continue
            lv, rv = left[symbol], right[symbol]
            match op:
                case "+":
                    result[symbol] = lv + rv
                case "-":
                    result[symbol] = lv - rv
                case "*":
                    result[symbol] = lv * rv
                case "/":
                    if rv == 0:
                        continue  # 除零保护：排除该股票
                    result[symbol] = lv / rv
        return result

    def _apply_func(
        self, func: str, vals: dict[str, float], snapshots: list[StockSnapshot]
    ) -> dict[str, float]:
        match func:
            case "abs":
                return {s: abs(v) for s, v in vals.items()}
            case "log":
                result: dict[str, float] = {}
                for s, v in vals.items():
                    if v > 0:
                        result[s] = math.log(v)
                return result
            case "sign":
                return {s: (1.0 if v > 0 else -1.0 if v < 0 else 0.0) for s, v in vals.items()}
            case "rank":
                return self._cross_section_rank(vals)
            case "zscore":
                return self._cross_section_zscore(vals)

        raise EvaluationError(f"Unknown function: {func}")

    def _cross_section_rank(self, vals: dict[str, float]) -> dict[str, float]:
        """截面百分位排名 [0, 1]。"""
        if not vals:
            return {}
        items = sorted(vals.items(), key=lambda x: x[1])
        n = len(items)
        if n == 1:
            return {items[0][0]: 0.5}
        if items[0][1] == items[-1][1]:
            return {s: 0.5 for s in vals}
        result: dict[str, float] = {}
        for rank, (symbol, _) in enumerate(items):
            result[symbol] = rank / (n - 1)
        return result

    def _cross_section_zscore(self, vals: dict[str, float]) -> dict[str, float]:
        """截面 Z 标准化。"""
        if not vals:
            return {}
        n = len(vals)
        if n == 1:
            return {list(vals.keys())[0]: 0.0}
        mean = sum(vals.values()) / n
        var = sum((v - mean) ** 2 for v in vals.values()) / n
        std = var ** 0.5
        if std == 0:
            return {s: 0.0 for s in vals}
        return {s: (v - mean) / std for s, v in vals.items()}
