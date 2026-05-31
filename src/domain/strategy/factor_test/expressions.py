"""AST 节点定义：因子表达式的抽象语法树。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class LiteralExpr:
    """数值常量。"""
    value: float


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorRefExpr:
    """因子字段引用（对应 StockSnapshot 字段名）。"""
    field_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BinOpExpr:
    """二元运算：+, -, *, /"""
    op: str
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True, slots=True, kw_only=True)
class UnaryFuncExpr:
    """一元函数：abs, log, sign, rank, zscore"""
    func: str
    operand: "Expr"


type Expr = LiteralExpr | FactorRefExpr | BinOpExpr | UnaryFuncExpr
