from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.price_limit import calculate_price_limits
from src.domain.risk.services.base_risk_signal_policy import BaseRiskSignalPolicy
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection


class LimitUpBreakPolicy(BaseRiskSignalPolicy):
    """涨停破板卖出策略。

    若当日最高价触及涨停价，但收盘价未封住涨停，则判定为多头动能衰竭，
    无条件触发清仓卖出信号。
    """

    def evaluate_positions(
        self, positions: list[Position], bars: dict[str, Bar]
    ) -> list[Signal]:
        signals: list[Signal] = []
        for pos in positions:
            bar = bars.get(pos.ticker)
            if bar is None or bar.volume <= 0 or bar.prev_close <= 0:
                continue
            price_limit = calculate_price_limits(bar.prev_close)
            if bar.high >= price_limit.limit_up and bar.close < price_limit.limit_up:
                signals.append(Signal(
                    symbol=pos.ticker, direction=SignalDirection.SELL,
                    confidence_score=1.0, strategy_name="LimitUpBreak",
                    reason=f"涨停破板: high={bar.high} limit_up={price_limit.limit_up} close={bar.close}",
                    generated_at=bar.timestamp,
                ))
        return signals
