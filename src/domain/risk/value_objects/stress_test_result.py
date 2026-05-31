from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class StressTestResult:
    """单个压力测试场景的结果。

    Attributes:
        scenario_name: 场景名称。
        scenario_type: 场景类型（"historical" 或 "hypothetical"）。
        description: 场景描述。
        portfolio_loss: 组合损失（百分比）。
        strategy_losses: 各策略的损失 {strategy_name: loss_percentage}。
        max_drawdown_under_stress: 压力期间最大回撤。
        recovery_days: 预计恢复天数（-1 表示无法恢复）。
        passed: 是否通过压力测试（组合损失 < 阈值）。
    """

    scenario_name: str
    scenario_type: str
    description: str
    portfolio_loss: float
    strategy_losses: dict[str, float]
    max_drawdown_under_stress: float
    recovery_days: int
    passed: bool
