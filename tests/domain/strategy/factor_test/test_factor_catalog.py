"""factor_catalog 测试 — 解析 + P3 第二-edge 研究因子可用性。"""

from src.domain.strategy.factor_test.factor_catalog import (
    P3_FACTORS,
    P4_FACTORS,
    resolve_factors,
)
from src.domain.strategy.factor_test.lexer import tokenize
from src.domain.strategy.factor_test.parser import FactorExpressionParser


def test_resolve_p3_returns_research_factors():
    fs = resolve_factors("P3")
    assert {f.factor_id for f in fs} == {"F20", "F21", "F22", "F23", "F24", "F25", "F26", "F27"}
    assert all(f.priority == "P3" for f in fs)
    # P3 仅用已就绪字段(market_cap/roe/ocf/pe/pb/earnings_growth/revenue_growth + 技术指标)
    assert all(f.field_ready for f in fs)


def test_p3_expressions_parse():
    parser = FactorExpressionParser()
    for f in P3_FACTORS:
        parser.parse(tokenize(f.expression))  # 不抛异常即视为通过


def test_resolve_all_includes_p3():
    ids = {f.factor_id for f in resolve_factors("all")}
    assert {"F20", "F23", "F27"} <= ids


def test_resolve_p4_composite_factors():
    fs = resolve_factors("P4")
    assert {f.factor_id for f in fs} == {"F30", "F31"}
    assert all(f.priority == "P4" and f.category == "复合" for f in fs)


def test_p4_expressions_parse():
    parser = FactorExpressionParser()
    for f in P4_FACTORS:
        parser.parse(tokenize(f.expression))  # 嵌套 zscore(rank()*rank())+... 可解析


def test_resolve_ids_and_priority_groups():
    assert [f.factor_id for f in resolve_factors("F01")] == ["F01"]
    assert all(f.priority == "P0" for f in resolve_factors("P0"))
