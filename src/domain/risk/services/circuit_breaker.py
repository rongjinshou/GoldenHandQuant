import logging
from datetime import datetime

from src.domain.account.entities.asset import Asset
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.domain.common.domain_event import DomainEvent
from src.domain.risk.value_objects.circuit_breaker_state import (
    BreakerStatus,
    CircuitBreakerState,
)
from src.domain.risk.value_objects.risk_event import (
    RiskEvent,
    RiskEventType,
    RiskSeverity,
)

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """风控熔断器。

    职责:
    1. 评估组合级风险指标（单日亏损、总回撤）
    2. 维护熔断状态（NORMAL -> TRIGGERED -> COOLDOWN -> NORMAL）
    3. 产出风控事件供通知系统消费

    生命周期:
    - 每个交易日开始时 reset_daily()
    - 盘中/盘后调用 evaluate() 检查风险
    - 触发后进入 TRIGGERED，禁止所有交易
    - 次日进入 COOLDOWN，仅允许卖出
    - 冷却期结束后恢复 NORMAL
    """

    def __init__(
        self,
        max_daily_loss: float = 0.03,
        max_total_drawdown: float = 0.20,
        cooldown_days: int = 1,
    ) -> None:
        self._max_daily_loss = max_daily_loss
        self._max_total_drawdown = max_total_drawdown
        self._cooldown_days = cooldown_days

        self._state = CircuitBreakerState()
        self._events: list[RiskEvent] = []
        self._initial_capital: float = 0.0
        self._day_open_asset: float = 0.0
        self._pending_domain_events: list[DomainEvent] = []

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    @property
    def events(self) -> list[RiskEvent]:
        return self._events

    def set_initial_capital(self, amount: float) -> None:
        """设置初始资金（回测开始时调用）。"""
        self._initial_capital = amount

    def reset_daily(self, current_date: datetime, day_open_asset: float) -> None:
        """每日盘前重置。

        Args:
            current_date: 当前日期。
            day_open_asset: 当日开盘时的总资产。
        """
        self._day_open_asset = day_open_asset
        self._events = []

        if self._state.status == BreakerStatus.TRIGGERED:
            self._state = CircuitBreakerState(
                status=BreakerStatus.COOLDOWN,
                triggered_at=self._state.triggered_at,
                trigger_reason=self._state.trigger_reason,
                daily_loss_rate=self._state.daily_loss_rate,
            )
            self._emit_domain_event("CircuitBreakerCooldownEntered", {
                "trigger_reason": self._state.trigger_reason,
            })
        elif self._state.status == BreakerStatus.COOLDOWN:
            self._state = CircuitBreakerState(status=BreakerStatus.NORMAL)
            self._events.append(RiskEvent(
                event_type=RiskEventType.CIRCUIT_BREAKER_OFF,
                severity=RiskSeverity.INFO,
                message="Circuit breaker recovered, trading resumed.",
            ))
            self._emit_domain_event("CircuitBreakerRecovered", {})

    def evaluate(
        self,
        current_asset: Asset,
        snapshots: list[DailySnapshot],
    ) -> CircuitBreakerState:
        """评估当前风险状态。

        Args:
            current_asset: 当前账户资产。
            snapshots: 历史快照列表。

        Returns:
            当前熔断器状态。
        """
        if self._state.status != BreakerStatus.NORMAL:
            return self._state

        # 检查 1: 单日亏损
        if self._day_open_asset > 0:
            daily_pnl = current_asset.total_asset - self._day_open_asset
            daily_loss_rate = -daily_pnl / self._day_open_asset
            if daily_loss_rate > self._max_daily_loss:
                self._trigger(
                    reason=f"Daily loss {daily_loss_rate:.2%} exceeds limit {self._max_daily_loss:.2%}",
                    daily_loss_rate=daily_loss_rate,
                )
                return self._state
        else:
            # confirmed-bug(2026-07-05): reset_daily() 未调用(或传了非正值)时哨兵值
            # 会让本道检查静默跳过——熔断器看似 NORMAL, 实则没做任何单日亏损评估。
            logger.warning(
                "CircuitBreaker.evaluate() 跳过单日亏损检查: day_open_asset=%.2f 非正, "
                "reset_daily() 可能尚未调用", self._day_open_asset,
            )

        # 检查 2: 总回撤
        if snapshots and self._initial_capital > 0:
            peak = self._initial_capital
            for s in snapshots:
                if s.total_asset > peak:
                    peak = s.total_asset
            current_dd = (peak - current_asset.total_asset) / peak if peak > 0 else 0
            if current_dd > self._max_total_drawdown:
                self._trigger(
                    reason=f"Total drawdown {current_dd:.2%} exceeds limit {self._max_total_drawdown:.2%}",
                )
                return self._state
        elif snapshots and self._initial_capital <= 0:
            logger.warning(
                "CircuitBreaker.evaluate() 跳过总回撤检查: initial_capital=%.2f 非正, "
                "set_initial_capital() 可能尚未调用", self._initial_capital,
            )

        return self._state

    def _trigger(self, reason: str, daily_loss_rate: float = 0.0) -> None:
        """触发熔断。"""
        now = datetime.now()
        self._state = CircuitBreakerState(
            status=BreakerStatus.TRIGGERED,
            triggered_at=now,
            trigger_reason=reason,
            daily_loss_rate=daily_loss_rate,
        )
        self._events.append(RiskEvent(
            event_type=RiskEventType.CIRCUIT_BREAKER_ON,
            severity=RiskSeverity.CRITICAL,
            message=f"CIRCUIT BREAKER TRIGGERED: {reason}",
        ))
        self._emit_domain_event("CircuitBreakerTriggered", {
            "reason": reason,
            "daily_loss_rate": daily_loss_rate,
        })

    def collect_pending_events(self) -> list[DomainEvent]:
        """收集并清空待发布的领域事件。

        Returns:
            本实体自上次收集以来产出的全部领域事件。
        """
        events = list(self._pending_domain_events)
        self._pending_domain_events.clear()
        return events

    def _emit_domain_event(self, event_type: str, payload: dict[str, object]) -> None:
        """内部方法：记录领域事件。"""
        self._pending_domain_events.append(DomainEvent(
            event_type=event_type,
            aggregate_id="circuit_breaker",
            aggregate_type="CircuitBreaker",
            payload=payload,
        ))
