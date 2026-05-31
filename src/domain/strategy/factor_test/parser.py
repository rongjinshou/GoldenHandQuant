"""递归下降解析器：将 Token 列表解析为 AST。"""

from src.domain.strategy.factor_test.expressions import (
    BinOpExpr,
    Expr,
    FactorRefExpr,
    LiteralExpr,
    UnaryFuncExpr,
)
from src.domain.strategy.factor_test.lexer import Token


class ParseError(Exception):
    """语法分析错误。"""


class FactorExpressionParser:
    """递归下降解析器。

    语法规则（运算符优先级从低到高）：
        expression  → term (('+' | '-') term)*
        term        → factor_expr (('*' | '/') factor_expr)*
        factor_expr → '(' expression ')'
                    | FUNC_NAME '(' expression ')'
                    | FACTOR_NAME
                    | NUMBER
    """

    def __init__(self) -> None:
        self._tokens: list[Token] = []
        self._pos: int = 0

    def parse(self, tokens: list[Token]) -> Expr:
        """解析 Token 列表为 AST。"""
        self._tokens = tokens
        self._pos = 0
        result = self._parse_expression()
        if self._current().type != "EOF":
            raise ParseError(f"Unexpected token: {self._current().value}")
        return result

    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _expect(self, token_type: str) -> Token:
        token = self._current()
        if token.type != token_type:
            raise ParseError(f"Expected {token_type}, got {token.type} ('{token.value}')")
        return self._advance()

    def _parse_expression(self) -> Expr:
        """expression → term (('+' | '-') term)*"""
        left = self._parse_term()
        while self._current().type == "OP" and self._current().value in ("+", "-"):
            op = self._advance().value
            right = self._parse_term()
            left = BinOpExpr(op=op, left=left, right=right)
        return left

    def _parse_term(self) -> Expr:
        """term → factor_expr (('*' | '/') factor_expr)*"""
        left = self._parse_factor_expr()
        while self._current().type == "OP" and self._current().value in ("*", "/"):
            op = self._advance().value
            right = self._parse_factor_expr()
            left = BinOpExpr(op=op, left=left, right=right)
        return left

    def _parse_factor_expr(self) -> Expr:
        """factor_expr → '(' expression ')' | FUNC_NAME '(' expression ')' | FACTOR_NAME | NUMBER"""
        token = self._current()

        # 括号表达式
        if token.type == "LPAREN":
            self._advance()
            expr = self._parse_expression()
            self._expect("RPAREN")
            return expr

        # 函数调用
        if token.type == "FUNC_NAME":
            func_name = self._advance().value
            self._expect("LPAREN")
            operand = self._parse_expression()
            self._expect("RPAREN")
            return UnaryFuncExpr(func=func_name, operand=operand)

        # 因子引用
        if token.type == "FACTOR_NAME":
            name = self._advance().value
            return FactorRefExpr(field_name=name)

        # 数值常量
        if token.type == "NUMBER":
            value = float(self._advance().value)
            return LiteralExpr(value=value)

        raise ParseError(f"Unexpected token: {token.type} ('{token.value}')")
