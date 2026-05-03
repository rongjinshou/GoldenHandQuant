from dataclasses import dataclass
from datetime import datetime

from src.domain.market.value_objects.bar import Bar


@dataclass(slots=True, kw_only=True)
class GateResult:
    pass_buy: bool
    reason: str = ""


class SystemRiskGate:
    """盘前系统级风控门禁。

    判定当日是否允许买入。不审核单个订单。SELL 信号不受此门禁影响。
    """

    def __init__(self, index_bars: list[Bar] | None = None) -> None:
        self._index_bars = index_bars or []

    def set_index_data(self, bars: list[Bar]) -> None:
        self._index_bars = bars

    def check_gate(self, current_date: datetime) -> GateResult:
        aligned_bars = [b for b in self._index_bars if b.timestamp <= current_date]
        if len(aligned_bars) < 20:
            return GateResult(pass_buy=True)
        recent = aligned_bars[-20:]
        ma20 = sum(b.close for b in recent) / 20
        if recent[-1].close < ma20:
            return GateResult(
                pass_buy=False,
                reason=f"Market circuit breaker: {recent[-1].close:.0f} < MA20 {ma20:.0f}",
            )
        return GateResult(pass_buy=True)
