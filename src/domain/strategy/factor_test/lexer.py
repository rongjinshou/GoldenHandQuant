"""词法分析器：将因子表达式字符串拆分为 Token 列表。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class Token:
    type: str   # NUMBER, FACTOR_NAME, FUNC_NAME, OP, LPAREN, RPAREN, EOF
    value: str


SUPPORTED_FUNCS = {"abs", "log", "sign", "rank", "zscore"}


def tokenize(expr: str) -> list[Token]:
    """将表达式字符串词法分析为 Token 列表。"""
    tokens: list[Token] = []
    i = 0
    n = len(expr)

    while i < n:
        ch = expr[i]

        # 跳过空白
        if ch in " \t\n\r":
            i += 1
            continue

        # 运算符
        if ch in "+-*/":
            tokens.append(Token(type="OP", value=ch))
            i += 1
            continue

        # 括号
        if ch == "(":
            tokens.append(Token(type="LPAREN", value="("))
            i += 1
            continue
        if ch == ")":
            tokens.append(Token(type="RPAREN", value=")"))
            i += 1
            continue

        # 数字（含小数点）
        if ch.isdigit():
            start = i
            while i < n and (expr[i].isdigit() or expr[i] == "."):
                i += 1
            tokens.append(Token(type="NUMBER", value=expr[start:i]))
            continue

        # 标识符（因子名或函数名）
        if ch.islower() or ch == "_":
            start = i
            while i < n and (expr[i].isalnum() or expr[i] == "_"):
                i += 1
            word = expr[start:i]
            if word in SUPPORTED_FUNCS:
                tokens.append(Token(type="FUNC_NAME", value=word))
            else:
                tokens.append(Token(type="FACTOR_NAME", value=word))
            continue

        raise ValueError(f"Unexpected character: '{ch}' at position {i}")

    tokens.append(Token(type="EOF", value=""))
    return tokens
