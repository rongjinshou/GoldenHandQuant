"""向量化表达式求值器：对 AST 在列式面板上求值，输出每行因子值。

与对象式 ``FactorExpressionEvaluator`` 行为逐位等价(见 docs/feat/0614-columnar-factor-engine
设计 §6 等价陷阱), 但以 pandas 列运算替代逐股 Python 循环。普通算术 + abs/log/sign 逐元素;
rank/zscore 是截面函数, 按 ``date`` 分组。domain 红线允许 numpy/pandas 纯计算。
"""

import numpy as np
import pandas as pd

from src.domain.strategy.factor_test.expressions import (
    BinOpExpr,
    Expr,
    FactorRefExpr,
    LiteralExpr,
    UnaryFuncExpr,
)
from src.domain.strategy.factor_test.field_mapping import resolve_field_name


class VectorizedEvaluationError(Exception):
    """向量化求值错误。"""


class VectorizedEvaluator:
    """对 AST 求值，返回与面板 index 对齐的因子值 Series。

    面板 DataFrame 须含 ``date`` 列(rank/zscore 截面分组用)与各因子字段列。
    """

    def evaluate(self, expr: Expr, df: pd.DataFrame) -> pd.Series:
        """返回因子值 Series(index 对齐 df, 缺失/无效 = NaN)。"""
        if df.empty:
            return pd.Series(dtype=float)
        return self._eval(expr, df)

    def _eval(self, expr: Expr, df: pd.DataFrame) -> pd.Series:
        match expr:
            case LiteralExpr(value=v):
                return pd.Series(float(v), index=df.index, dtype=float)

            case FactorRefExpr(field_name=name):
                col = resolve_field_name(name)
                if col not in df.columns:
                    return pd.Series(np.nan, index=df.index, dtype=float)
                return pd.to_numeric(df[col], errors="coerce").astype(float)

            case BinOpExpr(op=op, left=left, right=right):
                return self._apply_binop(op, self._eval(left, df), self._eval(right, df))

            case UnaryFuncExpr(func=func, operand=operand):
                return self._apply_func(func, self._eval(operand, df), df)

        raise VectorizedEvaluationError(f"Unknown expression type: {type(expr)}")

    @staticmethod
    def _apply_binop(op: str, left: pd.Series, right: pd.Series) -> pd.Series:
        match op:
            case "+":
                return left + right
            case "-":
                return left - right
            case "*":
                return left * right
            case "/":
                # 除零保护: 分母为 0 → NaN(对象式丢弃该股, 下游 dropna 一致)
                return left / right.where(right != 0)
        raise VectorizedEvaluationError(f"Unknown operator: {op}")

    def _apply_func(self, func: str, s: pd.Series, df: pd.DataFrame) -> pd.Series:
        match func:
            case "abs":
                return s.abs()
            case "sign":
                return pd.Series(np.sign(s.to_numpy()), index=s.index, dtype=float)
            case "log":
                # 仅 v>0; 其余 → NaN(对象式丢弃)
                return np.log(s.where(s > 0))
            case "rank":
                return s.groupby(df["date"], sort=False, group_keys=False).apply(
                    self._rank_group
                )
            case "zscore":
                return s.groupby(df["date"], sort=False, group_keys=False).apply(
                    self._zscore_group
                )
        raise VectorizedEvaluationError(f"Unknown function: {func}")

    @staticmethod
    def _rank_group(s: pd.Series) -> pd.Series:
        """截面百分位排名 [0,1]，与对象式逐位等价。

        对象式: 按值稳定排序后 enumerate → 并列按出现顺序(非平均秩);
        全相等 → 0.5; 单股 → 0.5。故用 method='first' + 显式全等/单股分支。
        """
        out = pd.Series(np.nan, index=s.index, dtype=float)
        valid = s.dropna()
        n = len(valid)
        if n == 0:
            return out
        if n == 1 or valid.max() == valid.min():
            out.loc[valid.index] = 0.5
            return out
        r = valid.rank(method="first")
        out.loc[valid.index] = (r - 1) / (n - 1)
        return out

    @staticmethod
    def _zscore_group(s: pd.Series) -> pd.Series:
        """截面 Z 标准化(总体标准差 ddof=0)，单股→0, std==0→0。"""
        out = pd.Series(np.nan, index=s.index, dtype=float)
        valid = s.dropna()
        n = len(valid)
        if n == 0:
            return out
        if n == 1:
            out.loc[valid.index] = 0.0
            return out
        mean = valid.mean()
        std = valid.std(ddof=0)
        out.loc[valid.index] = 0.0 if std == 0 else (valid - mean) / std
        return out

    @staticmethod
    def as_dict(series: pd.Series, df: pd.DataFrame) -> dict[str, float]:
        """{symbol: value}，丢弃 NaN(对应对象式的缺失跳过)。单日截面用。"""
        syms = df["symbol"].to_numpy()
        vals = series.to_numpy()
        return {
            syms[i]: float(vals[i])
            for i in range(len(vals))
            if not pd.isna(vals[i])
        }
