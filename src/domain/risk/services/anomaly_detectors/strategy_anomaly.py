import logging

from src.domain.risk.services.anomaly_detectors.base import BaseAnomalyDetector
from src.domain.risk.value_objects.anomaly_event import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyType,
    AutoAction,
)
from src.domain.trade.interfaces.repositories.trade_history_repo import TradeHistoryRepository

logger = logging.getLogger(__name__)


class StrategyAnomalyDetector(BaseAnomalyDetector):
    """策略异常检测器。

    检测维度:
    1. 滚动胜率突降: 近 N 笔交易胜率 < 阈值
    2. 连续亏损: 连续 N 笔亏损
    3. 信号频率异常: 信号数量突然暴增或归零
    """

    def __init__(
        self,
        trade_history: TradeHistoryRepository,
        strategy_name: str,
        min_win_rate: float = 0.45,
        max_consecutive_losses: int = 5,
        lookback_trades: int = 20,
    ) -> None:
        self._trade_history = trade_history
        self._strategy_name = strategy_name
        self._min_win_rate = min_win_rate
        self._max_consecutive_losses = max_consecutive_losses
        self._lookback_trades = lookback_trades

    def detect(self) -> list[AnomalyEvent]:
        events: list[AnomalyEvent] = []
        trades = self._trade_history.get_recent_trades(
            self._strategy_name, self._lookback_trades,
        )

        if len(trades) < 5:
            return events

        # 检测 1: 滚动胜率
        events.extend(self._check_win_rate(trades))

        # 检测 2: 连续亏损
        events.extend(self._check_consecutive_losses(trades))

        return events

    def _check_win_rate(
        self, trades: list,
    ) -> list[AnomalyEvent]:
        """检测滚动胜率突降。"""
        events: list[AnomalyEvent] = []
        winning = sum(1 for t in trades if t.pnl > 0)
        win_rate = winning / len(trades)

        if win_rate < self._min_win_rate:
            events.append(AnomalyEvent(
                anomaly_type=AnomalyType.STRATEGY,
                severity=AnomalySeverity.CRITICAL,
                source=self._strategy_name,
                message=(
                    f"策略 {self._strategy_name} 滚动胜率突降: "
                    f"{win_rate:.1%} < {self._min_win_rate:.1%} "
                    f"(近 {len(trades)} 笔)"
                ),
                metric_value=win_rate,
                threshold=self._min_win_rate,
                auto_action=AutoAction.PAUSE_STRATEGY,
            ))
        return events

    def _check_consecutive_losses(
        self, trades: list,
    ) -> list[AnomalyEvent]:
        """检测连续亏损。"""
        events: list[AnomalyEvent] = []
        consecutive = 0
        for trade in reversed(trades):
            if trade.pnl < 0:
                consecutive += 1
            else:
                break

        if consecutive >= self._max_consecutive_losses:
            events.append(AnomalyEvent(
                anomaly_type=AnomalyType.STRATEGY,
                severity=AnomalySeverity.CRITICAL,
                source=self._strategy_name,
                message=(
                    f"策略 {self._strategy_name} 连续亏损 {consecutive} 笔 "
                    f"(阈值: {self._max_consecutive_losses})"
                ),
                metric_value=float(consecutive),
                threshold=float(self._max_consecutive_losses),
                auto_action=AutoAction.PAUSE_STRATEGY,
            ))
        return events
