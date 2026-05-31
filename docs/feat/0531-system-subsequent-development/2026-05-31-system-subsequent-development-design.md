# GoldenHandQuant 架构缺陷分析与后续发展路线图

> **版本**: v1.0 | **日期**: 2026-05-31 | **作者**: Architecture Review
> **基于**: `docs/rules/architecture.md` v2.0 — 对当前代码库的全面审查

---

## 一、架构级缺陷 (P0 — 必须尽快解决)

### 1.1 缺少统一的事件溯源 (Event Sourcing) 机制

**现状**:
- 事件总线 `EventBus` 仅用于回测场景的解耦，实盘交易缺乏可审计的事件流
- `Order` 的状态变更没有产出领域事件，无法回溯"谁在什么时间做了什么"
- `CircuitBreaker` 的触发/恢复通过 `RiskEvent` 记录，但这些事件没有持久化
- `AutoPauseManager` 只持久化了最终状态，丢失了状态变更历史

**影响**:
- 交易操作无法审计，出现问题时无法溯源
- 监管合规风险（A 股要求交易记录可追溯）
- 状态异常时无法通过事件回放恢复

**建议方案**:

```
引入 DomainEvent 基类 + EventStore:

1. 定义 DomainEvent 基类
   @dataclass(frozen=True, slots=True, kw_only=True)
   class DomainEvent:
       event_id: str          # UUID
       event_type: str        # "OrderSubmitted" / "CircuitBreakerTriggered"
       aggregate_id: str      # 聚合根 ID（如 order_id）
       aggregate_type: str    # 聚合根类型（如 "Order"）
       timestamp: datetime
       payload: dict[str, object]

2. 关键实体自动发布事件
   - Order: CREATED → SUBMITTED → FILLED/CANCELED 每次状态变更发布事件
   - CircuitBreaker: NORMAL → TRIGGERED → COOLDOWN → NORMAL 发布事件
   - StrategyPoolEntry: CANDIDATE → ACTIVE → RETIRED 发布事件

3. EventStore 统一持久化
   - 基于 SQLite 的 append-only 事件表
   - 支持按 aggregate_id / event_type / 时间范围查询
   - 为后续审计和对账打下基础
```

### 1.2 应用层职责过重，缺少防腐层 (Anti-Corruption Layer)

**现状**:
- `AutoTradingEngine` 同时承担了调度、编排、错误处理三重职责（~240 行），违反 SRP
- `SignalPipeline.signals_to_targets()` 中 `volume=100` 是硬编码，未接入 `IPositionSizer`
- `MonitorService` 直接调用 `IAccountGateway.get_positions()` + `IMarketGateway.get_recent_bars()`，缺少 DTO 层屏蔽 domain 模型
- 应用层方法直接接收/返回领域实体，接口层与领域层耦合

**影响**:
- 修改领域模型会连锁影响接口层
- `volume=100` 硬编码可能导致实盘下单量错误
- AutoTradingEngine 难以测试和维护

**建议方案**:

```
1. 拆分 AutoTradingEngine
   - TradingScheduler: 调度逻辑（时间判断、线程管理、心跳）
   - TradingOrchestrator: 业务编排（信号 → 风控 → 下单 → 通知）
   - AutoTradingEngine: 顶层门面，组合以上两者

2. 引入 Command/Query DTO
   @dataclass(frozen=True, slots=True, kw_only=True)
   class PlaceOrderCommand:
       symbol: str
       direction: OrderDirection
       volume: int
       price: float
       strategy_name: str

   @dataclass(frozen=True, slots=True, kw_only=True)
   class MonitorQuery:
       account_id: str | None = None
       include_positions: bool = True
       include_risk: bool = True

3. SignalPipeline.signals_to_targets() 接入 IPositionSizer
   - 注入 IPositionSizer，由其计算目标数量
   - 删除 volume=100 硬编码
```

### 1.3 缺少事务一致性保证

**现状**:
- 回测中的"下单 → 冻结资金 → 撮合 → 扣款"是分散调用，没有事务边界
- 如果撮合成功但快照记录失败，会导致资产与快照不一致
- SQLite 持久化没有使用 `BEGIN TRANSACTION` / `COMMIT` 包裹
- `AutoTradingEngine.run_cycle()` 中信号生成、风控检查、下单是逐步执行，中间任何一步失败都无法回滚

**影响**:
- 数据不一致风险（资产 vs 快照 vs 持仓）
- 回测结果不可靠
- 实盘资金安全风险

**建议方案**:

```
引入 Unit of Work 模式:

class UnitOfWork:
    """事务工作单元。"""

    def __enter__(self) -> "UnitOfWork":
        self._conn = self._db.connect()
        self._conn.execute("BEGIN TRANSACTION")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self._conn.execute("COMMIT")
        else:
            self._conn.execute("ROLLBACK")
        self._conn.close()

    def commit(self) -> None:
        self._conn.execute("COMMIT")
        self._conn.close()

    def rollback(self) -> None:
        self._conn.execute("ROLLBACK")
        self._conn.close()

使用示例:
    with UnitOfWork(db) as uow:
        trade_gateway.place_order(order)      # 下单
        asset.freeze_cash(amount)              # 冻结资金
        snapshot_repo.save(daily_snapshot)     # 记录快照
        # 任何一步异常，自动回滚
```

---

## 二、设计级缺陷 (P1 — 应当尽快解决)

### 2.1 通知子域过于单薄

**现状**:
- `src/domain/notification/` 只有一个 `INotificationGateway` 接口和一个 `NotificationMessage` 值对象
- 缺少通知去重逻辑（同一事件可能触发多条重复通知）
- 缺少通知优先级队列（CRITICAL 应该比 INFO 先送达）
- 缺少通知确认/回执机制（关键通知如熔断触发，需要确认已送达）
- 缺少通知历史查询

**影响**:
- 异常事件可能被通知洪流淹没
- 关键通知无法确认是否送达
- 缺少通知效果的追踪和优化依据

**建议方案**:

```
扩展 NotificationHub:

1. 通知去重
   - 基于 (title, category, level) 的滑动窗口去重
   - 相同事件 5 分钟内只发送一次
   - 累计计数，最后一次通知中附带"共 N 次"

2. 优先级队列
   - EMERGENCY/CRITICAL: 立即发送，不受静默时段限制
   - WARNING: 队列发送，静默时段延迟
   - INFO: 批量合并，每小时摘要

3. 回执机制
   class NotificationReceipt:
       notification_id: str
       sent_at: datetime
       delivered: bool
       confirmed: bool
       confirmed_at: datetime | None
   - EMERGENCY 级别未确认时，5 分钟后重发
   - 支持确认链接（企业微信/Telegram 回调）

4. 通知历史
   - NotificationHistory 仓储
   - 支持按日期/级别/类别查询
   - 支持统计（发送量、送达率、确认率）
```

### 2.2 风控子域缺少风控日志聚合

**现状**:
- `RiskEvent` 由 `CircuitBreaker` 内部持有，随实例销毁而丢失
- `AlertEngine` 产出的 `Alert` 也没有持久化
- `AnomalyDetector` 检测到的 `AnomalyEvent` 只在日志中输出
- 缺少"每日风控报告"的自动生成能力

**影响**:
- 风控事件无法事后审查
- 无法分析风控策略的有效性（如某策略被拦截了多少次）
- 无法生成合规报告

**建议方案**:

```
引入 RiskLog 聚合根:

class RiskLog:
    """风控日志聚合根 — 统一记录所有风控事件。"""

    def append(self, event: RiskEvent | Alert | AnomalyEvent) -> None: ...
    def query(self, filter: RiskLogFilter) -> list[RiskLogEntry]: ...
    def daily_summary(self, date: date) -> RiskDailySummary: ...

持久化:
   - RiskLogRepository 接口（domain 层）
   - SQLiteRiskLogRepository 实现（infrastructure 层）
   - append-only 设计，禁止修改/删除

每日风控报告:
   - 盘后自动生成
   - 包含: 拦截次数、拦截原因分布、熔断触发次数、异常检测次数
   - 通过 NotificationHub 推送摘要
```

### 2.3 策略池缺少回测 → 上线的自动流转

**现状**:
- `PoolManager.evaluate_strategy()` 需要手动调用
- 缺少注册 → 回测 → 评级 → 自动上线的流水线
- 评级下滑后不会自动降级（ACTIVE → PAUSED）或下线（RETIRED）
- 策略池与 `CapitalAllocationEngine` 没有联动（新策略上线时不会自动调整资金分配）

**影响**:
- 策略运维需要人工介入，效率低
- 表现不佳的策略可能持续运行造成亏损
- 资金分配与策略池状态脱节

**建议方案**:

```
引入 StrategyLifecycleManager 应用服务:

class StrategyLifecycleManager:
    """策略全生命周期管理器。"""

    def register_and_backtest(self, name: str, ...) -> StrategyPoolEntry:
        """注册新策略并自动回测评估。"""
        # 1. 注册到策略池 (PoolManager.register)
        # 2. 自动运行回测 (BacktestAppService)
        # 3. 评估并评级 (PoolManager.evaluate_strategy)
        # 4. 评级 >= B → 自动上线 (entry.activate)
        # 5. 通知资金分配引擎 (CapitalAllocationEngine.adjust_for_new_strategy)
        ...

    def check_performance(self) -> list[StrategyPoolEntry]:
        """定期检查所有活跃策略的表现。"""
        # 1. 获取所有 ACTIVE 策略
        # 2. 检查 should_auto_retire
        # 3. 评级 D → PAUSED
        # 4. 连续跑输基准 → RETIRED
        # 5. 调整资金分配
        ...

调度:
   - 每周执行 check_performance()
   - 通过 NotificationHub 推送策略状态变更通知
```

### 2.4 ML 模型管理缺少 A/B 测试和影子模式

**现状**:
- `MLModelVersion` 只支持 `activate/rollback`，不支持灰度发布
- 没有"影子模式"（新模型只产出预测不实际交易，用于对比验证）
- `MlModelAnomalyDetector` 只检测漂移，不触发重训练
- 没有模型性能持续监控

**影响**:
- 新模型上线风险大（全量切换，无法灰度验证）
- 模型漂移后只能人工干预
- 无法量化新模型相比旧模型的实际收益提升

**建议方案**:

```
引入 ModelDeploymentStrategy:

class ModelDeploymentStrategy(StrEnum):
    FULL_ROLLOUT = "full_rollout"    # 全量切换
    CANARY = "canary"                # 金丝雀发布（10% 流量）
    SHADOW = "shadow"                # 影子模式（只预测不交易）

MLModelVersion 扩展:
   deployment: ModelDeploymentStrategy
   traffic_percentage: float  # 0.0 ~ 1.0

影子模式集成:
   - 在 AutoTradingEngine.run_cycle() 中:
     a. 活跃模型产出实际交易信号
     b. 影子模型产出预测信号（不执行）
     c. 记录两者差异到 ShadowComparisonLog
   - 定期分析影子模式日志:
     · 影子模型的预测准确率
     · 与活跃模型的收益对比
     · IC 值对比
   - 如果影子模型持续优于活跃模型 → 自动提示升级

漂移自动重训练:
   - MlModelAnomalyDetector 检测到漂移
   - 触发 TrainingPipeline.walk_forward_train()
   - 新模型以 SHADOW 模式部署
   - 影子验证通过后 → CANARY → FULL_ROLLOUT
```

---

## 三、功能欠缺分析

### 3.1 交易能力缺失

| 缺失功能 | 优先级 | 说明 | 预估工作量 |
|---------|--------|------|-----------|
| **盘中实时风控** | P0 | 当前 `CircuitBreaker` 仅在 `evaluate()` 时检查，缺少盘中 tick 级别监控 | 2 周 |
| **智能订单路由** | P1 | 当前只有一个 `ITradeGateway`，无法在不同券商间选择最优路径 | 3 周 |
| **算法交易** | P1 | 缺少 TWAP/VWAP/冰山单等算法拆单能力，大额订单直接市价冲击大 | 4 周 |
| **盘后自动对账** | P1 | 缺少系统持仓与券商持仓的自动对账功能 | 2 周 |
| **逆回购自动管理** | P2 | 闲置资金自动参与逆回购，提升资金利用率 | 1 周 |

### 3.2 研究能力缺失

| 缺失功能 | 优先级 | 说明 | 预估工作量 |
|---------|--------|------|-----------|
| **因子自动挖掘流水线** | P1 | `FactorMiner` 存在但缺少从挖掘 → 检验 → 入库 → 上线的端到端自动化 | 3 周 |
| **策略参数优化** | P2 | 缺少 Walk-Forward 参数优化（当前只有 ML 模型的 Walk-Forward） | 2 周 |
| **归因分析** | P2 | 缺少 Brinson 归因、因子归因等收益分解能力 | 3 周 |
| **组合优化** | P2 | 缺少均值-方差优化、Black-Litterman 等经典组合优化算法 | 4 周 |
| **多频率策略** | P2 | 当前只支持日线策略，缺少分钟级/周线级多频率策略框架 | 3 周 |

### 3.3 运维能力缺失

| 缺失功能 | 优先级 | 说明 | 预估工作量 |
|---------|--------|------|-----------|
| **健康检查与心跳** | P1 | `AutoTradingEngine` 守护线程崩溃后无外部感知机制 | 1 周 |
| **操作审计日志** | P1 | 缺少谁在什么时间执行了什么操作的审计追踪 | 2 周 |
| **配置热更新** | P2 | 修改 `trading.yaml` 后需要重启才能生效 | 1 周 |
| **多账户支持** | P2 | 当前 `QmtSettings` 只支持单个账户 | 2 周 |
| **部署自动化** | P2 | 缺少 Docker 化、CI/CD 流水线 | 2 周 |

---

## 四、后续发展路线图

### Phase 1 — 稳固基础（1-2 个月）

> **目标**: 消除架构级缺陷，确保系统可靠性和数据一致性

```
Week 1-2: [P0] 引入 DomainEvent + EventStore
   ├─ 定义 DomainEvent 基类（domain 层，纯标准库）
   ├─ Order/Position 状态变更自动产出事件
   ├─ CircuitBreaker 触发/恢复产出事件
   ├─ SQLite EventStore 实现（infrastructure 层）
   └─ 测试覆盖

Week 2-3: [P0] 重构 AutoTradingEngine 职责
   ├─ 抽取 TradingScheduler（调度逻辑、线程管理、心跳）
   ├─ 抽取 TradingOrchestrator（业务编排）
   ├─ SignalPipeline.signals_to_targets() 接入 IPositionSizer
   ├─ 引入 PlaceOrderCommand / MonitorQuery DTO
   └─ 重构测试

Week 3-4: [P0] 引入 Unit of Work 事务边界
   ├─ UnitOfWork 抽象（domain 层接口）
   ├─ SQLiteUnitOfWork 实现（infrastructure 层）
   ├─ BacktestAppService 关键操作包裹事务
   ├─ AutoTradingEngine 关键操作包裹事务
   └─ 事务回滚测试

Week 4-6: [P1] 健康检查 + 审计日志
   ├─ Watchdog 线程监控守护线程存活
   ├─ 心跳写入文件，外部可检测
   ├─ 异常时自动重启 + 通知
   ├─ OperationAuditLog 领域服务
   └─ 审计日志持久化与查询

Week 5-8: [P1] 通知子域扩展
   ├─ 通知去重（滑动窗口）
   ├─ 优先级队列
   ├─ 回执机制（EMERGENCY 未确认重发）
   ├─ 通知历史仓储
   └─ 每日通知摘要
```

**Phase 1 交付物**:
- ✅ 所有交易操作可审计（EventStore）
- ✅ 事务一致性保证（UnitOfWork）
- ✅ AutoTradingEngine 职责清晰（SRP）
- ✅ 守护线程崩溃可感知（Watchdog）
- ✅ 关键通知可确认送达（回执机制）

### Phase 2 — 研发闭环（2-4 个月）

> **目标**: 打通策略研发到上线的全流程自动化

```
Week 9-12: [P1] 策略全生命周期自动化
   ├─ StrategyLifecycleManager 应用服务
   ├─ register_and_backtest() 自动流水线
   ├─ check_performance() 定期巡检
   ├─ 与 CapitalAllocationEngine 联动
   └─ 策略状态变更通知

Week 10-14: [P1] 因子研发流水线
   ├─ FactorMiner → ICTest → LayerBacktest → 自动入库
   ├─ 因子衰减监控 + 自动淘汰
   ├─ 因子组合优化（正交化、逐步回归）
   └─ 因子表达式 DSL 增强

Week 12-16: [P1] ML 模型灰度发布
   ├─ ModelDeploymentStrategy (FULL_ROLLOUT / CANARY / SHADOW)
   ├─ 影子模式集成到 AutoTradingEngine
   ├─ ShadowComparisonLog 记录与对比
   ├─ 漂移检测 → 自动触发重训练
   └─ 灰度验证 → 自动升级

Week 14-16: [P1] 盘后自动对账
   ├─ 系统持仓 vs 券商持仓对比
   ├─ 资金余额校验
   ├─ 差异自动告警
   └─ 每日对账报告

Week 16-18: [P0] 盘中实时风控增强
   ├─ Tick 级别价格监控
   ├─ 实时止损检查
   ├─ 异常成交检测
   └─ 实时风控面板
```

**Phase 2 交付物**:
- ✅ 策略从研发到上线全自动化
- ✅ 因子研发闭环（挖掘 → 检验 → 上线）
- ✅ ML 模型安全上线（影子 → 金丝雀 → 全量）
- ✅ 每日自动对账
- ✅ 盘中实时风控

### Phase 3 — 能力跃迁（4-6 个月）

> **目标**: 引入机构级交易能力，提升资金利用效率和风险控制精度

```
Week 19-22: [P2] 算法交易
   ├─ TWAP 策略实现（时间加权平均价格）
   ├─ VWAP 策略实现（成交量加权平均价格）
   ├─ 冰山单（隐藏真实意图）
   ├─ 大额订单自动拆分
   └─ 算法交易执行器接口（IAlgoTrader）

Week 20-24: [P2] 归因分析
   ├─ Brinson 归因分解（配置 + 选择 + 交互）
   ├─ 因子归因（收益由哪些因子贡献）
   ├─ 每日自动生成归因报告
   └─ 归因可视化

Week 22-26: [P2] 组合优化
   ├─ 均值-方差优化
   ├─ Black-Litterman 模型
   ├─ 风险预算模型
   ├─ 与 CapitalAllocationEngine 集成
   └─ 回测中验证优化效果

Week 24-28: [P2] 配置热更新
   ├─ YAML 文件变更监听（watchdog）
   ├─ 运行时动态调整参数
   ├─ 参数变更审计日志
   └─ 变更回滚机制
```

**Phase 3 交付物**:
- ✅ 算法交易减少市场冲击
- ✅ 收益来源清晰可量化
- ✅ 资金分配科学化
- ✅ 参数调整无需重启

### Phase 4 — 体系化运营（6+ 个月）

> **目标**: 从单策略单账户走向多策略多账户体系化运营

```
Month 7-8: 多账户 + 多策略并行
   ├─ 多账户管理（不同券商/不同策略组）
   ├─ 策略间资金自动调配
   ├─ 全局风控视角（跨账户汇总）
   └─ 账户组管理接口

Month 8-10: 实时 Dashboard
   ├─ WebSocket 推送持仓/盈亏/风控状态
   ├─ 策略运行状态可视化
   ├─ 历史收益曲线实时更新
   ├─ 风控仪表盘
   └─ 移动端适配

Month 10-12: 微服务拆分评估与实施
   ├─ 性能瓶颈分析
   ├─ 拆分优先级评估:
     · 行情服务 (无状态, 计算密集)
     · 交易服务 (有状态, 低延迟)
     · 策略服务 (无状态, 计算密集)
     · 风控服务 (有状态, 高可靠)
   ├─ 服务间通信方案 (gRPC / message queue)
   ├─ 渐进式拆分（优先拆分无状态服务）
   └─ 统一监控与日志
```

**Phase 4 交付物**:
- ✅ 多账户体系化运营
- ✅ 实时可视化监控
- ✅ 微服务架构（按需拆分）

---

## 五、技术债务清单

| 编号 | 债务项 | 位置 | 影响 | 清理优先级 |
|------|--------|------|------|-----------|
| TD-01 | `SignalPipeline.signals_to_targets()` 中 `volume=100` 硬编码 | `application/signal_pipeline.py:72` | 实盘下单量错误 | **P0** |
| TD-02 | `AutoTradingEngine` 内部 `from src.domain.strategy.value_objects.signal_direction import SignalDirection` 延迟导入 | `application/auto_trading_engine.py:126` | 架构层次违规 | P1 |
| TD-03 | `NotificationFactory.create_notification_gateway()` 只使用第一个通知器 | `infrastructure/notification/factory.py:38` | 多渠道失效 | P1 |
| TD-04 | `RiskEventDispatcher.dispatch()` 中 `except Exception: pass` | `domain/risk/services/risk_event_dispatcher.py:22` | 通知失败无感知 | P1 |
| TD-05 | `StockSnapshot` 使用 `__slots__` + `__getattr__/__setattr__` 兼容层，增加理解成本 | `domain/market/value_objects/stock_snapshot.py` | 可维护性 | P2 |
| TD-06 | `BacktestAppService` 的 EventBus 模式与同步模式大量重复逻辑 | `application/backtest_app.py` | 代码重复 | P2 |
| TD-07 | 配置加载 `load_backtest_config()` / `load_trading_config()` 手动解析嵌套字典，与 `AppSettings` 结构易不同步 | `infrastructure/config/settings.py` | 配置遗漏风险 | P2 |
| TD-08 | `TrainingPipeline.prepare_dataset()` 中 `date` 和 `symbol` 列的来源隐式依赖于 `extract_base_features()` 的实现 | `infrastructure/ml_engine/training_pipeline.py` | 数据正确性 | P1 |

---

## 六、架构演进原则

在推进上述路线图时，必须遵循以下原则：

1. **领域层纯洁不可破**: 任何新功能（事件溯源、审计日志、风控日志）在 domain 层只能使用标准库
2. **接口先行**: 新增能力先在 domain 层定义 Protocol 接口，再在 infrastructure 层实现
3. **渐进式演进**: 不做大规模重写，每个 Phase 内的变更保持系统可运行
4. **测试覆盖先行**: 每个新功能必须先写测试，domain 层测试零 Mock
5. **向后兼容**: `StockSnapshot` 等已有接口的扩展必须保持向后兼容
6. **配置化 > 硬编码**: 所有参数（费率、阈值、时间窗口）必须通过 `AppSettings` 配置化
7. **安全内建**: 新增的任何外部通信（通知、API、Webhook）必须内置认证和脱敏
