"""实时风控监控服务。

职责：
1. Tick 级别价格监控（涨跌幅、波动率）
2. 实时止损检查
3. 异常成交检测（量价背离、流动性异常）
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.risk.value_objects.risk_alert import (
    RiskAlert,
    RiskAlertAction,
    RiskAlertSeverity,
    RiskAlertType,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class TickData:
    """Tick 行情数据（简化版）。"""
    symbol: str
    price: float
    volume: int
    timestamp: datetime = field(default_factory=datetime.now)
    bid_price: float = 0.0
    ask_price: float = 0.0
    pre_close: float = 0.0


@dataclass(slots=True, kw_only=True)
class PriceTracker:
    """单品种价格跟踪器。"""
    symbol: str
    last_price: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)
    recent_prices: list[float] = field(default_factory=list)
    tick_count: int = 0

    # 异常检测阈值
    max_price_change_pct: float = 0.05   # 单 Tick 最大变动 5%
    max_rapid_drop_pct: float = 0.03     # 连续下跌 3%
    rapid_drop_window: int = 10          # 连续下跌检测窗口（tick 数）

    def update(self, price: float, timestamp: datetime) -> None:
        """更新价格。"""
        self.last_price = price
        self.last_update = timestamp
        self.recent_prices.append(price)
        if len(self.recent_prices) > self.rapid_drop_window:
            self.recent_prices = self.recent_prices[-self.rapid_drop_window:]
        self.tick_count += 1


class RealtimeRiskMonitor:
    """实时风控监控器。

    对每个 Tick 进行风险检查，产出告警事件。
    设计为轻量级，不阻塞主交易循环。
    """

    def __init__(
        self,
        max_price_change_pct: float = 0.05,
        max_rapid_drop_pct: float = 0.03,
        rapid_drop_window: int = 10,
        max_spread_pct: float = 0.02,
        max_volume_spike_ratio: float = 5.0,
    ) -> None:
        self._max_price_change_pct = max_price_change_pct
        self._max_rapid_drop_pct = max_rapid_drop_pct
        self._rapid_drop_window = rapid_drop_window
        self._max_spread_pct = max_spread_pct
        self._max_volume_spike_ratio = max_volume_spike_ratio

        self._trackers: dict[str, PriceTracker] = {}
        self._avg_volumes: dict[str, float] = {}  # 历史平均成交量
        self._pending_alerts: list[RiskAlert] = []

    @property
    def pending_alerts(self) -> list[RiskAlert]:
        """获取待处理告警。"""
        return list(self._pending_alerts)

    def collect_alerts(self) -> list[RiskAlert]:
        """收集并清空待处理告警。"""
        alerts = list(self._pending_alerts)
        self._pending_alerts.clear()
        return alerts

    def on_tick(self, tick: TickData) -> list[RiskAlert]:
        """处理 Tick 数据，返回本轮告警。

        Args:
            tick: Tick 行情数据。

        Returns:
            本轮检测到的告警列表。
        """
        alerts: list[RiskAlert] = []

        # 获取或创建 tracker
        tracker = self._get_or_create_tracker(tick.symbol, tick.price)

        # 1. 单 Tick 价格异常检查
        if tracker.last_price > 0 and tracker.tick_count > 0:
            alerts.extend(self._check_price_change(tracker, tick))

        # 2. 买卖价差异常检查
        if tick.bid_price > 0 and tick.ask_price > 0:
            spread_alert = self._check_spread(tick)
            if spread_alert:
                alerts.append(spread_alert)

        # 3. 成交量异常检查
        volume_alert = self._check_volume_spike(tick)
        if volume_alert:
            alerts.append(volume_alert)

        # 4. 连续下跌检查
        if len(tracker.recent_prices) >= self._rapid_drop_window:
            drop_alert = self._check_rapid_drop(tracker, tick)
            if drop_alert:
                alerts.append(drop_alert)

        # 更新 tracker
        tracker.update(tick.price, tick.timestamp)

        # 缓存告警（供 collect_alerts 历史查询）
        self._pending_alerts.extend(alerts)

        return alerts

    def get_tracker(self, symbol: str) -> PriceTracker | None:
        """获取指定品种的价格跟踪器。"""
        return self._trackers.get(symbol)

    def _get_or_create_tracker(self, symbol: str, price: float) -> PriceTracker:
        """获取或创建价格跟踪器。"""
        if symbol not in self._trackers:
            self._trackers[symbol] = PriceTracker(
                symbol=symbol,
                last_price=price,
                max_price_change_pct=self._max_price_change_pct,
                max_rapid_drop_pct=self._max_rapid_drop_pct,
                rapid_drop_window=self._rapid_drop_window,
            )
        return self._trackers[symbol]

    def _check_price_change(self, tracker: PriceTracker, tick: TickData) -> list[RiskAlert]:
        """检查单 Tick 价格异常变动。"""
        alerts: list[RiskAlert] = []
        change_pct = abs(tick.price - tracker.last_price) / tracker.last_price

        if change_pct > self._max_price_change_pct:
            alert = RiskAlert(
                alert_type=RiskAlertType.PRICE_ANOMALY,
                severity=RiskAlertSeverity.CRITICAL,
                symbol=tick.symbol,
                message=(
                    f"价格异常变动: {tracker.last_price:.2f} -> {tick.price:.2f} "
                    f"({change_pct:.2%})"
                ),
                timestamp=tick.timestamp,
                action_required=RiskAlertAction.PAUSE_TRADING,
                current_price=tick.price,
                reference_price=tracker.last_price,
            )
            alerts.append(alert)

        # A 股涨跌停检查（10%）
        if tick.pre_close > 0:
            limit_pct = (tick.price - tick.pre_close) / tick.pre_close
            if abs(limit_pct) >= 0.098:  # 接近涨跌停
                alert = RiskAlert(
                    alert_type=RiskAlertType.PRICE_ANOMALY,
                    severity=RiskAlertSeverity.WARNING,
                    symbol=tick.symbol,
                    message=f"接近涨跌停: 当前 {tick.price:.2f}, 涨跌幅 {limit_pct:.2%}",
                    timestamp=tick.timestamp,
                    action_required=RiskAlertAction.NOTIFY,
                    current_price=tick.price,
                    reference_price=tick.pre_close,
                )
                alerts.append(alert)

        return alerts

    def _check_spread(self, tick: TickData) -> RiskAlert | None:
        """检查买卖价差异常。"""
        if tick.ask_price <= 0:
            return None
        spread_pct = (tick.ask_price - tick.bid_price) / tick.ask_price

        if spread_pct > self._max_spread_pct:
            return RiskAlert(
                alert_type=RiskAlertType.WIDE_SPREAD,
                severity=RiskAlertSeverity.WARNING,
                symbol=tick.symbol,
                message=f"买卖价差异常: {tick.bid_price:.2f}/{tick.ask_price:.2f} ({spread_pct:.2%})",
                timestamp=tick.timestamp,
                action_required=RiskAlertAction.NOTIFY,
                current_price=tick.price,
            )
        return None

    def _check_volume_spike(self, tick: TickData) -> RiskAlert | None:
        """检查成交量异常放大。"""
        avg_vol = self._avg_volumes.get(tick.symbol)
        if avg_vol is None or avg_vol <= 0:
            # 首次记录，设为基准
            self._avg_volumes[tick.symbol] = float(tick.volume)
            return None

        if tick.volume > avg_vol * self._max_volume_spike_ratio:
            return RiskAlert(
                alert_type=RiskAlertType.VOLUME_ANOMALY,
                severity=RiskAlertSeverity.WARNING,
                symbol=tick.symbol,
                message=f"成交量异常放大: {tick.volume} (均值 {avg_vol:.0f})",
                timestamp=tick.timestamp,
                action_required=RiskAlertAction.NOTIFY,
                current_price=tick.price,
            )

        # 更新移动平均（简单指数平均）
        self._avg_volumes[tick.symbol] = avg_vol * 0.95 + tick.volume * 0.05
        return None

    def _check_rapid_drop(self, tracker: PriceTracker, tick: TickData) -> RiskAlert | None:
        """检查连续下跌。"""
        prices = tracker.recent_prices
        if len(prices) < 2:
            return None

        # 计算窗口内跌幅
        window_high = max(prices)
        current_drop = (window_high - tick.price) / window_high if window_high > 0 else 0

        if current_drop > self._max_rapid_drop_pct:
            return RiskAlert(
                alert_type=RiskAlertType.RAPID_DROP,
                severity=RiskAlertSeverity.CRITICAL,
                symbol=tick.symbol,
                message=(
                    f"连续下跌: 窗口高点 {window_high:.2f} -> "
                    f"当前 {tick.price:.2f} ({current_drop:.2%})"
                ),
                timestamp=tick.timestamp,
                action_required=RiskAlertAction.CLOSE_POSITION,
                current_price=tick.price,
                reference_price=window_high,
                loss_rate=current_drop,
            )
        return None
