from dataclasses import dataclass, field
from datetime import datetime

from src.domain.strategy.value_objects.signal_direction import SignalDirection

@dataclass(slots=True, kw_only=True)
class Signal:
    """策略生成的交易信号实体。

    Attributes:
        symbol: 标的代码 (如 "600000.SH")。
        direction: 信号方向 (BUY/SELL)。
        target_volume: 建议交易数量 (正数)。
        confidence_score: 置信度分数 (0.0 - 1.0)。
        generated_at: 信号生成时间。
        strategy_name: 生成该信号的策略名称 (可选)。
        reason: 生成信号的原因/逻辑描述 (可选)。
    """

    symbol: str
    direction: SignalDirection
    target_volume: int
    confidence_score: float = 1.0
    generated_at: datetime = field(default_factory=datetime.now)
    strategy_name: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        """初始化验证。"""
        if self.target_volume <= 0:
            raise ValueError(f"Signal target_volume must be positive, got {self.target_volume}")
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError(f"Signal confidence_score must be between 0.0 and 1.0, got {self.confidence_score}")
