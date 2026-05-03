from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.risk.services.base_risk_signal_policy import BaseRiskSignalPolicy
from src.domain.strategy.value_objects.signal import Signal


class RiskSignalGenerator:
    """盘后风控信号生成器。

    聚合多个 BaseRiskSignalPolicy，评估持仓状态，主动产出 SELL 信号。
    """

    def __init__(self, policies: list[BaseRiskSignalPolicy] | None = None) -> None:
        self._policies = policies or []

    def evaluate(
        self, positions: list[Position], bars: dict[str, Bar]
    ) -> list[Signal]:
        signals: list[Signal] = []
        for policy in self._policies:
            signals.extend(policy.evaluate_positions(positions, bars))
        return signals
