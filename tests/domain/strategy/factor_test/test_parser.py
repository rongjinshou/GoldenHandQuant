"""递归下降解析器测试。"""

import pytest

from src.domain.strategy.factor_test.expressions import (
    BinOpExpr,
    FactorRefExpr,
    LiteralExpr,
    UnaryFuncExpr,
)
from src.domain.strategy.factor_test.lexer import tokenize
from src.domain.strategy.factor_test.parser import FactorExpressionParser, ParseError


class TestParserSimple:
    def test_single_factor(self):
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("pe_ratio"))
        assert isinstance(ast, FactorRefExpr)
        assert ast.field_name == "pe_ratio"

    def test_single_number(self):
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("42"))
        assert isinstance(ast, LiteralExpr)
        assert ast.value == 42.0


class TestParserBinOp:
    def test_addition(self):
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("a + b"))
        assert isinstance(ast, BinOpExpr)
        assert ast.op == "+"
        assert isinstance(ast.left, FactorRefExpr)
        assert isinstance(ast.right, FactorRefExpr)

    def test_subtraction(self):
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("a - b"))
        assert isinstance(ast, BinOpExpr)
        assert ast.op == "-"

    def test_multiplication(self):
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("a * b"))
        assert isinstance(ast, BinOpExpr)
        assert ast.op == "*"

    def test_division(self):
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("a / b"))
        assert isinstance(ast, BinOpExpr)
        assert ast.op == "/"


class TestParserPrecedence:
    def test_mul_before_add(self):
        """a + b * c 应解析为 a + (b * c)"""
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("a + b * c"))
        assert isinstance(ast, BinOpExpr)
        assert ast.op == "+"
        assert isinstance(ast.left, FactorRefExpr)
        assert isinstance(ast.right, BinOpExpr)
        assert ast.right.op == "*"

    def test_parentheses_override(self):
        """(a + b) * c 应解析为 (a + b) * c"""
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("(a + b) * c"))
        assert isinstance(ast, BinOpExpr)
        assert ast.op == "*"
        assert isinstance(ast.left, BinOpExpr)
        assert ast.left.op == "+"

    def test_complex_precedence(self):
        """a * b + c / d → (a * b) + (c / d)"""
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("a * b + c / d"))
        assert isinstance(ast, BinOpExpr)
        assert ast.op == "+"
        assert isinstance(ast.left, BinOpExpr) and ast.left.op == "*"
        assert isinstance(ast.right, BinOpExpr) and ast.right.op == "/"


class TestParserFunction:
    def test_simple_function(self):
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("rank(a)"))
        assert isinstance(ast, UnaryFuncExpr)
        assert ast.func == "rank"
        assert isinstance(ast.operand, FactorRefExpr)

    def test_function_with_expression(self):
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("abs(a + b)"))
        assert isinstance(ast, UnaryFuncExpr)
        assert ast.func == "abs"
        assert isinstance(ast.operand, BinOpExpr)

    def test_nested_function(self):
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("rank(abs(a))"))
        assert isinstance(ast, UnaryFuncExpr)
        assert ast.func == "rank"
        assert isinstance(ast.operand, UnaryFuncExpr)
        assert ast.operand.func == "abs"


class TestParserComplex:
    def test_rank_subtraction(self):
        """rank(a) - rank(b)"""
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("rank(a) - rank(b)"))
        assert isinstance(ast, BinOpExpr)
        assert ast.op == "-"
        assert isinstance(ast.left, UnaryFuncExpr) and ast.left.func == "rank"
        assert isinstance(ast.right, UnaryFuncExpr) and ast.right.func == "rank"

    def test_nested_complex(self):
        """rank(a + b) / c"""
        parser = FactorExpressionParser()
        ast = parser.parse(tokenize("rank(a + b) / c"))
        assert isinstance(ast, BinOpExpr)
        assert ast.op == "/"
        assert isinstance(ast.left, UnaryFuncExpr) and ast.left.func == "rank"
        assert isinstance(ast.right, FactorRefExpr) and ast.right.field_name == "c"


class TestParserErrors:
    def test_empty_expression(self):
        parser = FactorExpressionParser()
        with pytest.raises(ParseError):
            parser.parse(tokenize(""))

    def test_unmatched_paren(self):
        parser = FactorExpressionParser()
        with pytest.raises(ParseError):
            parser.parse(tokenize("(a + b"))

    def test_unexpected_token(self):
        parser = FactorExpressionParser()
        with pytest.raises(ParseError):
            parser.parse(tokenize("+ a"))
