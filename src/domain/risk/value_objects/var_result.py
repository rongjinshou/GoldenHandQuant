from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class VaRResult:
    """组合风险价值（VaR）计算结果。

    Attributes:
        confidence_level: 置信水平（如 0.95、0.99）。
        method: 计算方法（"historical" 或 "parametric"）。
        var_absolute: 绝对 VaR（损失金额）。
        var_percentage: 百分比 VaR（损失比例）。
        cvar: 条件 VaR（Expected Shortfall，尾部平均损失）。
        holding_period: 持有期（天数）。
        portfolio_value: 组合总价值。
        computed_at: 计算时间。
    """

    confidence_level: float
    method: str
    var_absolute: float
    var_percentage: float
    cvar: float
    holding_period: int
    portfolio_value: float
    computed_at: datetime = datetime.now()
