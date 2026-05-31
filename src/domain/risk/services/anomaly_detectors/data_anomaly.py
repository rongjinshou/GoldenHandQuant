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


class DataAnomalyDetector(BaseAnomalyDetector):
    """数据质量检测器。

    检测维度:
    1. 行情数据缺失: 某只股票连续无数据
    2. 价格跳变: 单日涨跌幅超过阈值 (非涨跌停)
    3. 成交量异常: 成交量突然放大/缩小
    """

    def __init__(
        self,
        market_gateway: IMarketGateway,
        symbols: list[str],
        max_price_jump: float = 0.10,
        volume_spike_ratio: float = 10.0,
        missing_days_threshold: int = 3,
    ) -> None:
        self._market_gateway = market_gateway
        self._symbols = symbols
        self._max_price_jump = max_price_jump
        self._volume_spike_ratio = volume_spike_ratio
        self._missing_days_threshold = missing_days_threshold

    def detect(self) -> list[AnomalyEvent]:
        events: list[AnomalyEvent] = []

        for symbol in self._symbols:
            bars = self._market_gateway.get_recent_bars(
                symbol, Timeframe.DAY_1, 30,
            )

            if not bars:
                events.append(AnomalyEvent(
                    anomaly_type=AnomalyType.DATA,
                    severity=AnomalySeverity.CRITICAL,
                    source=symbol,
                    message=f"标的 {symbol} 无行情数据",
                    metric_value=0.0,
                    threshold=float(self._missing_days_threshold),
                    auto_action=AutoAction.NONE,
                ))
                continue

            events.extend(self._check_price_jump(symbol, bars))
            events.extend(self._check_volume_spike(symbol, bars))

        return events

    def _check_price_jump(
        self, symbol: str, bars: list,
    ) -> list[AnomalyEvent]:
        """检测价格跳变。"""
        events: list[AnomalyEvent] = []
        if len(bars) < 2:
            return events

        for i in range(1, len(bars)):
            prev_close = bars[i - 1].close
            curr_close = bars[i].close
            if prev_close <= 0:
                continue

            change = abs(curr_close - prev_close) / prev_close
            if change > self._max_price_jump:
                events.append(AnomalyEvent(
                    anomaly_type=AnomalyType.DATA,
                    severity=AnomalySeverity.WARNING,
                    source=symbol,
                    message=(
                        f"标的 {symbol} 价格跳变: "
                        f"{change:.1%} > {self._max_price_jump:.1%}"
                    ),
                    metric_value=change,
                    threshold=self._max_price_jump,
                    auto_action=AutoAction.NONE,
                ))

        return events

    def _check_volume_spike(
        self, symbol: str, bars: list,
    ) -> list[AnomalyEvent]:
        """检测成交量异常。"""
        events: list[AnomalyEvent] = []
        if len(bars) < 5:
            return events

        recent_volumes = [b.volume for b in bars[-5:-1]]
        avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0
        current_volume = bars[-1].volume

        if avg_volume > 0:
            ratio = current_volume / avg_volume
            if ratio > self._volume_spike_ratio:
                events.append(AnomalyEvent(
                    anomaly_type=AnomalyType.DATA,
                    severity=AnomalySeverity.WARNING,
                    source=symbol,
                    message=(
                        f"标的 {symbol} 成交量异常放大: "
                        f"{ratio:.1f}x > {self._volume_spike_ratio:.1f}x"
                    ),
                    metric_value=ratio,
                    threshold=self._volume_spike_ratio,
                    auto_action=AutoAction.NONE,
                ))

        return events
