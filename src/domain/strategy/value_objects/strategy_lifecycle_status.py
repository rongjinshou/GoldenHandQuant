from enum import StrEnum


class StrategyLifecycleStatus(StrEnum):
    """策略生命周期状态（比 StrategyStatus 更细化）。"""

    CANDIDATE = "CANDIDATE"      # 已注册，待回测
    BACKTESTING = "BACKTESTING"  # 回测中
    EVALUATING = "EVALUATING"    # 评级中
    ACTIVE = "ACTIVE"            # 已上线
    PAUSED = "PAUSED"            # 暂停
    RETIRED = "RETIRED"          # 已下线
