from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.risk.services.base_risk_signal_policy import BaseRiskSignalPolicy
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection


class HardStopLossPolicy(BaseRiskSignalPolicy):
    """绝对止损策略。

    若持仓账面亏损超过 max_loss_ratio，立刻生成市价清仓信号。
    """

    def __init__(self, max_loss_ratio: float = 0.03) -> None:
        self._max_loss = max_loss_ratio

    def evaluate_positions(
        self, positions: list[Position], bars: dict[str, Bar]
    ) -> list[Signal]:
        signals: list[Signal] = []
        for pos in positions:
            bar = bars.get(pos.ticker)
            if bar is None or pos.total_volume <= 0 or pos.average_cost <= 0:
                continue
            loss_ratio = (bar.close - pos.average_cost) / pos.average_cost
            if loss_ratio < -self._max_loss:
                signals.append(Signal(
                    symbol=pos.ticker, direction=SignalDirection.SELL,
                    confidence_score=1.0, strategy_name="HardStopLoss",
                    reason=f"Stop loss: {loss_ratio:.2%} < -{self._max_loss:.0%}",
                    generated_at=bar.timestamp,
                ))
        return signals
