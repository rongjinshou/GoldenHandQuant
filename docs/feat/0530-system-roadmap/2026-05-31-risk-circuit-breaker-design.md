# 风控熔断机制 设计文档

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 详细设计 / 技术方案
**状态**: 草案
**所属阶段**: Phase 2（半自动交易）- 子项目 2.3

---

## 一、背景与动机

### 1.1 问题陈述

自动化交易的前提是有可靠的风控。当前系统已具备部分风控能力，但存在关键缺口：

- **已有能力**：单标的止损（`HardStopLossPolicy`）、回撤检测（`DrawdownPolicy`）、仓位上限（`PositionLimitPolicy`）、指数级门禁（`SystemRiskGate`）
- **核心缺失**：**组合级单日亏损熔断** -- 当单日亏损超过阈值时，自动停止所有交易并通知用户

用户需求原话：> "当单日亏损超过 3% 时自动停止交易并通知。"

### 1.2 现有代码分析

| 组件 | 位置 | 职责 | 状态 |
|------|------|------|------|
| `BaseRiskPolicy` | `src/domain/risk/services/base_risk_policy.py` | 订单级风控接口 | 可复用 |
| `BaseRiskSignalPolicy` | `src/domain/risk/services/base_risk_signal_policy.py` | 盘后信号级风控接口 | 可复用 |
| `RiskChain` | `src/domain/risk/services/risk_chain.py` | 订单级责任链 | 可扩展 |
| `RiskSignalGenerator` | `src/domain/risk/services/risk_signal_generator.py` | 盘后信号聚合器 | 可扩展 |
| `SystemRiskGate` | `src/domain/risk/services/system_risk_gate.py` | 盘前指数门禁 | 可复用 |
| `RiskCheckResult` | `src/domain/risk/value_objects/risk_check_result.py` | 风控结果值对象 | 可复用 |
| `RiskSettings` | `src/infrastructure/config/settings.py` | 风控配置 | 需扩展 |
| `CrossSectionalStrategyRunner` | `src/application/strategy_runner.py` | 策略执行器（已集成风控） | 需扩展 |

**现有集成点**（`CrossSectionalStrategyRunner.evaluate`）：
1. 盘前：`SystemRiskGate.check_gate()` 判定是否允许买入
2. 盘中：`RiskSignalGenerator` 产出止损/破板卖出信号
3. 信号过滤：`gate.pass_buy == False` 时移除所有 BUY 信号

**缺失的集成点**：
- 没有"当日组合级亏损"的检测
- 没有"熔断后停止所有交易（含卖出）"的机制
- 没有熔断状态管理和恢复流程
- 没有通知机制

---

## 二、总体设计

### 2.1 设计原则

1. **Domain 红线**：风控核心逻辑在 `src/domain/risk/` 下，不引入第三方依赖
2. **配置驱动**：所有阈值通过 YAML 配置，运行时可调整
3. **最小侵入**：扩展现有接口，不修改已有策略的签名
4. **分层职责**：Domain 定义规则和状态，Application 编排流程，Infrastructure 实现通知

### 2.2 架构概览

```
src/domain/risk/
├── value_objects/
│   ├── risk_check_result.py          # 已有
│   ├── circuit_breaker_state.py      # 新增: 熔断状态值对象
│   └── risk_event.py                 # 新增: 风控事件值对象
├── services/
│   ├── base_risk_policy.py           # 已有
│   ├── base_risk_signal_policy.py    # 已有
│   ├── risk_chain.py                 # 已有
│   ├── risk_signal_generator.py      # 已有
│   ├── system_risk_gate.py           # 已有
│   ├── circuit_breaker.py            # 新增: 熔断器核心
│   └── risk_policies/
│       ├── drawdown_policy.py        # 已有
│       ├── hard_stop_loss_policy.py  # 已有
│       ├── limit_up_break_policy.py  # 已有
│       ├── position_limit_policy.py  # 已有
│       ├── simple_risk_policy.py     # 已有
│       ├── daily_loss_policy.py      # 新增: 单日亏损熔断
│       └── total_position_policy.py  # 新增: 总仓位上限
└── interfaces/
    └── notification.py               # 新增: 通知接口 (Protocol)

src/infrastructure/
├── notification/
│   ├── console_notifier.py           # 新增: 终端通知
│   ├── wechat_notifier.py            # 新增: 微信通知 (企业微信 webhook)
│   └── email_notifier.py             # 新增: 邮件通知
└── config/
    └── settings.py                   # 扩展 RiskSettings
```

---

## 三、核心组件设计

### 3.1 熔断状态值对象

**文件**: `src/domain/risk/value_objects/circuit_breaker_state.py`

```python
from dataclasses import dataclass
from enum import StrEnum
from datetime import datetime


class BreakerStatus(StrEnum):
    """熔断器状态。"""
    NORMAL = "NORMAL"           # 正常运行
    TRIGGERED = "TRIGGERED"     # 已触发熔断，禁止所有交易
    COOLDOWN = "COOLDOWN"       # 冷却期，仅允许卖出


@dataclass(slots=True, kw_only=True)
class CircuitBreakerState:
    """熔断器状态值对象。

    Attributes:
        status: 当前状态。
        triggered_at: 触发时间。
        trigger_reason: 触发原因。
        daily_loss_rate: 当日亏损率。
        resume_at: 预计恢复时间（冷却期结束后）。
    """
    status: BreakerStatus = BreakerStatus.NORMAL
    triggered_at: datetime | None = None
    trigger_reason: str = ""
    daily_loss_rate: float = 0.0
    resume_at: datetime | None = None

    @property
    def is_normal(self) -> bool:
        return self.status == BreakerStatus.NORMAL

    @property
    def blocks_all_trading(self) -> bool:
        """TRIGGERED 状态禁止所有交易。"""
        return self.status == BreakerStatus.TRIGGERED

    @property
    def allows_sell_only(self) -> bool:
        """COOLDOWN 状态仅允许卖出。"""
        return self.status == BreakerStatus.COOLDOWN
```

### 3.2 风控事件值对象

**文件**: `src/domain/risk/value_objects/risk_event.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class RiskEventType(StrEnum):
    """风控事件类型。"""
    DAILY_LOSS_BREACH = "DAILY_LOSS_BREACH"         # 单日亏损超限
    DRAWDOWN_BREACH = "DRAWDOWN_BREACH"             # 总回撤超限
    POSITION_LIMIT_BREACH = "POSITION_LIMIT_BREACH" # 仓位超限
    STOP_LOSS_TRIGGERED = "STOP_LOSS_TRIGGERED"     # 个股止损触发
    CIRCUIT_BREAKER_ON = "CIRCUIT_BREAKER_ON"       # 熔断器开启
    CIRCUIT_BREAKER_OFF = "CIRCUIT_BREAKER_OFF"     # 熔断器恢复
    ANOMALY_DETECTED = "ANOMALY_DETECTED"           # 异常检测


class RiskSeverity(StrEnum):
    """风控事件严重级别。"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(slots=True, kw_only=True)
class RiskEvent:
    """风控事件。"""
    event_type: RiskEventType
    severity: RiskSeverity
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
```

### 3.3 熔断器核心

**文件**: `src/domain/risk/services/circuit_breaker.py`

熔断器是整个风控系统的核心协调者。它聚合多个风险检测策略，维护熔断状态，并在状态变化时产出事件。

```python
from datetime import datetime, timedelta

from src.domain.risk.value_objects.circuit_breaker_state import (
    BreakerStatus, CircuitBreakerState,
)
from src.domain.risk.value_objects.risk_event import (
    RiskEvent, RiskEventType, RiskSeverity,
)
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar


class CircuitBreaker:
    """风控熔断器。

    职责:
    1. 评估组合级风险指标（单日亏损、总回撤、总仓位）
    2. 维护熔断状态（NORMAL → TRIGGERED → COOLDOWN → NORMAL）
    3. 产出风控事件供通知系统消费

    生命周期:
    - 每个交易日开始时 reset_daily()
    - 盘中每次调用 evaluate() 检查风险
    - 触发后进入 TRIGGERED，禁止所有交易
    - 次日进入 COOLDOWN，仅允许卖出
    - 冷却期结束后恢复 NORMAL
    """

    def __init__(
        self,
        max_daily_loss: float = 0.03,
        max_total_drawdown: float = 0.20,
        max_total_position_ratio: float = 0.80,
        cooldown_days: int = 1,
    ) -> None:
        self._max_daily_loss = max_daily_loss
        self._max_total_drawdown = max_total_drawdown
        self._max_total_position_ratio = max_total_position_ratio
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

        # 状态机转换
        if self._state.status == BreakerStatus.TRIGGERED:
            # 熔断次日进入冷却期
            self._state = CircuitBreakerState(
                status=BreakerStatus.COOLDOWN,
                triggered_at=self._state.triggered_at,
                trigger_reason=self._state.trigger_reason,
                daily_loss_rate=self._state.daily_loss_rate,
            )
        elif self._state.status == BreakerStatus.COOLDOWN:
            # 冷却期结束，恢复正常
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
        # 已经在熔断/冷却中，不重复触发
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
```

### 3.4 单日亏损策略（订单级）

**文件**: `src/domain/risk/services/risk_policies/daily_loss_policy.py`

与 `CircuitBreaker` 配合，在订单级拦截买入操作。

```python
from src.domain.account.entities.asset import Asset
from src.domain.risk.services.base_risk_policy import BaseRiskPolicy
from src.domain.risk.value_objects.risk_check_result import RiskCheckResult
from src.domain.risk.services.circuit_breaker import CircuitBreaker
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection


class DailyLossPolicy(BaseRiskPolicy):
    """单日亏损订单级策略。

    当熔断器状态非 NORMAL 时，拒绝非卖出订单。
    """

    def __init__(self, circuit_breaker: CircuitBreaker) -> None:
        self._breaker = circuit_breaker

    def check(self, order: Order) -> RiskCheckResult:
        state = self._breaker.state

        if state.blocks_all_trading:
            return RiskCheckResult.reject(
                f"Circuit breaker active: {state.trigger_reason}"
            )

        if state.allows_sell_only and order.direction == OrderDirection.BUY:
            return RiskCheckResult.reject(
                f"Cooldown period, sell-only: {state.trigger_reason}"
            )

        return RiskCheckResult.pass_check()
```

### 3.5 总仓位上限策略

**文件**: `src/domain/risk/services/risk_policies/total_position_policy.py`

```python
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.risk.services.base_risk_policy import BaseRiskPolicy
from src.domain.risk.value_objects.risk_check_result import RiskCheckResult
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection


class TotalPositionPolicy(BaseRiskPolicy):
    """总仓位上限策略。

    当总持仓市值占总资产比例超过阈值时，拒绝新增买入。
    """

    def __init__(
        self,
        positions: list[Position],
        asset: Asset,
        current_prices: dict[str, float],
        max_ratio: float = 0.80,
    ) -> None:
        self._positions = positions
        self._asset = asset
        self._current_prices = current_prices
        self._max_ratio = max_ratio

    def check(self, order: Order) -> RiskCheckResult:
        if order.direction != OrderDirection.BUY:
            return RiskCheckResult.pass_check()

        market_value = sum(
            p.total_volume * self._current_prices.get(p.ticker, p.average_cost)
            for p in self._positions
        )
        # 加上新订单的金额
        new_value = market_value + order.price * order.volume
        ratio = new_value / self._asset.total_asset if self._asset.total_asset > 0 else 0

        if ratio > self._max_ratio:
            return RiskCheckResult.reject(
                f"Total position {ratio:.2%} exceeds limit {self._max_ratio:.2%}"
            )
        return RiskCheckResult.pass_check()
```

### 3.6 通知接口与实现

**接口** (`src/domain/risk/interfaces/notification.py`):

```python
from typing import Protocol
from src.domain.risk.value_objects.risk_event import RiskEvent


class IRiskNotifier(Protocol):
    """风控通知接口。"""

    def notify(self, event: RiskEvent) -> None:
        """发送风控通知。"""
        ...
```

**终端通知** (`src/infrastructure/notification/console_notifier.py`):

```python
from src.domain.risk.value_objects.risk_event import RiskEvent, RiskSeverity


class ConsoleNotifier:
    """终端通知实现。"""

    _SEVERITY_COLORS = {
        RiskSeverity.INFO: "\033[94m",      # Blue
        RiskSeverity.WARNING: "\033[93m",   # Yellow
        RiskSeverity.CRITICAL: "\033[91m",  # Red
    }
    _RESET = "\033[0m"

    def notify(self, event: RiskEvent) -> None:
        color = self._SEVERITY_COLORS.get(event.severity, "")
        print(f"{color}[RISK {event.severity}] {event.message}{self._RESET}")
```

**企业微信 Webhook** (`src/infrastructure/notification/wechat_notifier.py`):

```python
import json
import urllib.request
from src.domain.risk.value_objects.risk_event import RiskEvent, RiskSeverity


class WeChatNotifier:
    """企业微信 Webhook 通知。"""

    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    def notify(self, event: RiskEvent) -> None:
        emoji = {
            RiskSeverity.INFO: "[INFO]",
            RiskSeverity.WARNING: "[WARN]",
            RiskSeverity.CRITICAL: "[ALERT]",
        }
        payload = {
            "msgtype": "text",
            "text": {
                "content": f"{emoji.get(event.severity, '')} {event.message}"
            },
        }
        req = urllib.request.Request(
            self._url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # 通知失败不应影响交易
```

### 3.7 风险事件分发器

**文件**: `src/domain/risk/services/risk_event_dispatcher.py`

```python
from src.domain.risk.interfaces.notification import IRiskNotifier
from src.domain.risk.value_objects.risk_event import RiskEvent


class RiskEventDispatcher:
    """风控事件分发器。

    将风控事件广播给所有已注册的通知器。
    """

    def __init__(self) -> None:
        self._notifiers: list[IRiskNotifier] = []

    def add_notifier(self, notifier: IRiskNotifier) -> None:
        self._notifiers.append(notifier)

    def dispatch(self, event: RiskEvent) -> None:
        for notifier in self._notifiers:
            notifier.notify(event)

    def dispatch_all(self, events: list[RiskEvent]) -> None:
        for event in events:
            self.dispatch(event)
```

---

## 四、熔断状态机

### 4.1 状态转换图

```
                    evaluate() 触发
    NORMAL ─────────────────────────────→ TRIGGERED
      ↑                                    │
      │  cooldown_days 结束                 │ 次日 reset_daily()
      │                                    ↓
      └────────────────────────────── COOLDOWN
           (仅允许卖出)
```

### 4.2 状态行为

| 状态 | BUY 订单 | SELL 订单 | 触发条件 |
|------|---------|----------|---------|
| NORMAL | 允许 | 允许 | -- |
| TRIGGERED | 拒绝 | 拒绝 | 单日亏损 > max_daily_loss 或总回撤 > max_total_drawdown |
| COOLDOWN | 拒绝 | 允许 | TRIGGERED 次日自动转入 |

### 4.3 关键时序

```
Day 1 (正常):
  09:15  reset_daily() → NORMAL
  09:30  evaluate() → NORMAL, 允许交易
  14:00  evaluate() → 发现当日亏损 3.5% > 3%
         → TRIGGERED, 拒绝后续所有订单
         → dispatch CIRCUIT_BREAKER_ON 事件

Day 2 (冷却):
  09:15  reset_daily() → COOLDOWN (TRIGGERED 次日)
  09:30  允许卖出, 拒绝买入
  15:00  日终

Day 3 (恢复):
  09:15  reset_daily() → NORMAL (COOLDOWN 结束)
         → dispatch CIRCUIT_BREAKER_OFF 事件
  09:30  正常交易
```

---

## 五、配置设计

### 5.1 YAML 配置结构

```yaml
# resources/backtest.yaml 或 resources/live_trade.yaml
risk:
  system_gate:
    index_symbol: "000852.SH"
  stop_loss:
    max_loss_ratio: 0.03
  circuit_breaker:
    enabled: true
    max_daily_loss: 0.03        # 单日亏损熔断阈值
    max_total_drawdown: 0.20    # 总回撤熔断阈值
    max_total_position: 0.80    # 总仓位上限
    cooldown_days: 1            # 冷却天数
  notification:
    console: true
    wechat:
      enabled: false
      webhook_url: ""
    email:
      enabled: false
      smtp_host: ""
      smtp_port: 465
      sender: ""
      password: ""
      receivers: []
```

### 5.2 Settings 扩展

```python
@dataclass(slots=True, kw_only=True)
class CircuitBreakerSettings:
    enabled: bool = True
    max_daily_loss: float = 0.03
    max_total_drawdown: float = 0.20
    max_total_position: float = 0.80
    cooldown_days: int = 1


@dataclass(slots=True, kw_only=True)
class WeChatNotificationSettings:
    enabled: bool = False
    webhook_url: str = ""


@dataclass(slots=True, kw_only=True)
class EmailNotificationSettings:
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 465
    sender: str = ""
    password: str = ""
    receivers: list[str] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class NotificationSettings:
    console: bool = True
    wechat: WeChatNotificationSettings = field(default_factory=WeChatNotificationSettings)
    email: EmailNotificationSettings = field(default_factory=EmailNotificationSettings)


@dataclass(slots=True, kw_only=True)
class RiskSettings:
    system_gate: SystemGateSettings = field(default_factory=SystemGateSettings)
    stop_loss: StopLossSettings = field(default_factory=StopLossSettings)
    circuit_breaker: CircuitBreakerSettings = field(default_factory=CircuitBreakerSettings)
    notification: NotificationSettings = field(default_factory=NotificationSettings)
    policies: list[str] = field(default_factory=list)
```

---

## 六、应用层集成

### 6.1 CrossSectionalStrategyRunner 集成点

当前 `CrossSectionalStrategyRunner.evaluate()` 的流程:

```
1. 获取指数数据 → SystemRiskGate
2. 获取个股行情
3. 策略生成信号
4. 风控信号生成（止损/破板）
5. SystemRiskGate 过滤 BUY 信号
6. PositionSizer 计算目标
```

**改造后流程**:

```
1. 获取指数数据 → SystemRiskGate
2. 获取个股行情
3. [NEW] CircuitBreaker.evaluate() 检查组合风险
4. [NEW] 如果 TRIGGERED → 清空所有信号，直接返回空 targets
5. [NEW] 如果 COOLDOWN → 移除 BUY 信号
6. 策略生成信号
7. 风控信号生成（止损/破板）
8. SystemRiskGate 过滤 BUY 信号
9. [NEW] DailyLossPolicy 订单级检查
10. PositionSizer 计算目标
```

### 6.2 BacktestAppService 集成点

在回测主循环中:

```
for current_time in valid_timestamps:
    # [NEW] 盘前重置熔断器
    circuit_breaker.reset_daily(current_time, day_open_asset)

    targets, close_prices = runner.evaluate(context)

    self._execute_targets(targets, current_time, account_id)
    self._settle_and_snapshot(current_time, close_prices)

    # [NEW] 盘后评估熔断器（基于最新快照）
    asset = self.trade_gateway.get_asset()
    circuit_breaker.evaluate(asset, self.snapshots)

    # [NEW] 分发风控事件
    dispatcher.dispatch_all(circuit_breaker.events)
```

### 6.3 SingleStrategyRunner 集成

`SingleStrategyRunner` 当前没有风控集成，需要:

1. 注入 `CircuitBreaker` 和 `RiskChain`
2. 在 `evaluate()` 中先检查熔断状态
3. 对生成的 targets 应用 `RiskChain.check()`

---

## 七、通知机制设计

### 7.1 通知级别与渠道

| 事件严重级别 | 终端 | 企业微信 | 邮件 |
|-------------|------|---------|------|
| INFO | 是 | 否 | 否 |
| WARNING | 是 | 是 | 否 |
| CRITICAL | 是 | 是 | 是 |

### 7.2 通知消息模板

**熔断触发** (CRITICAL):
```
[RISK ALERT] CIRCUIT BREAKER TRIGGERED
原因: 单日亏损 3.5% 超过阈值 3.0%
时间: 2026-05-31 14:00:00
操作: 所有交易已暂停，明日进入冷却期（仅允许卖出）
```

**熔断恢复** (INFO):
```
[RISK INFO] Circuit breaker recovered, trading resumed.
```

**个股止损** (WARNING):
```
[RISK WARNING] Stop loss triggered for 600000.SH: -3.2% < -3.0%
```

### 7.3 通知失败处理

- 通知失败**不阻塞**交易流程
- 失败时静默记录日志（`infrastructure/logging/`）
- 不重试（避免通知风暴）

---

## 八、异常检测（扩展能力）

### 8.1 策略信号异常

检测条件:
- 单次信号数量异常多（> 通常的 2 倍）
- 信号方向集中度异常（全部 BUY 或全部 SELL）
- 连续 N 天无信号

处理: 产出 `ANOMALY_DETECTED` 事件，级别 WARNING。

### 8.2 数据异常

检测条件:
- 行情数据缺失（某只股票无 Bar 数据）
- 价格跳变异常（日涨跌幅 > 15%，排除新股/复牌）
- 成交量为 0

处理: 跳过异常数据，产出 WARNING 事件。

### 8.3 实现位置

异常检测作为 `BaseRiskSignalPolicy` 的新实现:

```python
class AnomalyDetectionPolicy(BaseRiskSignalPolicy):
    """异常检测策略。"""
    ...
```

---

## 九、与未来阶段的关系

### 9.1 Phase 3 扩展点

- **组合 VaR**：在 `CircuitBreaker.evaluate()` 中增加 VaR 检查
- **策略级熔断**：每个策略有独立的熔断器
- **相关性熔断**：策略间相关性突然升高时触发

### 9.2 Phase 4 扩展点

- **ML 模型熔断**：模型预测准确率下降时自动停用
- **远程控制**：通过手机端手动触发/解除熔断
- **自动恢复策略**：根据市场状态自动调整熔断阈值

---

## 十、测试策略

### 10.1 单元测试

| 测试文件 | 测试对象 | 关键用例 |
|---------|---------|---------|
| `test_circuit_breaker.py` | `CircuitBreaker` | 状态机转换、阈值触发、冷却恢复 |
| `test_daily_loss_policy.py` | `DailyLossPolicy` | TRIGGERED 拒绝、COOLDOWN 仅卖 |
| `test_total_position_policy.py` | `TotalPositionPolicy` | 超限拒绝、卖出放行 |
| `test_risk_event_dispatcher.py` | `RiskEventDispatcher` | 多通知器分发 |

### 10.2 集成测试

- 回测场景：模拟单日亏损 3.5%，验证熔断触发和次日恢复
- 回测场景：模拟总回撤 25%，验证熔断触发
- 回测场景：冷却期内卖出正常执行

---

## 十一、设计决策记录

| 决策 | 理由 | 替代方案 |
|------|------|---------|
| 熔断器在 Domain 层 | 核心风控逻辑不含第三方依赖，符合 DDD 红线 | 放在 Application 层（被否决：职责不清） |
| 三状态状态机 | 简单明确，TRIGGERED 当日全禁、次日仅卖、再恢复 | 连续冷却多天（过度设计） |
| 通知接口用 Protocol | 与现有 `ITradeGateway` 等接口模式一致 | 使用 ABC（被否决：Protocol 更轻量） |
| 配置驱动阈值 | 与现有 `RiskSettings` 风格一致 | 硬编码（被否决：不可调） |
| 事件分发器独立 | 通知逻辑与风控评估解耦 | 内嵌在 CircuitBreaker（被否决：职责混合） |
