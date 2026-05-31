from dataclasses import dataclass

from src.application.live_signal_service import SignalDisplay
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.strategy.value_objects.signal_direction import SignalDirection


@dataclass(slots=True, kw_only=True)
class EnhancedSignalDisplay(SignalDisplay):
    """增强信号展示 — 在原有基础上增加审核相关字段。"""
    risk_score: float = 0.0
    ml_confidence: float = 0.0
    signal_age_hours: float = 0.0
    historical_win_rate: float = 0.0


def calculate_risk_score(
    signal_display: SignalDisplay,
    position: Position | None,
    asset: Asset,
) -> float:
    """计算信号风险评分 (0.0 = 低风险, 1.0 = 高风险)。

    基于:
    - 持仓集中度: 单只标的资金占比越高，风险越大
    - 信号置信度: 置信度越低，风险越大
    - 方向: 卖出风险低于买入（卖出释放资金）
    """
    score = 0.0

    # 持仓集中度 (0.0 ~ 0.4)
    if asset.total_asset > 0:
        concentration = signal_display.required_capital / asset.total_asset
        score += min(concentration * 4.0, 0.4)

    # 置信度反转 (0.0 ~ 0.4): 置信度 1.0 -> 0.0 风险, 置信度 0.0 -> 0.4 风险
    score += (1.0 - signal_display.confidence_score) * 0.4

    # 方向调整 (0.0 ~ 0.2): 买入比卖出风险高
    if signal_display.direction == SignalDirection.BUY:
        score += 0.2

    return round(min(max(score, 0.0), 1.0), 4)
