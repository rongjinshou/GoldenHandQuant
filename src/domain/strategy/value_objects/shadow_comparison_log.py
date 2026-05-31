"""影子模式对比日志值对象。"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class ShadowComparisonLog:
    """影子模式单条信号对比记录（不可变值对象）。

    记录活跃模型与影子模型在同一标的上产生的信号对比。

    Attributes:
        active_version_id: 活跃模型版本 ID。
        shadow_version_id: 影子模型版本 ID。
        symbol: 标的代码。
        active_direction: 活跃模型信号方向 ("BUY" / "SELL" / "HOLD")。
        shadow_direction: 影子模型信号方向。
        active_confidence: 活跃模型置信度 (0.0 ~ 1.0)。
        shadow_confidence: 影子模型置信度 (0.0 ~ 1.0)。
        match: 两者方向是否一致。
        divergence: 差异度 (0.0 ~ 1.0)。
        recorded_at: 记录时间。
    """

    active_version_id: str
    shadow_version_id: str
    symbol: str
    active_direction: str
    shadow_direction: str
    active_confidence: float
    shadow_confidence: float
    match: bool
    divergence: float
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not (0.0 <= self.active_confidence <= 1.0):
            raise ValueError(
                f"active_confidence must be in [0.0, 1.0], got {self.active_confidence}"
            )
        if not (0.0 <= self.shadow_confidence <= 1.0):
            raise ValueError(
                f"shadow_confidence must be in [0.0, 1.0], got {self.shadow_confidence}"
            )
        if not (0.0 <= self.divergence <= 1.0):
            raise ValueError(
                f"divergence must be in [0.0, 1.0], got {self.divergence}"
            )

    @staticmethod
    def compute_divergence(
        active_confidence: float,
        shadow_confidence: float,
        directions_match: bool,
    ) -> float:
        """计算两个信号之间的差异度。

        方向一致时: 差异 = |confidence_a - confidence_s|
        方向不一致时: 差异 = 1.0 - |confidence_a - confidence_s| * 0.5
        """
        conf_diff = abs(active_confidence - shadow_confidence)
        if directions_match:
            return round(conf_diff, 6)
        return round(1.0 - conf_diff * 0.5, 6)
