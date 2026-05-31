from datetime import datetime

from src.domain.account.entities.asset import Asset
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.domain.risk.value_objects.circuit_breaker_state import (
    BreakerStatus,
    CircuitBreakerState,
)
from src.domain.risk.value_objects.risk_event import (
    RiskEvent,
    RiskEventType,
    RiskSeverity,
)


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
        elif self._state.status == BreakerStatus.COOLDOWN:
            self._state = CircuitBreakerState(status=BreakerStatus.NORMAL)
            self._events.append(RiskEvent(
                event_type=RiskEventType.CIRCUIT_BREAKER_OFF,
                severity=RiskSeverity.INFO,
                message="Circuit breaker recovered, trading resumed.",
            ))

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
