import logging

from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.risk.services.anomaly_detectors.base import BaseAnomalyDetector
from src.domain.risk.value_objects.anomaly_event import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyType,
    AutoAction,
)

logger = logging.getLogger(__name__)


class MarketAnomalyDetector(BaseAnomalyDetector):
    """市场极端行情检测器。

    检测维度:
    1. 指数暴跌: 沪深300单日跌幅 > 阈值
    2. 连续下跌: 指数连续 N 日下跌
    """

    def __init__(
        self,
        market_gateway: IMarketGateway,
        index_symbol: str = "000300.SH",
        crash_threshold: float = -0.03,
        max_consecutive_drops: int = 5,
    ) -> None:
        self._market_gateway = market_gateway
        self._index_symbol = index_symbol
        self._crash_threshold = crash_threshold
        self._max_consecutive_drops = max_consecutive_drops

    def detect(self) -> list[AnomalyEvent]:
        events: list[AnomalyEvent] = []

        bars = self._market_gateway.get_recent_bars(
            self._index_symbol, Timeframe.DAY_1, 30,
        )

        if not bars or len(bars) < 2:
            return events

        events.extend(self._check_index_crash(bars))
        events.extend(self._check_consecutive_drops(bars))

        return events

    def _check_index_crash(self, bars: list) -> list[AnomalyEvent]:
        """检测指数单日暴跌。"""
        events: list[AnomalyEvent] = []

        prev_close = bars[-2].close
        curr_close = bars[-1].close
        if prev_close <= 0:
            return events

        change = (curr_close - prev_close) / prev_close
        if change <= self._crash_threshold:
            events.append(AnomalyEvent(
                anomaly_type=AnomalyType.MARKET,
                severity=AnomalySeverity.CRITICAL,
                source=self._index_symbol,
                message=(
                    f"指数 {self._index_symbol} 暴跌: "
                    f"{change:.2%} (阈值: {self._crash_threshold:.2%})"
                ),
                metric_value=change,
                threshold=self._crash_threshold,
                auto_action=AutoAction.PAUSE_ALL,
            ))

        return events

    def _check_consecutive_drops(self, bars: list) -> list[AnomalyEvent]:
        """检测指数连续下跌。"""
        events: list[AnomalyEvent] = []

        consecutive_drops = 0
        for i in range(len(bars) - 1, 0, -1):
            if bars[i].close < bars[i - 1].close:
                consecutive_drops += 1
            else:
                break

        if consecutive_drops >= self._max_consecutive_drops:
            events.append(AnomalyEvent(
                anomaly_type=AnomalyType.MARKET,
                severity=AnomalySeverity.CRITICAL,
                source=self._index_symbol,
                message=(
                    f"指数 {self._index_symbol} 连续下跌 {consecutive_drops} 日 "
                    f"(阈值: {self._max_consecutive_drops})"
                ),
                metric_value=float(consecutive_drops),
                threshold=float(self._max_consecutive_drops),
                auto_action=AutoAction.PAUSE_ALL,
            ))

        return events
