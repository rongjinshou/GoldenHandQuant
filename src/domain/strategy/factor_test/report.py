"""因子测试报告值对象。"""

import copy
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorTestReport:
    """因子测试结果报告。"""
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
    layer_returns: list[float] = field(default_factory=list)
    long_short_return: float = 0.0
    layer_cumulative: list[list[float]] = field(default_factory=list)

    # 单调性
    monotonicity_score: float = 0.0

    # 因子衰减
    decay_periods: list[int] = field(default_factory=list)
    decay_ics: list[float] = field(default_factory=list)

    # 综合评分
    score: float = 0.0
    grade: str = "D"
    grade_reasons: list[str] = field(default_factory=list)

    def __post_init__(self):
        for field_name in self.__dataclass_fields__:
            val = getattr(self, field_name)
            if isinstance(val, (list, dict, set)):
                object.__setattr__(self, field_name, copy.deepcopy(val))
