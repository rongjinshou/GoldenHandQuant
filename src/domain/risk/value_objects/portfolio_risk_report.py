import copy
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.risk.value_objects.correlation_matrix import CorrelationMatrix
from src.domain.risk.value_objects.diversification_result import DiversificationResult
from src.domain.risk.value_objects.ml_risk_alert import MLRiskAlert
from src.domain.risk.value_objects.stress_test_result import StressTestResult
from src.domain.risk.value_objects.var_result import VaRResult


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioRiskReport:
    """组合风控综合报告。

    Attributes:
        computed_at: 计算时间。
        strategy_count: 参与组合的策略数。
        correlation: 相关性矩阵。
        diversification: 分散度评估。
        var_95: 95% 置信水平 VaR。
        var_99: 99% 置信水平 VaR。
        stress_tests: 压力测试结果列表。
        ml_alerts: ML 风险告警列表。
        overall_risk_level: 整体风险等级（"low"、"medium"、"high"、"critical"）。
        recommendations: 风险建议列表。
    """

    computed_at: datetime = datetime.now()
    strategy_count: int = 0
    correlation: CorrelationMatrix = field(default_factory=lambda: CorrelationMatrix(
        strategy_names=[], matrix=[], computed_at=datetime.now()
    ))
    diversification: DiversificationResult = field(default_factory=lambda: DiversificationResult(
        diversification_ratio=1.0, effective_strategies=1.0,
        concentration_index=1.0, max_pairwise_correlation=0.0, is_well_diversified=False
    ))
    var_95: VaRResult = field(default_factory=lambda: VaRResult(
        confidence_level=0.95, method="historical", var_absolute=0.0,
        var_percentage=0.0, cvar=0.0, holding_period=1, portfolio_value=0.0
    ))
    var_99: VaRResult = field(default_factory=lambda: VaRResult(
        confidence_level=0.99, method="historical", var_absolute=0.0,
        var_percentage=0.0, cvar=0.0, holding_period=1, portfolio_value=0.0
    ))
    stress_tests: list[StressTestResult] = field(default_factory=list)
    ml_alerts: list[MLRiskAlert] = field(default_factory=list)
    overall_risk_level: str = "low"
    recommendations: list[str] = field(default_factory=list)

    def __post_init__(self):
        for field_name in self.__dataclass_fields__:
            val = getattr(self, field_name)
            if isinstance(val, (list, dict, set)):
                object.__setattr__(self, field_name, copy.deepcopy(val))
