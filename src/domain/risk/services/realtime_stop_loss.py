"""实时止损服务。

职责：
1. 跟踪持仓价格变化
2. 固定止损 / 移动止损检查
3. 触发止损时产出告警和止损信号
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from src.domain.risk.value_objects.risk_alert import (
    RiskAlert,
    RiskAlertAction,
    RiskAlertSeverity,
    RiskAlertType,
)

logger = logging.getLogger(__name__)


class StopLossType(StrEnum):
    """止损类型。"""
    FIXED = "fixed"          # 固定止损价
    PERCENTAGE = "percentage" # 百分比止损
    TRAILING = "trailing"     # 移动止损


@dataclass(slots=True, kw_only=True)
class StopLossRule:
    """止损规则。"""
    symbol: str
    stop_loss_type: StopLossType
    stop_price: float = 0.0           # 固定止损价（FIXED 类型使用）
    stop_pct: float = 0.05            # 止损百分比（PERCENTAGE/TRAILING 使用）
    cost_price: float = 0.0           # 持仓成本价
    highest_price: float = 0.0        # 持仓期间最高价（TRAILING 使用）
    volume: int = 0                   # 持仓数量
    enabled: bool = True


@dataclass(slots=True, kw_only=True)
class StopLossTrigger:
    """止损触发结果。"""
    symbol: str
    trigger_price: float
    stop_price: float
    loss_rate: float
    volume: int
    stop_type: StopLossType
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


class RealtimeStopLossService:
    """实时止损服务。

    管理多个品种的止损规则，每次价格更新时检查是否触发止损。
    触发时返回 StopLossTrigger，由上层决定是否自动下单。
    """

    def __init__(self) -> None:
        self._rules: dict[str, StopLossRule] = {}
        self._triggers: list[StopLossTrigger] = []
        self._pending_alerts: list[RiskAlert] = []

    @property
    def rules(self) -> dict[str, StopLossRule]:
        """当前止损规则。"""
        return dict(self._rules)

    @property
    def pending_alerts(self) -> list[RiskAlert]:
        """待处理告警。"""
        return list(self._pending_alerts)

    def collect_alerts(self) -> list[RiskAlert]:
        """收集并清空待处理告警。"""
        alerts = list(self._pending_alerts)
        self._pending_alerts.clear()
        return alerts

    def collect_triggers(self) -> list[StopLossTrigger]:
        """收集并清空止损触发记录。"""
        triggers = list(self._triggers)
        self._triggers.clear()
        return triggers

    def set_fixed_stop(self, symbol: str, stop_price: float, cost_price: float, volume: int) -> None:
        """设置固定止损。"""
        self._rules[symbol] = StopLossRule(
            symbol=symbol,
            stop_loss_type=StopLossType.FIXED,
            stop_price=stop_price,
            cost_price=cost_price,
            volume=volume,
        )

    def set_percentage_stop(self, symbol: str, cost_price: float, stop_pct: float, volume: int) -> None:
        """设置百分比止损。"""
        stop_price = cost_price * (1 - stop_pct)
        self._rules[symbol] = StopLossRule(
            symbol=symbol,
            stop_loss_type=StopLossType.PERCENTAGE,
            stop_price=stop_price,
            stop_pct=stop_pct,
            cost_price=cost_price,
            volume=volume,
        )

    def set_trailing_stop(self, symbol: str, current_price: float, stop_pct: float, volume: int) -> None:
        """设置移动止损。"""
        stop_price = current_price * (1 - stop_pct)
        self._rules[symbol] = StopLossRule(
            symbol=symbol,
            stop_loss_type=StopLossType.TRAILING,
            stop_price=stop_price,
            stop_pct=stop_pct,
            cost_price=current_price,
            highest_price=current_price,
            volume=volume,
        )

    def remove_rule(self, symbol: str) -> None:
        """移除止损规则。"""
        self._rules.pop(symbol, None)

    def on_price_update(self, symbol: str, price: float, timestamp: datetime | None = None) -> StopLossTrigger | None:
        """价格更新时检查止损。

        Args:
            symbol: 证券代码。
            price: 当前价格。
            timestamp: 时间戳。

        Returns:
            如果触发止损，返回 StopLossTrigger；否则返回 None。
        """
        rule = self._rules.get(symbol)
        if rule is None or not rule.enabled:
            return None

        now = timestamp or datetime.now()

        # 移动止损：更新最高价和止损价
        if rule.stop_loss_type == StopLossType.TRAILING:
            if price > rule.highest_price:
                rule.highest_price = price
                rule.stop_price = price * (1 - rule.stop_pct)

        # 检查是否触发
        if price <= rule.stop_price:
            return self._trigger_stop(rule, price, now)

        return None

    def _trigger_stop(self, rule: StopLossRule, price: float, timestamp: datetime) -> StopLossTrigger:
        """触发止损。"""
        loss_rate = (price - rule.cost_price) / rule.cost_price if rule.cost_price > 0 else 0

        trigger = StopLossTrigger(
            symbol=rule.symbol,
            trigger_price=price,
            stop_price=rule.stop_price,
            loss_rate=loss_rate,
            volume=rule.volume,
            stop_type=rule.stop_loss_type,
            message=(
                f"止损触发 [{rule.stop_loss_type.value}]: {rule.symbol} "
                f"当前 {price:.2f} <= 止损价 {rule.stop_price:.2f}, "
                f"亏损 {loss_rate:.2%}"
            ),
            timestamp=timestamp,
        )

        self._triggers.append(trigger)

        # 产出告警
        alert = RiskAlert(
            alert_type=(
                RiskAlertType.TRAILING_STOP
                if rule.stop_loss_type == StopLossType.TRAILING
                else RiskAlertType.STOP_LOSS
            ),
            severity=RiskAlertSeverity.CRITICAL,
            symbol=rule.symbol,
            message=trigger.message,
            timestamp=timestamp,
            action_required=RiskAlertAction.CLOSE_POSITION,
            current_price=price,
            reference_price=rule.stop_price,
            loss_rate=loss_rate,
        )
        self._pending_alerts.append(alert)

        # 禁用规则（避免重复触发）
        rule.enabled = False

        logger.warning("止损触发: %s", trigger.message)

        return trigger
