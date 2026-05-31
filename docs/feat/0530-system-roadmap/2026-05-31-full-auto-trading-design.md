# Phase 4: 全自动交易 — 设计文档

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 详细设计 / 技术方案
**状态**: 草案

---

## 一、需求概述

### 1.1 阶段目标

**从"人工审核"到"全自动执行"，实现真正的自动化交易。人只做异常处理和战略决策。**

### 1.2 用户故事

> 作为量化投资者，我希望系统每天自动执行策略信号、自动检测异常、自动暂停有问题的策略，
> 我只需要在手机上看看状态，偶尔处理一下告警。每周花 30 分钟复盘即可。

### 1.3 三个子项目

| # | 子项目 | 核心价值 | 优先级 |
|---|--------|---------|--------|
| 1 | 策略自动执行引擎 | 消除人工审核环节，信号到下单全自动 | P0 |
| 2 | 异常检测与自动暂停 | 保障资金安全，策略失效时自动停机 | P0 |
| 3 | 远程监控与告警 | 随时随地掌握系统状态 | P1 |

### 1.4 前置条件（进入 Phase 4 的门槛）

| 条件 | 量化标准 | 验证方式 |
|------|---------|---------|
| 风控熔断稳定运行 | 6 个月+ 无误触发 | 实盘日志统计 |
| 策略历史胜率 | > 55% | 回测 + 实盘统计 |
| 策略夏普比率 | > 1.5 | 回测报告 |
| ML 模型样本外 IC | 稳定 > 0.05 | 滚动验证 |
| 多策略组合运行 | 3 个月+ 稳定 | 实盘日志 |

---

## 二、现有架构分析

### 2.1 当前交易流程

```
当前半自动流程（live_trade.py）:

  QmtMarketGateway ──┐
  QmtTradeGateway  ──┤── LiveSignalService.scan()
                      │     ├── 拉行情 (get_recent_bars)
                      │     ├── 跑策略 (strategy.generate_signals)
                      │     └── 算仓位 (sizer.calculate_target)
                      │
                      ├── 用户审核 (CLI 交互: y/N 确认)
                      │
                      └── place_confirmed_orders()
                            └── trade_gateway.place_order()
```

### 2.2 现有风控体系

| 组件 | 文件 | 职责 |
|------|------|------|
| `BaseRiskPolicy` | `src/domain/risk/services/base_risk_policy.py` | 订单级风控接口（拦截下单） |
| `RiskChain` | `src/domain/risk/services/risk_chain.py` | 责任链：串联多个 Policy，任一不通过即拦截 |
| `SimpleRiskPolicy` | `src/domain/risk/services/risk_policies/simple_risk_policy.py` | 基础校验（价格>0, 数量>0） |
| `DrawdownPolicy` | `src/domain/risk/services/risk_policies/drawdown_policy.py` | 回撤熔断：当日回撤超阈值禁止买入 |
| `PositionLimitPolicy` | `src/domain/risk/services/risk_policies/position_limit_policy.py` | 单标的仓位上限 |
| `BaseRiskSignalPolicy` | `src/domain/risk/services/base_risk_signal_policy.py` | 持仓级风控接口（主动产出 SELL 信号） |
| `HardStopLossPolicy` | `src/domain/risk/services/risk_policies/hard_stop_loss_policy.py` | 绝对止损：亏损超阈值生成清仓信号 |
| `LimitUpBreakPolicy` | `src/domain/risk/services/risk_policies/limit_up_break_policy.py` | 涨停破板卖出 |
| `RiskSignalGenerator` | `src/domain/risk/services/risk_signal_generator.py` | 聚合多个 SignalPolicy |
| `SystemRiskGate` | `src/domain/risk/services/system_risk_gate.py` | 盘前系统级门禁（指数<MA20 禁止买入） |

### 2.3 现有缺口

| 缺口 | 说明 |
|------|------|
| 无自动执行循环 | 当前需要人工运行 CLI，无定时自动执行 |
| 无执行监控 | 下单后不跟踪成交状态、滑点 |
| 无策略级异常检测 | 只有订单级风控，无策略表现监控 |
| 无数据质量检查 | 行情缺失、财务异常无检测 |
| 无远程通知 | 仅 CLI 输出，无推送能力 |
| 无远程控制 | 必须在本地操作 |

---

## 三、子项目 4.1：策略自动执行引擎

### 3.1 架构设计

```
                         ┌──────────────────────────┐
                         │    AutoTradingEngine      │
                         │  (src/application/)       │
                         │                           │
                         │  ┌─────────────────────┐  │
                         │  │  ExecutionLoop       │  │
                         │  │  - 定时触发           │  │
                         │  │  - 交易时段校验       │  │
                         │  │  - 异常检测前置       │  │
                         │  └──────────┬──────────┘  │
                         │             │              │
                         │  ┌──────────▼──────────┐  │
                         │  │  SignalPipeline      │  │
                         │  │  - 策略信号生成       │  │
                         │  │  - 信号去重/过滤      │  │
                         │  │  - 仓位计算           │  │
                         │  └──────────┬──────────┘  │
                         │             │              │
                         │  ┌──────────▼──────────┐  │
                         │  │  OrderExecutor       │  │
                         │  │  - 风控检查           │  │
                         │  │  - 自动下单           │  │
                         │  │  - 成交跟踪           │  │
                         │  │  - 滑点监控           │  │
                         │  └──────────┬──────────┘  │
                         │             │              │
                         │  ┌──────────▼──────────┐  │
                         │  │  ExecutionMonitor    │  │
                         │  │  - 成功率统计         │  │
                         │  │  - 滑点分析           │  │
                         │  │  - 执行报告           │  │
                         │  └─────────────────────┘  │
                         └──────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
            ┌───────▼──────┐ ┌─────▼─────┐ ┌──────▼──────┐
            │ IMarketGateway│ │ITradeGateway│ │INotification│
            │  (QMT)       │ │  (QMT)     │ │  Gateway    │
            └──────────────┘ └───────────┘ └─────────────┘
```

### 3.2 核心组件设计

#### 3.2.1 AutoTradingEngine（应用层）

**文件**: `src/application/auto_trading_engine.py`

**职责**: 全自动交易的主控引擎，编排信号生成、风控检查、下单执行的完整闭环。

```python
@dataclass(slots=True, kw_only=True)
class AutoTradingConfig:
    """自动交易配置。"""
    strategy_names: list[str]           # 要执行的策略列表
    symbols: list[str]                  # 标的列表
    execution_times: list[str]          # 执行时间（如 ["09:35", "14:50"]）
    max_orders_per_cycle: int = 20      # 单次循环最大下单数
    min_confidence: float = 0.6         # 最低信号置信度
    enabled: bool = True                # 总开关


class AutoTradingEngine:
    """全自动交易引擎。

    定时执行策略信号 → 风控检查 → 自动下单 → 成交跟踪。
    """

    def __init__(
        self,
        signal_pipeline: SignalPipeline,
        order_executor: OrderExecutor,
        execution_monitor: ExecutionMonitor,
        anomaly_detector: AnomalyDetector,
        notification_gateway: INotificationGateway,
        config: AutoTradingConfig,
    ) -> None: ...

    def run_cycle(self) -> CycleResult:
        """执行一次完整的自动交易循环。"""
        # 1. 异常检测前置检查
        # 2. 生成信号
        # 3. 风控过滤
        # 4. 自动下单
        # 5. 记录执行结果
        # 6. 推送通知
        ...

    def start(self) -> None:
        """启动自动交易循环（守护线程）。"""
        ...

    def stop(self) -> None:
        """停止自动交易。"""
        ...
```

#### 3.2.2 SignalPipeline（应用层）

**文件**: `src/application/signal_pipeline.py`

**职责**: 统一的信号生成管线，聚合多策略信号、风控信号，输出可执行的订单目标。

```python
class SignalPipeline:
    """信号生成管线。

    复用现有 StrategyRunner + RiskSignalGenerator + SystemRiskGate，
    增加信号去重、置信度过滤、冲突解决。
    """

    def generate(self, context: DayContext) -> list[OrderTarget]:
        """生成当日可执行的订单目标列表。"""
        # 1. 各策略生成信号（复用 StrategyRunner.evaluate）
        # 2. 风控信号生成（复用 RiskSignalGenerator.evaluate）
        # 3. 系统门禁检查（复用 SystemRiskGate.check_gate）
        # 4. 信号去重（同一标的多策略信号合并）
        # 5. 置信度过滤（低于阈值的信号丢弃）
        # 6. 冲突解决（BUY vs SELL 冲突时优先 SELL）
        ...
```

#### 3.2.3 OrderExecutor（应用层）

**文件**: `src/application/order_executor.py`

**职责**: 自动下单执行器，集成风控检查，跟踪订单状态。

```python
@dataclass(slots=True, kw_only=True)
class ExecutionRecord:
    """执行记录。"""
    order_id: str
    symbol: str
    direction: OrderDirection
    target_price: float
    target_volume: int
    actual_price: float | None = None
    actual_volume: int = 0
    slippage: float = 0.0
    status: ExecutionStatus = ExecutionStatus.PENDING
    error_message: str = ""
    submitted_at: datetime | None = None
    filled_at: datetime | None = None


class OrderExecutor:
    """自动下单执行器。

    复用现有 OrderService 的风控检查逻辑，
    增加执行跟踪、滑点计算、重试机制。
    """

    def __init__(
        self,
        trade_gateway: ITradeGateway,
        risk_chain: RiskChain,
        max_retries: int = 2,
    ) -> None: ...

    def execute(self, targets: list[OrderTarget]) -> list[ExecutionRecord]:
        """执行订单目标列表。"""
        # 1. 卖出优先（先卖后买，释放资金）
        # 2. 逐单风控检查（复用 RiskChain.check）
        # 3. 下单并记录
        # 4. 查询成交状态
        # 5. 计算滑点
        ...
```

#### 3.2.4 ExecutionMonitor（域层）

**文件**: `src/domain/trade/services/execution_monitor.py`

**职责**: 执行质量监控，统计成功率、滑点、成交延迟。

```python
@dataclass(slots=True, kw_only=True)
class ExecutionStats:
    """执行统计。"""
    total_orders: int
    successful_orders: int
    failed_orders: int
    success_rate: float
    avg_slippage_buy: float
    avg_slippage_sell: float
    max_slippage: float
    avg_fill_time_seconds: float


class ExecutionMonitor:
    """执行质量监控。"""

    def record(self, record: ExecutionRecord) -> None:
        """记录一次执行结果。"""
        ...

    def get_stats(self, days: int = 30) -> ExecutionStats:
        """获取最近 N 天的执行统计。"""
        ...

    def check_health(self) -> HealthStatus:
        """检查执行健康状态。

        规则：
        - 成功率 < 90% → WARNING
        - 成功率 < 80% → CRITICAL
        - 平均滑点 > 0.3% → WARNING
        - 平均滑点 > 0.5% → CRITICAL
        """
        ...
```

### 3.3 执行优化（P1，后期实现）

#### 3.3.1 拆单策略

大额订单拆分为多个小单，减少市场冲击：

```python
class OrderSplitter:
    """订单拆分器。"""

    def split(self, order: OrderTarget, max_single_volume: int = 500) -> list[OrderTarget]:
        """将大单拆分为多个小单。

        规则：
        - 单笔不超过 max_single_volume
        - 单笔不超过当日成交量 10%
        - 买入时分批挂单（降低均价）
        """
        ...
```

#### 3.3.2 算法交易（P2，远期）

- TWAP（时间加权均价）：在指定时间段内均匀下单
- VWAP（成交量加权均价）：按历史成交量分布下单
- 冰山单：只显示部分数量，分批成交

---

## 四、子项目 4.2：异常检测与自动暂停

### 4.1 架构设计

```
                         ┌──────────────────────────────┐
                         │       AnomalyDetector         │
                         │  (src/application/)           │
                         │                               │
                         │  ┌──────────────────────────┐ │
                         │  │  StrategyAnomalyDetector  │ │
                         │  │  - 胜率突降检测            │ │
                         │  │  - 信号频率异常            │ │
                         │  │  - 连续亏损检测            │ │
                         │  └──────────────────────────┘ │
                         │                               │
                         │  ┌──────────────────────────┐ │
                         │  │  DataAnomalyDetector      │ │
                         │  │  - 行情数据缺失            │ │
                         │  │  - 价格跳变检测            │ │
                         │  │  - 财务数据异常            │ │
                         │  └──────────────────────────┘ │
                         │                               │
                         │  ┌──────────────────────────┐ │
                         │  │  MarketAnomalyDetector    │ │
                         │  │  - 极端行情检测            │ │
                         │  │  - 流动性枯竭              │ │
                         │  │  - 指数暴跌                │ │
                         │  └──────────────────────────┘ │
                         │                               │
                         │  ┌──────────────────────────┐ │
                         │  │  AutoPauseManager         │ │
                         │  │  - 暂停决策                │ │
                         │  │  - 恢复条件                │ │
                         │  │  - 通知推送                │ │
                         │  └──────────────────────────┘ │
                         └──────────────────────────────┘
```

### 4.2 核心组件设计

#### 4.2.1 AnomalyDetector（应用层）

**文件**: `src/application/anomaly_detector.py`

```python
@dataclass(slots=True, kw_only=True)
class AnomalyEvent:
    """异常事件。"""
    anomaly_type: AnomalyType        # STRATEGY / DATA / MARKET / ML_MODEL
    severity: AnomalySeverity        # WARNING / CRITICAL
    source: str                      # 触发源（策略名/数据源/指标名）
    message: str                     # 人类可读描述
    metric_value: float              # 触发指标值
    threshold: float                 # 阈值
    detected_at: datetime
    auto_action: AutoAction = AutoAction.NONE  # NONE / PAUSE_STRATEGY / PAUSE_ALL


class AnomalyDetector:
    """异常检测聚合器。

    聚合多个子检测器，统一输出异常事件。
    """

    def __init__(
        self,
        strategy_detectors: list[BaseAnomalyDetector],
        data_detectors: list[BaseAnomalyDetector],
        market_detectors: list[BaseAnomalyDetector],
        pause_manager: AutoPauseManager,
        notification_gateway: INotificationGateway,
    ) -> None: ...

    def run_checks(self) -> list[AnomalyEvent]:
        """运行所有异常检测。"""
        events: list[AnomalyEvent] = []
        for detector in self._all_detectors:
            events.extend(detector.detect())
        # 根据严重程度决定是否自动暂停
        for event in events:
            if event.auto_action == AutoAction.PAUSE_ALL:
                self.pause_manager.pause_all(event)
            elif event.auto_action == AutoAction.PAUSE_STRATEGY:
                self.pause_manager.pause_strategy(event.source, event)
        return events
```

#### 4.2.2 策略异常检测器（域层）

**文件**: `src/domain/risk/services/anomaly_detectors/strategy_anomaly_detector.py`

```python
class StrategyAnomalyDetector(BaseAnomalyDetector):
    """策略失效检测。

    检测维度：
    1. 滚动胜率突降：近 20 笔交易胜率 < 阈值
    2. 连续亏损：连续 N 笔亏损
    3. 信号频率异常：信号数量突然暴增或归零
    4. 盈亏比恶化：近 N 笔交易盈亏比下降
    """

    def __init__(
        self,
        trade_history: TradeHistoryRepository,
        strategy_name: str,
        min_win_rate: float = 0.45,
        max_consecutive_losses: int = 5,
        lookback_trades: int = 20,
    ) -> None: ...

    def detect(self) -> list[AnomalyEvent]:
        ...
```

#### 4.2.3 数据异常检测器（域层）

**文件**: `src/domain/risk/services/anomaly_detectors/data_anomaly_detector.py`

```python
class DataAnomalyDetector(BaseAnomalyDetector):
    """数据质量检测。

    检测维度：
    1. 行情数据缺失：某只股票连续无数据
    2. 价格跳变：单日涨跌幅超过阈值（非涨跌停）
    3. 成交量异常：成交量突然放大/缩小 10 倍+
    4. 财务数据异常：关键财务指标突变
    """

    def __init__(
        self,
        market_gateway: IMarketGateway,
        symbols: list[str],
        max_price_jump: float = 0.10,
        volume_spike_ratio: float = 10.0,
    ) -> None: ...

    def detect(self) -> list[AnomalyEvent]:
        ...
```

#### 4.2.4 市场异常检测器（域层）

**文件**: `src/domain/risk/services/anomaly_detectors/market_anomaly_detector.py`

```python
class MarketAnomalyDetector(BaseAnomalyDetector):
    """市场极端行情检测。

    检测维度：
    1. 指数暴跌：沪深300单日跌幅 > 3%
    2. 市场恐慌：涨跌比 < 0.2（上涨家数/下跌家数）
    3. 流动性枯竭：市场总成交量骤降
    4. 连续下跌：指数连续 N 日下跌
    """

    def __init__(
        self,
        market_gateway: IMarketGateway,
        index_symbol: str = "000300.SH",
        crash_threshold: float = -0.03,
        panic_ratio: float = 0.2,
    ) -> None: ...

    def detect(self) -> list[AnomalyEvent]:
        ...
```

#### 4.2.5 ML 模型异常检测器（域层）

**文件**: `src/domain/risk/services/anomaly_detectors/ml_model_anomaly_detector.py`

```python
class MlModelAnomalyDetector(BaseAnomalyDetector):
    """ML 模型健康检测。

    检测维度：
    1. 预测准确率下降：近期预测 IC < 阈值
    2. 特征漂移：输入特征分布与训练时差异 > 阈值
    3. 预测分布异常：预测值分布偏离历史范围
    4. 模型置信度下降：平均置信度持续走低
    """

    def __init__(
        self,
        prediction_log: PredictionLogRepository,
        feature_distribution: FeatureDistributionRepository,
        min_ic: float = 0.03,
        max_drift_score: float = 0.3,
    ) -> None: ...

    def detect(self) -> list[AnomalyEvent]:
        ...
```

#### 4.2.6 AutoPauseManager（应用层）

**文件**: `src/application/auto_pause_manager.py`

```python
@dataclass(slots=True, kw_only=True)
class PauseState:
    """暂停状态。"""
    strategy_name: str
    is_paused: bool
    reason: str
    paused_at: datetime | None = None
    resume_conditions: list[str] = field(default_factory=list)


class AutoPauseManager:
    """自动暂停管理器。

    维护每个策略的暂停状态，管理暂停/恢复逻辑。
    """

    def __init__(
        self,
        notification_gateway: INotificationGateway,
    ) -> None: ...

    def pause_strategy(self, strategy_name: str, event: AnomalyEvent) -> None:
        """暂停指定策略。"""
        ...

    def pause_all(self, event: AnomalyEvent) -> None:
        """暂停所有策略（紧急熔断）。"""
        ...

    def check_resume(self, strategy_name: str) -> bool:
        """检查是否满足恢复条件。

        恢复条件：
        - 异常消失（连续 N 次检测正常）
        - 人工确认恢复
        """
        ...

    def resume(self, strategy_name: str, operator: str = "system") -> None:
        """恢复策略执行。"""
        ...

    def get_status(self) -> list[PauseState]:
        """获取所有策略的暂停状态。"""
        ...
```

### 4.3 暂停等级

| 等级 | 触发条件 | 动作 | 恢复方式 |
|------|---------|------|---------|
| WARNING | 胜率略降、滑点略高 | 推送通知，不暂停 | 自动恢复 |
| PAUSE_STRATEGY | 单策略连续亏损、信号异常 | 暂停该策略，其他继续 | 自动/手动 |
| PAUSE_ALL | 指数暴跌、数据大面积缺失、多策略同时异常 | 暂停所有交易 | 仅手动 |

---

## 五、子项目 4.3：远程监控与告警

### 5.1 架构设计

```
  ┌──────────────────────────────────────────────┐
  │              GoldenHandQuant Server            │
  │                                                │
  │  ┌────────────┐  ┌────────────┐  ┌──────────┐│
  │  │ Trading    │  │ Anomaly    │  │ Execution││
  │  │ Engine     │  │ Detector   │  │ Monitor  ││
  │  └─────┬──────┘  └─────┬──────┘  └────┬─────┘│
  │        │               │              │       │
  │        └───────────────┼──────────────┘       │
  │                        │                       │
  │               ┌────────▼────────┐              │
  │               │ NotificationHub │              │
  │               │ (事件聚合 + 路由) │              │
  │               └────────┬────────┘              │
  │                        │                       │
  │        ┌───────────────┼───────────────┐       │
  │        │               │               │       │
  │  ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐ │
  │  │ WeChat    │  │ Telegram  │  │ WebPush   │ │
  │  │ Gateway   │  │ Gateway   │  │ Gateway   │ │
  │  └───────────┘  └───────────┘  └───────────┘ │
  └──────────────────────────────────────────────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
         ┌────▼────┐ ┌───▼───┐ ┌────▼────┐
         │  微信    │ │Telegram│ │ Web     │
         │  公众号  │ │  Bot  │ │Dashboard│
         └─────────┘ └───────┘ └─────────┘
```

### 5.2 核心组件设计

#### 5.2.1 INotificationGateway（域层接口）

**文件**: `src/domain/notification/interfaces/notification_gateway.py`

```python
class INotificationGateway(Protocol):
    """通知网关接口。"""

    def send(self, message: NotificationMessage) -> bool:
        """发送通知。"""
        ...

    def send_batch(self, messages: list[NotificationMessage]) -> int:
        """批量发送，返回成功数。"""
        ...
```

#### 5.2.2 NotificationMessage（域层值对象）

**文件**: `src/domain/notification/value_objects/notification_message.py`

```python
class NotificationLevel(Enum):
    INFO = "info"           # 信息：每日报告
    WARNING = "warning"     # 警告：滑点偏高
    CRITICAL = "critical"   # 严重：策略暂停
    EMERGENCY = "emergency" # 紧急：全部熔断


@dataclass(slots=True, kw_only=True)
class NotificationMessage:
    """通知消息。"""
    title: str
    body: str
    level: NotificationLevel
    category: str           # trade / risk / anomaly / system
    timestamp: datetime
    metadata: dict[str, str] = field(default_factory=dict)
```

#### 5.2.3 NotificationHub（应用层）

**文件**: `src/application/notification_hub.py`

```python
class NotificationHub:
    """通知中心。

    聚合系统内所有事件源，路由到对应的通知渠道。
    支持消息去重、频率限制、静默时段。
    """

    def __init__(
        self,
        gateways: list[INotificationGateway],
        rate_limiter: RateLimiter | None = None,
        quiet_hours: tuple[int, int] | None = None,
    ) -> None: ...

    def notify(self, message: NotificationMessage) -> None:
        """发送通知到所有渠道。"""
        ...

    def notify_trade_executed(self, record: ExecutionRecord) -> None:
        """交易执行通知。"""
        ...

    def notify_risk_triggered(self, result: RiskCheckResult, order: Order) -> None:
        """风控触发通知。"""
        ...

    def notify_anomaly_detected(self, event: AnomalyEvent) -> None:
        """异常检测通知。"""
        ...

    def notify_daily_report(self, stats: ExecutionStats) -> None:
        """每日报告通知。"""
        ...
```

#### 5.2.4 微信通知网关（基础设施层）

**文件**: `src/infrastructure/notification/wechat_gateway.py`

```python
class WeChatNotificationGateway(INotificationGateway):
    """微信公众号/企业微信通知网关。

    方案选择：
    - 企业微信机器人 Webhook（最简单，免费）
    - Server酱（个人项目推荐，免费额度足够）
    - PushPlus（备选方案）
    """

    def __init__(self, webhook_url: str) -> None: ...

    def send(self, message: NotificationMessage) -> bool:
        ...
```

#### 5.2.5 Telegram 通知网关（基础设施层）

**文件**: `src/infrastructure/notification/telegram_gateway.py`

```python
class TelegramNotificationGateway(INotificationGateway):
    """Telegram Bot 通知网关。"""

    def __init__(self, bot_token: str, chat_id: str) -> None: ...

    def send(self, message: NotificationMessage) -> bool:
        ...
```

#### 5.2.6 Web Dashboard（基础设施层，P1）

**文件**: `src/infrastructure/web/dashboard.py`

基于 FastAPI 的轻量 Web Dashboard，提供：

| 端点 | 功能 |
|------|------|
| `GET /api/status` | 系统状态（运行中/暂停/停止） |
| `GET /api/positions` | 当前持仓 |
| `GET /api/stats` | 执行统计 |
| `GET /api/anomalies` | 异常事件历史 |
| `POST /api/control/pause` | 暂停交易 |
| `POST /api/control/resume` | 恢复交易 |
| `GET /api/events` | SSE 实时事件流 |

### 5.3 远程控制

通过 Web Dashboard 或 Telegram Bot 实现远程控制：

| 操作 | Web | Telegram | 微信 |
|------|-----|---------|------|
| 查看状态 | GET /api/status | /status | 关键词回复 |
| 暂停交易 | POST /api/control/pause | /pause | "暂停" |
| 恢复交易 | POST /api/control/resume | /resume | "恢复" |
| 查看持仓 | GET /api/positions | /positions | "持仓" |
| 查看统计 | GET /api/stats | /stats | "统计" |

**安全措施**：
- 所有控制操作需要密码/Token 验证
- 操作日志完整记录
- 仅允许在非交易时段执行恢复操作（交易时段的暂停可随时执行）

---

## 六、领域模型扩展

### 6.1 新增域层组件

```
src/domain/
├── notification/                    # 新增：通知子域
│   ├── __init__.py
│   ├── interfaces/
│   │   └── notification_gateway.py  # INotificationGateway Protocol
│   └── value_objects/
│       ├── notification_message.py  # NotificationMessage, NotificationLevel
│       └── notification_config.py   # 静默时段、频率限制配置
│
├── risk/
│   ├── services/
│   │   └── anomaly_detectors/       # 新增：异常检测器
│   │       ├── __init__.py
│   │       ├── base.py              # BaseAnomalyDetector
│   │       ├── strategy_anomaly.py
│   │       ├── data_anomaly.py
│   │       ├── market_anomaly.py
│   │       └── ml_model_anomaly.py
│   └── value_objects/
│       └── anomaly_event.py         # AnomalyEvent, AnomalyType, AnomalySeverity
│
└── trade/
    ├── services/
    │   └── execution_monitor.py     # 新增：执行监控
    └── value_objects/
        └── execution_record.py      # 新增：ExecutionRecord
```

### 6.2 新增应用层组件

```
src/application/
├── auto_trading_engine.py           # 新增：自动交易引擎
├── signal_pipeline.py               # 新增：信号管线
├── order_executor.py                # 新增：自动下单执行器
├── anomaly_detector.py              # 新增：异常检测聚合器
├── auto_pause_manager.py            # 新增：自动暂停管理器
└── notification_hub.py              # 新增：通知中心
```

### 6.3 新增基础设施层组件

```
src/infrastructure/
├── notification/                    # 新增：通知网关实现
│   ├── __init__.py
│   ├── wechat_gateway.py
│   ├── telegram_gateway.py
│   └── webhook_gateway.py
│
└── web/                             # 新增：Web Dashboard
    ├── __init__.py
    ├── dashboard.py
    ├── routes/
    │   ├── status.py
    │   ├── control.py
    │   └── events.py
    └── static/
```

### 6.4 新增接口层

```
src/interfaces/
├── cli/
│   ├── auto_trade.py                # 新增：自动交易 CLI 入口
│   └── monitor.py                   # 新增：监控 CLI
└── api/
    └── v1/
        ├── control.py               # 新增：远程控制 API
        └── status.py                # 新增：状态查询 API
```

---

## 七、配置扩展

### 7.1 新增配置项

在 `src/infrastructure/config/settings.py` 中扩展：

```python
@dataclass(slots=True, kw_only=True)
class AutoTradeSettings:
    """自动交易配置。"""
    enabled: bool = False
    strategy_names: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    execution_times: list[str] = field(default_factory=lambda: ["09:35", "14:50"])
    max_orders_per_cycle: int = 20
    min_confidence: float = 0.6


@dataclass(slots=True, kw_only=True)
class AnomalySettings:
    """异常检测配置。"""
    min_win_rate: float = 0.45
    max_consecutive_losses: int = 5
    lookback_trades: int = 20
    crash_threshold: float = -0.03
    max_price_jump: float = 0.10
    volume_spike_ratio: float = 10.0


@dataclass(slots=True, kw_only=True)
class NotificationSettings:
    """通知配置。"""
    wechat_webhook: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    quiet_hours_start: int = 23
    quiet_hours_end: int = 7
    rate_limit_per_minute: int = 10
```

### 7.2 配置文件示例

```yaml
# resources/trading.yaml (扩展)

auto_trade:
  enabled: false
  strategy_names: ["micro_value", "multi_factor"]
  symbols: ["000852.SH"]  # 或从策略自动生成
  execution_times: ["09:35", "14:50"]
  max_orders_per_cycle: 20
  min_confidence: 0.6

anomaly:
  min_win_rate: 0.45
  max_consecutive_losses: 5
  lookback_trades: 20
  crash_threshold: -0.03

notification:
  wechat_webhook: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
  telegram_bot_token: ""
  telegram_chat_id: ""
  quiet_hours: [23, 7]
```

---

## 八、关键设计决策

### 8.1 复用 vs 新建

| 组件 | 决策 | 理由 |
|------|------|------|
| 信号生成 | 复用 `StrategyRunner` | 已有完整实现，无需重写 |
| 风控检查 | 复用 `RiskChain` + 各 Policy | 已有责任链模式，可扩展 |
| 系统门禁 | 复用 `SystemRiskGate` | 已有指数 MA20 门禁 |
| 订单执行 | 新建 `OrderExecutor` | 需要增加执行跟踪、滑点监控 |
| 异常检测 | 新建，域层接口 + 应用层聚合 | 全新能力 |
| 通知推送 | 新建，域层 Protocol + 基础设施实现 | 全新能力 |

### 8.2 自动执行的触发方式

**选择：定时任务 + 事件驱动混合**

- 定时触发：每日固定时间执行交易循环（APScheduler / 简单 sleep 循环）
- 事件驱动：异常检测结果实时触发暂停/通知
- 不选择消息队列：个人项目规模，不需要 Kafka/RabbitMQ

### 8.3 暂停状态持久化

暂停状态需要持久化（SQLite 或 JSON 文件），防止进程重启后丢失暂停状态。

**选择：SQLite**

- 轻量，无需额外服务
- 支持并发读
- 已有 Python 标准库支持

### 8.4 Web Dashboard 技术选型

**选择：FastAPI + SSE**

- 已在项目中预留 FastAPI（`src/interfaces/api/`）
- SSE（Server-Sent Events）满足单向实时推送需求
- 不需要 WebSocket 的双向通信
- 前端用简单的 HTML + Alpine.js，不需要 React/Vue

---

## 九、安全设计

### 9.1 操作安全

| 风险 | 措施 |
|------|------|
| 误触发自动交易 | `auto_trade.enabled` 默认 false，需显式开启 |
| 远程控制被滥用 | 所有控制操作需 Token 验证 |
| 暂停后忘记恢复 | 每日盘前自动检查，发送提醒通知 |
| 策略异常不停机 | 多级异常检测，CRITICAL 级自动暂停 |

### 9.2 数据安全

| 风险 | 措施 |
|------|------|
| 交易密钥泄露 | 密钥不进代码，通过环境变量/配置文件 |
| 通知内容泄露 | 通知不含完整账户信息，只含摘要 |
| 日志泄露 | 日志脱敏（隐藏账户 ID 后四位） |

---

## 十、非功能需求

### 10.1 性能

| 指标 | 目标 |
|------|------|
| 交易循环执行时间 | < 30 秒 |
| 异常检测执行时间 | < 5 秒 |
| 通知推送延迟 | < 10 秒 |
| Web Dashboard 响应时间 | < 1 秒 |

### 10.2 可靠性

| 指标 | 目标 |
|------|------|
| 自动执行成功率 | > 95% |
| 异常检测准确率 | > 90% |
| 误报率 | < 5% |
| 通知送达率 | > 99% |

### 10.3 可观测性

- 所有关键操作写日志（logging 模块）
- 执行记录持久化（SQLite）
- 每日自动生成运行报告
