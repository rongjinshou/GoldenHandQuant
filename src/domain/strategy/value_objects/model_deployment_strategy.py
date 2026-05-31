"""模型部署策略枚举。"""

from enum import StrEnum


class ModelDeploymentStrategy(StrEnum):
    """ML 模型部署策略。

    流转路径:
    SHADOW → CANARY → FULL_ROLLOUT

    - FULL_ROLLOUT: 全量部署，模型产出实际交易信号。
    - CANARY: 灰度部署，按 traffic_percentage 比例分流。
    - SHADOW: 影子部署，模型产出预测信号但不执行交易。
    """

    FULL_ROLLOUT = "FULL_ROLLOUT"
    CANARY = "CANARY"
    SHADOW = "SHADOW"
