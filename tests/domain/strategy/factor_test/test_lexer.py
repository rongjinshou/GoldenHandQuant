"""词法分析器测试。"""

from src.domain.strategy.factor_test.lexer import Token, tokenize


class TestLexerNumbers:
    def test_integer(self):
        tokens = tokenize("42")
        assert tokens[0] == Token(type="NUMBER", value="42")
        assert tokens[1].type == "EOF"

    def test_decimal(self):
        tokens = tokenize("3.14")
        assert tokens[0] == Token(type="NUMBER", value="3.14")

    def test_zero(self):
        tokens = tokenize("0")
        assert tokens[0] == Token(type="NUMBER", value="0")


class TestLexerIdentifiers:
    def test_factor_name(self):
        tokens = tokenize("pe_ratio")
        assert tokens[0] == Token(type="FACTOR_NAME", value="pe_ratio")

    def test_func_name_abs(self):
        tokens = tokenize("abs(x)")
        assert tokens[0] == Token(type="FUNC_NAME", value="abs")

    def test_func_name_rank(self):
        tokens = tokenize("rank(x)")
        assert tokens[0] == Token(type="FUNC_NAME", value="rank")

    def test_func_name_zscore(self):
        tokens = tokenize("zscore(x)")
        assert tokens[0] == Token(type="FUNC_NAME", value="zscore")


class TestLexerOperators:
    def test_plus(self):
        tokens = tokenize("a + b")
        assert tokens[1] == Token(type="OP", value="+")

    def test_divide(self):
        tokens = tokenize("a / b")
        assert tokens[1] == Token(type="OP", value="/")

    def test_parentheses(self):
        tokens = tokenize("(a)")
        assert tokens[0] == Token(type="LPAREN", value="(")
        assert tokens[2] == Token(type="RPAREN", value=")")


class TestLexerComplexExpression:
    def test_full_expression(self):
        tokens = tokenize("earnings_growth / pe_ratio")
        types = [t.type for t in tokens]
        assert types == ["FACTOR_NAME", "OP", "FACTOR_NAME", "EOF"]

    def test_function_expression(self):
        tokens = tokenize("rank(a + b) * c")
        types = [t.type for t in tokens]
        assert types == [
            "FUNC_NAME", "LPAREN", "FACTOR_NAME", "OP", "FACTOR_NAME",
            "RPAREN", "OP", "FACTOR_NAME", "EOF",
        ]

    def test_nested_function(self):
        tokens = tokenize("abs(log(x))")
        types = [t.type for t in tokens]
        assert types == [
            "FUNC_NAME", "LPAREN", "FUNC_NAME", "LPAREN", "FACTOR_NAME",
            "RPAREN", "RPAREN", "EOF",
        ]

    def test_complex_expression(self):
        tokens = tokenize("rank(earnings_growth) - rank(pe_ratio)")
        types = [t.type for t in tokens]
        assert types == [
            "FUNC_NAME", "LPAREN", "FACTOR_NAME", "RPAREN",
            "OP",
            "FUNC_NAME", "LPAREN", "FACTOR_NAME", "RPAREN",
            "EOF",
        ]


class TestLexerErrors:
    def test_unexpected_character(self):
        import pytest
        with pytest.raises(ValueError, match="Unexpected character"):
            tokenize("a @ b")
