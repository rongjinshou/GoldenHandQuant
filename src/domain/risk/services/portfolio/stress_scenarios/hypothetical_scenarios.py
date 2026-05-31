from src.domain.risk.services.portfolio.stress_scenarios.historical_scenarios import (
    StressScenario,
)


def get_hypothetical_scenarios() -> list[StressScenario]:
    """返回 5 个假设压力测试场景。"""
    return [
        StressScenario(
            name="市场暴跌",
            scenario_type="hypothetical",
            description="所有策略收益率同时乘以冲击系数 -10%",
            shock_params={"shock_factor": -0.10},
        ),
        StressScenario(
            name="相关性崩溃",
            scenario_type="hypothetical",
            description="危机时所有策略相关性飙升至 0.9",
            shock_params={"crisis_correlation": 0.9},
        ),
        StressScenario(
            name="流动性危机",
            scenario_type="hypothetical",
            description="高换手策略额外承受 2x 滑点惩罚",
            shock_params={"liquidity_penalty": 2.0},
        ),
        StressScenario(
            name="单策略失效",
            scenario_type="hypothetical",
            description="某个策略突然收益率降为 -5%/天，持续 5 天",
            shock_params={"loss_per_day": -0.05, "duration": 5.0},
        ),
        StressScenario(
            name="ML 模型失效",
            scenario_type="hypothetical",
            description="ML 策略预测完全随机，收益率为 0，持续 20 天",
            shock_params={"duration": 20.0},
        ),
    ]
