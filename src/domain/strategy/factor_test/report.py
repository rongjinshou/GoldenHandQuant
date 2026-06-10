"""因子测试报告值对象。"""

import copy
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorTestReport:
    """因子测试结果报告（不含评分）。"""
    expression: str
    test_period: tuple[str, str]
    universe_count: int

    # IC/IR
    ic_mean: float
    ic_std: float
    ir: float
    ic_positive_rate: float
    ic_series: list[tuple[str, float]] = field(default_factory=list)

    # 分层收益
    layer_count: int = 5
    rebalance_days: int = 1
    layer_returns: list[float] = field(default_factory=list)
    long_short_return: float = 0.0
    layer_cumulative: list[list[float]] = field(default_factory=list)

    # 单调性
    monotonicity_score: float = 0.0

    # 因子衰减
    decay_periods: list[int] = field(default_factory=list)
    decay_ics: list[float] = field(default_factory=list)

    def __post_init__(self):
        for field_name in self.__dataclass_fields__:
            val = getattr(self, field_name)
            if isinstance(val, (list, dict, set)):
                object.__setattr__(self, field_name, copy.deepcopy(val))


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoredFactorTestReport:
    """包含评分的因子测试报告，通过工厂方法一次性构建。"""

    report: FactorTestReport
    score: float
    grade: str
    grade_reasons: list[str]

    def __post_init__(self):
        object.__setattr__(self, "grade_reasons", copy.deepcopy(self.grade_reasons))

    # 便捷属性代理，兼容已有代码直接访问 report 字段
    @property
    def expression(self) -> str:
        return self.report.expression

    @property
    def test_period(self) -> tuple[str, str]:
        return self.report.test_period

    @property
    def universe_count(self) -> int:
        return self.report.universe_count

    @property
    def ic_mean(self) -> float:
        return self.report.ic_mean

    @property
    def ic_std(self) -> float:
        return self.report.ic_std

    @property
    def ir(self) -> float:
        return self.report.ir

    @property
    def ic_positive_rate(self) -> float:
        return self.report.ic_positive_rate

    @property
    def ic_series(self) -> list[tuple[str, float]]:
        return self.report.ic_series

    @property
    def layer_count(self) -> int:
        return self.report.layer_count

    @property
    def rebalance_days(self) -> int:
        return self.report.rebalance_days

    @property
    def layer_returns(self) -> list[float]:
        return self.report.layer_returns

    @property
    def long_short_return(self) -> float:
        return self.report.long_short_return

    @property
    def layer_cumulative(self) -> list[list[float]]:
        return self.report.layer_cumulative

    @property
    def monotonicity_score(self) -> float:
        return self.report.monotonicity_score

    @property
    def decay_periods(self) -> list[int]:
        return self.report.decay_periods

    @property
    def decay_ics(self) -> list[float]:
        return self.report.decay_ics
