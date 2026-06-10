# GoldenHandQuant 架构宪法与开发规范 (Architecture & Coding Guidelines)

> **版本**: v3.0 | **更新日期**: 2026-06-01 | **适用范围**: 全项目 AI 编码助手 & 人类开发者

## 1. 系统定位与核心架构

* **系统名称**: GoldenHandQuant
* **业务场景**: 中国 A 股量化交易系统（回测框架 + 实盘交易 + 策略研发平台）
* **架构模式**: 基于领域驱动设计 (DDD) 的单体架构 (Monolithic Architecture)
* **核心驱动**: 进程内事件驱动 (In-Memory Event-Driven) + 定时调度 (Scheduled Execution)
* **Python 版本**: 3.13+
* **运行模式**:
  - **回测模式**: 通过 `BacktestAppService` 编排历史行情推进、策略信号、模拟撮合、日终结算
  - **实盘模式**: 通过 `AutoTradingEngine` 定时执行策略信号 → 风控检查 → 自动下单 → 成交跟踪
  - **研究模式**: 通过因子挖掘、因子检验、ML 训练管道进行策略研发

## 2. 核心红线 (AI 编码绝对禁令)

作为本项目的 AI 编程助手，你在生成任何代码时，**必须绝对遵守以下红线，不可有任何逾越**：

1. **领域层无副作用 (Domain Purity)**: `src/domain` 目录下的代码**允许**使用纯计算库（numpy / pandas / scipy——无 I/O、无网络、无全局状态），用于向量化数值计算；**严禁**引入带副作用或环境依赖的库：数据源 SDK（xtquant、tushare）、存储引擎（duckdb、sqlite 包装）、Web 框架（fastapi）、可视化（matplotlib）、ML 训练库（lightgbm、catboost）。红线的本质是"领域逻辑无副作用、可独立测试"，而非禁用高性能数值库（变更决定与动机见 `docs/feat/0611-market-data-store/2026-06-11-market-data-store-design.md` §2，2026-06-11）。
2. **严格的依赖控制**: 依赖关系只能**由外向内**。
   * Infrastructure（基础设施层）可以调用 Application（应用层）和 Domain（领域层）。
   * Application 可以调用 Domain。
   * **Domain 不能调用任何其他层。**
3. **接口隔离原则 (DIP)**: 领域层只定义接口（Protocol 类 / ABC），具体的外部调用（如对接 QMT、发送通知、ML 推理）必须在 `src/infrastructure` 层实现这些接口。领域层需要跨子域通信时，通过接口解耦（如 `risk` 子域通过 `IRiskNotifier` 接口通知，不直接依赖 `notification` 子域）。
4. **强制类型注解 (Type Hinting)**: 所有函数签名、类属性必须包含完整且准确的 Python Type Hints。
5. **通知脱敏**: 交易通知中的敏感信息（价格、数量）必须支持脱敏模式：价格只保留整数，数量使用模糊级别（如 `1K 级`、`>5W`），避免泄露精确交易信息。
6. **状态文件完整性**: 持久化的状态文件（如 `pause_state.json`）必须附带 HMAC 签名，加载时校验签名防止篡改。

## 3. 标准目录结构与职责说明

请严格按照以下目录结构划分模块：

```
GoldenHandQuant/
├── resources/              # 运行时配置文件 (yaml)
│   ├── backtest.yaml       # 回测配置
│   ├── backtest_multi_factor.yaml
│   └── trading.yaml        # 实盘交易配置
├── data/                   # 本地数据缓存、快照、预训练模型存放区
│   └── factors/models/     # ML 模型存储
├── logs/                   # 运行日志存放区
└── src/
    ├── domain/             # 【领域层】核心业务逻辑，实体、值对象、领域服务、接口定义
    │   ├── common/         # 公共子域（DomainEvent、EventStore、UnitOfWork、审计日志）
    │   │   ├── value_objects/     # DomainEvent、AuditLogEntry、ConfigChangeLog
    │   │   ├── services/          # AuditService
    │   │   └── interfaces/        # EventStore、UnitOfWork、AuditLogRepository
    │   ├── account/        # 账户与持仓子域
    │   │   ├── entities/          # Asset、Position、AccountGroup
    │   │   ├── value_objects/     # MonitorQuery、ReconciliationReport、PositionDifference
    │   │   ├── services/          # SettlementService、ReconciliationService、MultiAccountService
    │   │   └── interfaces/        # IAccountGateway、IAccountRepository、IReconciliationRepository、IAccountGroupRepository
    │   ├── trade/          # 交易执行子域（订单、成交、执行监控、算法交易）
    │   │   ├── entities/          # Order
    │   │   ├── value_objects/     # OrderEvents、PlaceOrderCommand、HealthStatus、AlgoOrderConfig/Status/Slice/Progress
    │   │   ├── services/          # ExecutionMonitor、AlgoOrderManager
    │   │   │   └── algo_strategies/ # TWAPStrategy、VWAPStrategy、IcebergStrategy
    │   │   └── interfaces/        # ITradeGateway、IAlgoTrader、IHealthGateway
    │   ├── market/         # 行情与因子子域（Bar、K线周期、基本面快照、股票截面快照）
    │   ├── strategy/       # 策略信号子域
    │   │   ├── factors/    # 因子定义（价值、质量、技术、价量、反转、低波、基本面、挖掘）
    │   │   ├── factor_test/# 因子表达式检验（词法/语法分析、求值器、打分器、报告）
    │   │   ├── pool/       # 策略池（条目管理、评级引擎、ML 模型版本）
    │   │   ├── services/   # 策略实现（时序策略、截面策略）+ 过滤器
    │   │   │   ├── strategy_lifecycle_manager.py  # 策略生命周期管理
    │   │   │   ├── factor_pipeline.py             # 因子研发流水线
    │   │   │   └── shadow_mode_service.py         # ML 影子模式服务
    │   │   └── value_objects/     # StrategyLifecycleStatus、FactorLifecycleStatus、ModelDeploymentStrategy、ShadowComparisonLog
    │   ├── risk/           # 风控拦截子域
    │   │   ├── value_objects/     # RiskDomainEvents、RiskAlert
    │   │   └── services/
    │   │       ├── risk_policies/     # 逐单风控策略（止损、回撤、仓位限制等）
    │   │       ├── alert_rules/       # 告警规则（集中度、日亏损、仓位比、个股亏损）
    │   │       ├── anomaly_detectors/ # 异常检测器（策略、数据、市场、ML 模型）
    │   │       ├── portfolio/         # 组合级风控（相关性、分散度、VaR、压力测试）
    │   │       ├── realtime_risk_monitor.py  # 实时风控监控
    │   │       └── realtime_stop_loss.py     # 实时止损
    │   ├── portfolio/      # 仓位管理子域（PositionSizer + 资金分配 + 再平衡 + 组合优化）
    │   │   ├── value_objects/     # OptimizationResult
    │   │   └── services/
    │   │       ├── sizers/              # 仓位计算
    │   │       ├── allocation_algorithms/ # 资金分配算法
    │   │       ├── rebalance_triggers/    # 再平衡触发
    │   │       └── optimization/          # 组合优化（MeanVariance、BlackLitterman、RiskBudget）
    │   ├── notification/   # 通知子域（通知网关接口、消息值对象、去重、优先级、回执）
    │   │   ├── value_objects/     # NotificationMessage、NotificationPriority、NotificationReceipt、NotificationHistory
    │   │   ├── services/          # NotificationDeduplicator、NotificationPriorityQueue
    │   │   └── interfaces/        # INotificationGateway、INotificationHistoryRepository
    │   └── backtest/       # 回测模拟子域（报告、快照、交易记录、策略对比、归因分析）
    │       ├── value_objects/     # DailySnapshot、TradeRecord、AttributionReport、DashboardSnapshot
    │       └── services/
    │           └── attribution/   # BrinsonAttribution、FactorAttribution
    ├── application/        # 【应用层】用例编排，协调领域对象与基础设施
    │   ├── backtest_app.py          # 回测编排
    │   ├── trading_app.py           # 实盘交易编排
    │   ├── auto_trading_engine.py   # 全自动交易引擎（定时循环 + 守护线程）
    │   ├── trading_orchestrator.py  # 交易编排器（信号→风控→下单→通知）
    │   ├── trading_scheduler.py     # 交易调度器（线程管理、时间判断、心跳）
    │   ├── signal_pipeline.py       # 信号管线（去重、置信度过滤、冲突解决）
    │   ├── order_executor.py        # 订单执行器
    │   ├── order_service.py         # 订单服务
    │   ├── notification_hub.py      # 通知中心（频率限制、静默时段、去重、优先级）
    │   ├── monitor_service.py       # 实盘监控编排
    │   ├── anomaly_detector.py      # 异常检测聚合器
    │   ├── auto_pause_manager.py    # 自动暂停管理器（HMAC 签名状态持久化）
    │   ├── strategy_runner.py       # 策略运行器
    │   ├── live_signal_service.py   # 实盘信号服务
    │   ├── strategy_comparison_app.py # 策略对比应用
    │   ├── health_service.py        # 健康检查服务（Watchdog、心跳）
    │   ├── strategy_lifecycle_app.py # 策略生命周期应用服务
    │   ├── factor_pipeline_app.py   # 因子流水线应用服务
    │   ├── ml_deployment_app.py     # ML 模型灰度发布应用服务
    │   ├── reconciliation_app.py    # 盘后对账应用服务
    │   ├── realtime_risk_app.py     # 实时风控应用服务
    │   ├── algo_trading_app.py      # 算法交易应用服务
    │   ├── attribution_app.py       # 归因分析应用服务
    │   ├── portfolio_optimization_app.py # 组合优化应用服务
    │   ├── config_app.py            # 配置热更新应用服务
    │   ├── multi_account_app.py     # 多账户应用服务
    │   └── dashboard_app.py         # 实时 Dashboard 应用服务
    ├── infrastructure/     # 【基础设施层】脏活累活，外部依赖的具体实现
    │   ├── gateway/        # QMT/xtquant + Tushare 的具体对接实现
    │   ├── mock/           # 回测模拟网关 (MockMarketGateway, MockTradeGateway)
    │   ├── ml_engine/      # ML 模型训练与推理（LightGBM 管道、特征工程、因子挖掘）
    │   ├── factor_test/    # 因子检验基础设施（IC 计算、衰减分析、分层回测）
    │   ├── event_bus/      # 进程内事件总线实现 (基于 asyncio.Queue)
    │   ├── persistence/    # SQLite 持久化 + 内存策略池仓储
    │   │   ├── event_store.py       # SQLiteEventStore 事件存储
    │   │   ├── unit_of_work.py      # SQLiteUnitOfWork 事务管理
    │   │   └── repositories/        # OrderRepository、SnapshotRepository、AuditLogRepository
    │   ├── notification/   # 通知实现（Console、企业微信、邮件、Telegram、Webhook）
    │   ├── snapshot/       # 快照存储
    │   ├── web/            # Web 基础设施（Token 认证、Dashboard、WebSocket）
    │   │   ├── websocket_manager.py      # WebSocket 管理器
    │   │   └── dashboard_data_provider.py # Dashboard 数据提供者
    │   ├── visualization/  # 回测结果图表绘制 + 策略对比可视化
    │   ├── logging/        # 回测进度日志
    │   └── config/         # 配置加载与管理（YAML + 环境变量替换 + 热更新）
    │       ├── settings.py          # 配置管理
    │       ├── config_watcher.py    # 配置文件监听器
    │       └── config_hot_reload.py # 配置热更新服务
    └── interfaces/         # 【用户接口层】系统出入口
        ├── api/            # API 路由定义 (FastAPI: backtest、account 端点)
        │   └── routes/     # 路由模块（含 Dashboard WebSocket 路由）
        ├── cli/            # 命令行入口模块
        │   ├── commands/   # 结构化子命令（backtest、compare、factor_test、live、research）
        │   └── signal_review/ # 信号审核 CLI（增强显示、审核存储、审核 UI）
        └── events/         # 外部回调接收器
```

### 3.1 子域内部结构规范

每个子域必须有一个对应的目录，目录名就是子域的名称。每个目录下按需包含以下包：

1. **entities 包**: 定义该子域的核心实体（如 Account, Position, Order, StrategyPoolEntry 等），每个实体必须是一个独立的 Python 模块。实体是充血模型，包含状态转换方法（如 `Order.submit()`, `StrategyPoolEntry.activate()`）和业务规则校验。
2. **value_objects 包**: 定义该子域的不可变值对象（如 Price, Volume, Bar, Signal, RiskCheckResult, NotificationMessage 等），每个值对象必须是一个独立的 Python 模块。值对象使用 `frozen=True` 确保不可变性。
3. **services 包**: 实现该子域的业务逻辑。接口/基类（如 `BaseStrategy`, `BaseRiskPolicy`, `BaseAnomalyDetector`）直接放在 services 下，具体实现放在子包中（如 `strategies/`, `risk_policies/`, `sizers/`, `allocation_algorithms/`, `rebalance_triggers/`, `alert_rules/`, `anomaly_detectors/`, `portfolio/`）。
4. **interfaces 包**: 定义该子域的外部依赖接口（Protocol 类），根据功能不同，可分为以下子目录：
   * **gateways 包**: 网关接口（如 `ITradeGateway`, `IMarketGateway`, `IAccountGateway`, `INotificationGateway` 等）。回测专用接口通过组合继承扩展（如 `IBacktestBroker` 组合了 `ITradeGateway` + `IAccountGateway`）。
   * **repositories 包**: 仓储接口（如 `IAccountRepository`, `ITradeHistoryRepository`, `IStrategyPoolRepository` 等）。

### 3.2 关键接口组合模式

回测场景中，`IBacktestBroker`（定义在 `src/domain/backtest/interfaces/gateways/`）通过多重继承组合 `ITradeGateway` + `IAccountGateway`，并扩展 `list_orders()`、`create_sub_account()` 等回测专用方法。`MockTradeGateway` 在 infrastructure 层同时实现这些接口，避免接口碎片化。

### 3.3 跨子域通信模式

子域之间通过接口解耦，禁止直接依赖具体实现：

* **risk → notification**: 通过 `IRiskNotifier` 接口（定义在 `src/domain/risk/interfaces/notification.py`），由 `RiskNotifierAdapter`（infrastructure 层）桥接到 `INotificationGateway`。
* **risk → account/market**: 通过构造函数注入 `IAccountGateway`、`IMarketGateway` 等接口。
* **strategy → ml_engine**: 通过 `IInferenceEngine` 接口（定义在 `src/domain/strategy/interfaces/inference_engine.py`），ML 具体实现在 infrastructure 层。

## 4. A 股领域知识建模规范 (Domain Knowledge Constraints)

在设计领域模型（Domain Model）及实现回测/实盘网关（Gateway）时，必须严格内置以下 A 股特定业务规则，以确保回测与实盘逻辑的一致性：

### 4.1 核心结算与资产规则

1. **T+1 结算规则**: `Position` (持仓实体) 必须明确区分 `total_volume` (总持仓) 和 `available_volume` (可用持仓)。当日买入成交后，只能增加 `total_volume`，不可增加 `available_volume`（当日不可卖）。日终通过 `settle_t_plus_1()` 方法将 `available_volume` 同步为 `total_volume`。
2. **资金冻结规则**: `Asset` (资产实体) 必须包含 `total_asset` (总资产)、`available_cash` (可用资金) 和 `frozen_cash` (冻结资金)。`Order` 提交（SUBMITTED）时必须立即计算并转移资金至 `frozen_cash`，成交（FILLED）或撤单（CANCELED）时进行对应的解冻与扣减。提供 `freeze_cash()`、`unfreeze_cash()`、`deduct_frozen_cash()` 三个独立方法。
3. **订单状态机**: `Order` 实体的 `status` 必须遵循严格的单向状态扭转，禁止逆向修改：
   * `CREATED` (已创建) -> `SUBMITTED` (已报)
   * `SUBMITTED` -> `PARTIAL_FILLED` (部成) / `FILLED` (已成) / `CANCELED` (已撤) / `REJECTED` (废单)
   * `PARTIAL_FILLED` -> `FILLED` / `PARTIAL_CANCELED` (部成撤)
   * 实现中使用 `match/case` 语法处理状态流转逻辑。
4. **价格与数量约束**:
   * 买入申报数量必须为 100 的整数倍（一手）。
   * 所有的行情特征计算（Indicator Calculation）必须强制使用 **前复权 (Forward Adjusted)** 数据。

### 4.2 真实交易成本建模 (Transaction Costs)

严禁在回测中使用"无摩擦"假设。无论是实盘资金计算还是回测模拟撮合，必须内置以下计算逻辑（费率通过 `CostsSettings` 配置化）：

1. **佣金 (Commission)**: 买卖双向收取，默认费率万分之 2.5 (0.00025)，且**单笔最低收取 5 元**（此规则用于滤除在实盘中无法获利的无效微利信号）。
2. **印花税 (Stamp Duty)**: 仅在**卖出**时单向收取，默认千分之 1 (0.001)。
3. **过户费 (Transfer Fee)**: 买卖双向收取，默认十万分之 1 (0.00001)。

### 4.3 滑点与流动性惩罚模型 (Slippage & Liquidity)

为弥合历史回测与真实交易的鸿沟，回测网关（Mock Gateway）必须实现以下机制：

1. **价格滑点 (Price Slippage)**:
   * 模拟买入实际成交价 = `参考价 * (1 + slippage)` (默认向上偏移 0.1%)。
   * 模拟卖出实际成交价 = `参考价 * (1 - slippage)` (默认向下偏移 0.1%)。
2. **成交容量限制 (Capacity Limit)**:
   * 必须校验订单体积对盘口的冲击。单笔订单的 `volume` 默认不得超过当前行情 K 线总 `volume` 的 10%。
   * 若超出，超出部分必须标记为未能成交（`PARTIAL_CANCELED`），严禁在无流动性的假定下完成巨额成交。
3. **涨跌停校验**: 回测时必须通过 `PriceLimit` 值对象校验成交价是否在涨跌停范围内，触及涨跌停的订单标记为 `REJECTED`。

### 4.4 复权价与真实成交价分离

1. **策略计算使用复权价**: K 线 `Bar` 实体的 `open/high/low/close` 字段存储前复权价格，保证策略指标的连续性。
2. **账户结算使用不复权价**: `Bar.unadjusted_close` 字段存储真实成交价（不复权），`MockTradeGateway._simulate_fill()` 中以此计算费用和更新账户资产。
3. **收盘强制撤单**: 在跨日回测时，所有未成交订单（`SUBMITTED`, `PARTIAL_FILLED`）在每日收盘后必须强制流转为 `CANCELED` 状态，模拟 A 股当日有效的报单机制。由 `DailySettlementService.process_daily_settlement()` 统一处理。

## 5. 策略子域 (Strategy Subdomain)

`src/domain/strategy/` 是系统最大的子域，包含策略信号生成、因子体系、策略池管理等完整能力。

### 5.1 策略类型体系

1. **时序策略 (Bar Strategy)**: 继承 `BaseStrategy`，基于 K 线时间序列生成信号。实现：`DualMaStrategy`、`MicroValueStrategy`。
2. **截面策略 (Cross-Sectional Strategy)**: 继承 `CrossSectionalStrategy`，基于全市场日频快照（`StockSnapshot`）产出批量信号。实现：`MultiFactorStrategy`、`MlReturnPredictionStrategy`。
3. **ML 策略**: 通过 `IInferenceEngine` 接口调用 ML 模型推理结果生成信号。

### 5.2 因子体系

`src/domain/strategy/factors/` 定义了多种因子（均实现 `Factor` Protocol）：

* **价值因子** (`value_factor.py`): PE、PB、PCF、PS、股息率
* **质量因子** (`quality_factor.py`): ROE、ROA、毛利率、净利率、资产周转率
* **技术因子** (`technical_factors.py`): RSI、MACD、均线、ATR
* **价量因子** (`price_volume_factors.py`): 收益率、波动率、换手率、偏度、非流动性
* **反转因子** (`reversal_factor.py`): 短期反转
* **低波因子** (`low_volatility_factor.py`): 低波动异象
* **基本面因子** (`fundamental_factors.py`): 营收增长、利润增长、现金流
* **挖掘因子** (`mined_factor.py`): 因子挖掘产出的合成因子

**FactorScorer** 提供 `percentile_rank()`（百分位排名）和 `weighted_combine()`（加权合成）工具方法。

### 5.3 因子表达式检验

`src/domain/strategy/factor_test/` 提供因子表达式的定义和求值能力（纯 domain 层）：

* **Lexer/Parser**: 将因子表达式字符串解析为 AST（支持算术运算、截面函数 `rank`/`zscore`、一元函数 `abs`/`log`/`sign`）
* **FactorExpressionEvaluator**: 对 AST 求值，输出每只股票的因子值
* **Scorer/Report**: 因子评分与报告生成

### 5.4 信号过滤器

`src/domain/strategy/services/filters/` 提供截面策略的股票池过滤：

* `filter_st`: 排除 ST/\*ST 股票
* `filter_penny_stock`: 排除低价股
* `filter_new_listing`: 排除次新股
* `filter_trading_status`: 排除停牌/退市股
* `filter_quality`: 保留 ROE > 中位数 且 OCF > 0 的标的

### 5.5 策略池管理

`src/domain/strategy/pool/` 管理策略的完整生命周期：

* **StrategyPoolEntry**: 充血实体，状态机 `CANDIDATE → ACTIVE → PAUSED/SUSPENDED → RETIRED`
* **RatingEngine**: 基于 Sharpe Ratio、最大回撤、胜率计算综合评分 (0-100)，映射到 A/B/C/D 评级
* **PoolManager**: 协调注册、评估、自动下线检查
* **MLModelVersion**: ML 模型版本元数据（不可变值对象），支持 `with_active()` 切换活跃版本和 `rollback_model_version()` 回滚

## 6. 风控子域 (Risk Subdomain)

`src/domain/risk/` 提供多层风控能力，从逐单拦截到组合级监控。

### 6.1 逐单风控 (Per-Order Risk Control)

* **RiskChain**: 责任链模式，按顺序执行多个风控策略，任一不通过即拦截
* **风控策略实现**:
  - `SimpleRiskPolicy`: 基础风控
  - `HardStopLossPolicy`: 硬止损
  - `DailyLossPolicy`: 单日亏损限制
  - `DrawdownPolicy`: 回撤限制
  - `PositionLimitPolicy`: 单标的仓位限制
  - `TotalPositionPolicy`: 总仓位限制
  - `LimitUpBreakPolicy`: 涨停板打开拦截

### 6.2 系统级风控 (System-Level Risk Gate)

* **SystemRiskGate**: 盘前系统级风控门禁，基于指数 MA20 判定当日是否允许买入。SELL 信号不受此门禁影响。

### 6.3 熔断器 (Circuit Breaker)

* **CircuitBreaker**: 组合级熔断机制，状态机 `NORMAL → TRIGGERED → COOLDOWN → NORMAL`
  - 触发条件: 单日亏损超限 / 总回撤超限
  - TRIGGERED 状态: 禁止所有交易
  - COOLDOWN 状态: 次日进入冷却期，仅允许卖出
  - 自动恢复: 冷却期结束后恢复 NORMAL

### 6.4 告警引擎 (Alert Engine)

* **AlertEngine**: 基于 `AlertRule` Protocol 的规则引擎
* **告警规则**: `ConcentrationRule`（集中度）、`DailyLossRule`（日亏损）、`PositionRatioRule`（仓位比例）、`StockLossRule`（个股亏损）

### 6.5 异常检测 (Anomaly Detection)

* **BaseAnomalyDetector**: 异常检测器基类
* **检测器实现**:
  - `StrategyAnomalyDetector`: 策略异常（胜率过低、连续亏损）
  - `DataAnomalyDetector`: 数据异常（价格跳变、成交量异常）
  - `MarketAnomalyDetector`: 市场异常（指数暴跌）
  - `MlModelAnomalyDetector`: ML 模型异常（预测漂移）
* **自动动作**: `AnomalyEvent.auto_action` 字段指定 `PAUSE_ALL`（全部暂停）或 `PAUSE_STRATEGY`（单策略暂停）

### 6.6 组合级风控 (Portfolio Risk)

* **PortfolioRiskService**: 组合风险汇总
* **CorrelationAnalyzer**: 持仓相关性分析
* **DiversificationEvaluator**: 分散度评估
* **PortfolioVaRCalculator**: VaR 计算
* **StressTestRunner**: 压力测试运行器（含历史情景和假设情景）
* **MlModelRiskMonitor**: ML 模型风险监控

### 6.7 风控事件分发

* **RiskEventDispatcher**: 将 `RiskEvent` 广播给所有已注册的 `IRiskNotifier`，通知失败不阻塞交易

## 7. 仓位管理与资金分配子域 (Portfolio Subdomain)

`src/domain/portfolio/` 负责将策略信号转换为具体的目标交易量，并管理多策略间的资金分配。

### 7.1 仓位计算 (Position Sizing)

* **IPositionSizer**: 仓位计算接口，`calculate_target(signal, current_price, asset, position) -> int`
* **内置 Sizer**:
  - `FixedRatioSizer`: 固定比例仓位管理器
  - `EqualWeightSizer`: 等权仓位管理器
  - `KellySizer`: 凯利公式仓位管理器

### 7.2 资金分配 (Capital Allocation)

* **CapitalAllocationEngine**: 协调分配算法和再平衡触发
  - 约束: `max_single_weight`(单策略最大权重)、`min_single_weight`(单策略最小权重)、`max_weight_change`(单次最大权重变化幅度)
  - 冷启动保护: 新策略默认权重上限 20%
  - 绩效不足时回退等权分配
* **IAllocationAlgorithm**: 分配算法接口
  - `EqualWeightAllocation`: 等权分配
  - `SharpeWeightAllocation`: 夏普加权
  - `RiskParityAllocation`: 风险平价
  - `KellyAllocation`: 凯利分配
* **IRebalanceTrigger**: 再平衡触发接口
  - `DailyTrigger` / `WeeklyTrigger` / `MonthlyTrigger`

### 7.3 关键实体与值对象

* **OrderTarget**: 订单目标值对象，封装信号到目标持仓量的映射
* **StrategyAllocation**: 策略资金分配结果
* **StrategyPerformance**: 策略绩效数据
* **AllocationResult**: 分配计算结果
* **RebalanceFrequency**: 再平衡频率枚举

## 8. 通知子域 (Notification Subdomain)

`src/domain/notification/` 定义通知的领域抽象，与具体渠道解耦。

* **INotificationGateway**: 通知网关接口，`send()` / `send_batch()`
* **NotificationMessage**: 不可变值对象，包含 `title`、`body`、`level`(INFO/WARNING/CRITICAL/EMERGENCY)、`category`(trade/risk/anomaly/system)、`timestamp`、`metadata`

## 9. 回测应用服务流程 (BacktestAppService)

`BacktestAppService.run_backtest()` 是回测的核心编排方法，完整流程如下：

1. **数据准备** (`prepare_data`): 通过 `IHistoryDataFetcher` 拉取历史 K 线，加载到 `IBacktestMarketGateway`。
2. **多策略支持**: 支持传入 `list[BaseStrategy]`，为每个策略创建子账户并独立运行回测，最终返回 `list[BacktestReport]`。
3. **回测主循环** (每个交易日):
   a. `market_gateway.set_current_time()` — 推进到当前时间
   b. `market_gateway.get_recent_bars()` — 获取回溯窗口内的 K 线（默认 101 根）
   c. `strategy.generate_signals()` — 策略生成交易信号
   d. `status_registry.is_tradable()` — 停牌/退市检查
   e. `sizer.calculate_target()` — 仓位计算
   f. `trade_gateway.place_order()` — 下单并模拟撮合
   g. `settlement_service.process_daily_settlement()` — 日终结算（撤单 + T+1 释放）
   h. `_record_snapshot()` — 记录每日资产快照
4. **双模式驱动**:
   * 同步模式（默认）: 直接在 for 循环中执行上述步骤。
   * EventBus 模式 (`use_event_bus=True`): 通过 `EventBus` 发布 `MarketTickEvent` 和 `DailySettlementEvent`。
5. **绩效评估**: `PerformanceEvaluator.evaluate()` 汇总快照和成交记录，生成 `BacktestReport`。
6. **策略对比**: `ComparisonReportService` 支持多策略对比，生成 `ComparisonReport`。
7. **可视化**: 可选调用 `BacktestPlotter.plot()` 或 `ComparisonPlotter` 绘制收益曲线。

## 10. 自动交易引擎 (AutoTradingEngine)

`AutoTradingEngine` 是实盘自动交易的核心编排器，运行在守护线程中：

1. **启动流程**: `start()` 启动守护线程，按 `check_interval_seconds`（默认 60 秒）轮询
2. **交易循环** (`run_cycle`):
   a. 检查是否启用（`AutoTradingConfig.enabled`）
   b. 异常检测前置检查（`AnomalyDetector.run_checks()`）
   c. 逐策略评估，跳过已暂停策略（`AutoPauseManager.is_strategy_paused()`）
   d. 全局熔断检查（`AutoPauseManager.is_all_paused`）
   e. 信号管线处理（`SignalPipeline.process()`：去重 → 置信度过滤 → 冲突解决 → 转换）
   f. 单次循环最大下单数限制（`max_orders_per_cycle`）
   g. 自动下单（`OrderExecutor.execute()`）
   h. 执行质量记录（`ExecutionMonitor.record()`）
   i. 推送通知（`NotificationHub.notify_trade_executed()`，带脱敏）
3. **交易时段判断**: 仅在 9:25-11:30 和 13:00-15:00 执行
4. **执行时间匹配**: 只在配置的 `execution_times`（如 09:35、14:50）执行
5. **自动暂停**: 异常事件触发 `AutoPauseManager`，支持单策略暂停和全部暂停
6. **状态持久化**: `AutoPauseManager` 将暂停状态持久化到 JSON 文件，附带 HMAC 签名校验

## 11. 事件总线 (EventBus)

`src/infrastructure/event_bus/` 提供进程内异步事件驱动能力：

1. **EventBus**: 基于 `asyncio.Queue` 的发布/订阅实现，支持 `publish()` 和 `subscribe()`。
2. **事件类型** (`events.py`): `MarketTickEvent`（行情推进）、`DailySettlementEvent`（日终结算）。
3. **处理器** (`handlers.py`): 各步骤的业务处理逻辑注册为事件处理器。
4. **当前状态**: EventBus 模式作为可选开关（`use_event_bus=True`），同步循环仍为默认路径，两者共享核心逻辑。

## 12. 配置管理 (Configuration)

`src/infrastructure/config/settings.py` 提供统一的配置管理，支持 YAML 文件 + 环境变量替换：

### 12.1 配置结构

```python
AppSettings
├── backtest: BacktestSettings        # 回测参数
├── strategy: StrategySettings        # 策略参数
├── position_sizing: PositionSizingSettings  # 仓位参数
├── qmt: QmtSettings                  # QMT 连接参数
├── data: DataSettings                # 数据源参数（含 Tushare token）
├── risk: RiskSettings                # 风控参数
│   ├── system_gate: SystemGateSettings     # 系统门禁
│   ├── stop_loss: StopLossSettings         # 止损
│   ├── circuit_breaker: CircuitBreakerSettings  # 熔断器
│   └── notification: NotificationSettings  # 通知配置
│       ├── wechat: WeChatNotificationSettings
│       └── email: EmailNotificationSettings
├── costs: CostsSettings              # 交易成本（费率配置化）
├── live_trade: LiveTradeSettings     # 实盘交易参数
├── monitor: MonitorSettings          # 监控参数（含告警阈值）
├── auto_trade: AutoTradeSettings     # 自动交易参数
├── anomaly: AnomalySettings          # 异常检测参数
└── auto_notification: AutoNotificationSettings  # 自动通知（含 Telegram）
```

### 12.2 配置加载

* `load_backtest_config()`: 从 `resources/backtest.yaml` 加载回测配置
* `load_trading_config()`: 从 `resources/trading.yaml` 加载实盘配置
* 环境变量替换: YAML 中 `${VAR}` 占位符自动替换为环境变量值

## 13. ML 引擎 (ML Engine)

`src/infrastructure/ml_engine/` 提供 ML 模型的训练、推理和特征工程能力（属于基础设施层，可使用第三方库）：

### 13.1 训练管道

* **TrainingPipeline**: LightGBM Walk-Forward 滚动训练
  - 支持 Optuna 超参优化
  - Embargo 窗口防止信息泄露
  - fillna 只用训练集中位数，避免测试集信息泄露
  - 模型保存为 joblib 格式，附带 metadata.json
* **LGBMConfig**: LightGBM 训练配置（可序列化为参数字典）

### 13.2 特征工程

* **FeaturePipeline**: 特征提取管道
* **FeatureTransforms**: `extract_base_features()` → `compute_derived_features()` → `cross_section_standardize()`
* **LabelGenerator**: 前瞻收益标签生成（支持 winsorize）
* **FeatureCombiner**: 多源特征组合
* **TimeSeriesCV**: 时间序列交叉验证
* **CollinearityFilter**: 共线性过滤

### 13.3 因子挖掘

* **FactorMiner**: 自动因子挖掘
* **FactorEvaluator**: 因子评估
* **FactorRepository**: 因子持久化

### 13.4 推理与模型管理

* **InferenceEngine**: 实现 `IInferenceEngine` 接口，提供 `predict_batch()`
* **ModelLoader**: 模型加载（LightGBM joblib 格式）
* **ModelRegistry**: 模型注册与版本管理
* **Evaluator**: 模型评估

## 14. 因子检验基础设施 (Factor Test Infrastructure)

`src/infrastructure/factor_test/` 提供因子 IC 检验和分层回测能力：

* **ICCalculator**: 因子 IC 值计算（Rank IC / Normal IC）
* **DecayAnalyzer**: 因子衰减分析（IC 随时间衰减）
* **LayerBacktest**: 分层回测（按因子值分 N 层，每层独立回测）
* **TestRunner**: 因子检验运行器

## 15. 通知基础设施 (Notification Infrastructure)

`src/infrastructure/notification/` 提供多渠道通知实现：

* **ConsoleNotifier**: 控制台输出
* **WeChatNotifier**: 企业微信 Webhook 通知
* **EmailNotifier**: SMTP 邮件通知
* **TelegramGateway**: Telegram Bot 通知
* **RiskNotifierAdapter**: 桥接 `IRiskNotifier` → `INotificationGateway`
* **Factory**: `create_notifiers()` / `create_notification_gateway()` 根据配置自动创建通知渠道

### 15.1 通知中心 (NotificationHub)

* **频率限制**: `RateLimiter` 限制每分钟最多 N 条通知
* **静默时段**: 配置 `quiet_hours`（如 23:00-07:00），静默时段跳过非紧急通知
* **EMERGENCY 级别**: 不受静默时段限制
* **脱敏**: `notify_trade_executed()` 支持 `sanitize=True` 模式

## 16. Web 安全 (Web Security)

`src/infrastructure/web/` 提供 API 安全能力：

* **TokenAuth**: Token 认证中间件，支持静态 Token 和 HMAC 比较（`hmac.compare_digest` 防时序攻击）
* **日志脱敏**: `mask_sensitive()` 方法遮盖账户 ID 等敏感信息

## 17. StockSnapshot 数据模型

`StockSnapshot` 是截面策略和因子体系的核心输入，将 Bar + 基本面数据合并为统一视图：

* 内部拆分为 3 个不可变子对象: `PriceVolumeData`、`FundamentalData`、`TechnicalIndicators`
* 通过 `__getattr__`/`__setattr__` 保持向后兼容的 flat 访问模式
* 支持价量（close/open/high/low/volume/turnover_rate）、基本面（market_cap/roe_ttm/pe_ratio/pb_ratio 等）、技术指标（return_5d/volatility_20d/rsi_14/macd 等）三大类字段

## 18. AI 执行协议 (AI Workflow Protocol)

每次接收到新任务时，AI 需按以下步骤执行：

1. **分析**: 确认该任务属于 DDD 的哪一层，并简述设计思路。
2. **编码**: 按照 `ARCHITECTURE.md` 的要求编写高质量代码。
3. **自检**: 生成完毕后，自行核对是否违反了上述红线（如：是否在 domain 层 import 了 xtquant/duckdb 等副作用库）。若有违反，立即自行修正。

## 19. Python 现代编码风格与规范 (Modern Coding Conventions)

为了保持代码库的极高可读性、执行性能和前沿性，本项目全面拥抱 Python 3.13+ 的现代特性。AI 在生成代码时必须严格遵循以下风格：

1. **现代类型注解 (Advanced Type Hinting)**:
   - **全面弃用**旧版 `typing` 模块中的大写集合（如 `List`, `Dict`, `Union`, `Optional`）。
   - 强制使用内置泛型和管道符：`list[str]`, `dict[str, int]`, `str | None`。
   - 在返回类实例自身时，强制使用 `typing.Self`。

2. **高性能数据类 (Modern Dataclasses)**:
   - 领域实体（Entities）使用 `@dataclass(slots=True, kw_only=True)`。
   - 值对象（Value Objects）使用 `@dataclass(frozen=True, slots=True, kw_only=True)` 确保不可变性。
   - `slots=True`：彻底杜绝动态字典，极致优化海量持仓/订单对象的内存占用。
   - `kw_only=True`：强制要求实例化时必须使用关键字传参，彻底杜绝参数错位导致的致命交易 Bug。

3. **结构化模式匹配 (Structural Pattern Matching)**:
   - 在处理复杂的领域状态机（如 `Order` 的状态流转、表达式求值分支）或事件路由时，**优先使用 `match / case` 语法**，替代冗长且易错的 `if-elif-else`。

4. **严格的命名与格式化 (PEP 8 严格模式)**:
   - 默认以 **Ruff** 和 **Black** 为隐式代码格式化标准。单行代码长度限制建议为 120 字符。
   - 类名使用 `PascalCase`；函数、变量、方法使用 `snake_case`；全局常量使用 `UPPER_SNAKE_CASE`。
   - 模块内部私有属性/方法严格使用单下划线前缀 `_`，绝不允许滥用双下划线 `__`（除非为规避命名冲突）。

5. **异常处理与错误边界 (Error Handling)**:
   - 绝不允许出现 bare `except:` 或 `except Exception: pass`。
   - 必须捕获具体的异常类型。在基础设施层捕获到第三方异常后，必须将其包装为领域层自定义的异常（如 `raise OrderSubmitError from e`）再向上抛出。
   - 领域层异常定义在各子域的 `exceptions.py` 中（如 `src/domain/trade/exceptions.py`、`src/domain/account/exceptions.py`）。

6. **专业文档字符串 (Docstrings)**:
   - 所有公共模块、类、复杂的领域方法必须包含 **Google Style** 的 Docstring。
   - 必须明确标注 `Args:`（参数说明）、`Returns:`（返回值说明）以及可能抛出的 `Raises:`（异常说明）。

7. **严格的模块导入规范 (Import Rules)**:
   - **包外依赖（跨层/跨模块调用）必须绝对导入**：例如在 `infrastructure` 层调用 `domain` 层，必须使用 `from src.domain.trade.entities.order import Order`，严禁使用相对导入。
   - **包内依赖（同包兄弟模块调用）推荐相对导入**：例如在 `src/infrastructure/gateway/` 内的 `qmt_trade.py` 调用同目录的 `xtquant_client.py`，必须使用 `from .xtquant_client import xtdata`，以保持包的内聚性和重构友好度。

## 20. 单元测试规范 (Unit Testing Standards)

本项目采用业内最先进的 Python 测试框架 `pytest`，并严格遵守工业级测试规范。测试代码的质量必须等同甚至高于生产代码。

1. **核心原则 (The FIRST Principle)**:
   - **Fast (快速)**: 测试必须秒级运行完毕。
   - **Isolated (隔离)**: 测试用例之间绝对独立，禁止共享状态或依赖执行顺序。涉及 `infrastructure` 层的外部网络调用或 QMT 客户端连接，**必须使用 `pytest-mock` 进行拦截和 Mock**。
   - **Repeatable (可重复)**: 在任何环境、任何时间运行的结果必须完全一致。
   - **Self-validating (自我验证)**: 测试只允许输出 Pass/Fail，禁止需要人工肉眼比对 Print 日志。
   - **Thorough (全面)**: 关键业务流（如资金冻结、订单状态机、策略池状态机、熔断器状态机）必须覆盖边界条件和异常分支。

2. **AAA 结构模式 (Arrange-Act-Assert)**:
   - 每个测试用例内部必须清晰划分三个逻辑块，并建议用空行或注释隔开：
     1. `Arrange`: 准备 Mock 数据、实例化实体、设置初始状态。
     2. `Act`: 调用被测方法。
     3. `Assert`: 严格断言返回值或状态的改变。

3. **极致语义化的命名规范 (Descriptive Naming)**:
   - 测试文件、类、函数强制使用 `snake_case`。
   - 测试函数命名规范必须严格遵循公式：`test_<待测方法名>_<特定场景>_<预期行为>`。
   - ❌ 错误示例：`test_order_logic()` (毫无信息量)
   - ✅ 正确示例：`test_apply_trade_with_partial_fill_should_update_filled_volume_and_keep_submitted_status()`

4. **DDD 各分层的测试策略**:
   - **领域层 (Domain)**: 要求极高的测试覆盖率（目标 90%+）。因为是纯粹的业务逻辑（无外部依赖），此类测试**完全不需要也不允许 Mock**。重点死磕 `Position` 的 T+1 变更、`Order` 的状态机、`StrategyPoolEntry` 的状态机、`CircuitBreaker` 的状态机。
   - **应用层 (Application)**: 重点测试业务流编排。必须完整 Mock 掉所有的 `Gateway`，验证编排逻辑是否正确调用了各领域服务和基础设施。
   - **基础设施层 (Infrastructure)**: 重点测试防腐层（ACL）的数据转换逻辑（如验证 QMT/Tushare 的数据映射是否正确）和通知渠道的适配逻辑。

5. **目录映射与文件命名规范 (Mirror Directory Structure)**:
   - 测试代码的目录层级必须与源代码 `src/` 下的层级保持 **1:1 绝对镜像映射**。
   - 测试文件的命名规范：必须严格以 `test_` 为前缀，后接对应的源文件名。
   - 举例对照：
     * 源文件：`src/domain/account/entities/asset.py`
     * 测试文件：`tests/domain/account/entities/test_asset.py`
     * 源文件：`src/domain/risk/services/circuit_breaker.py`
     * 测试文件：`tests/domain/risk/services/test_circuit_breaker.py`

6. **测试工具规范**:
   - 优先使用 `Fake` 对象替代 `MagicMock`，使测试更具可读性和可维护性
   - 共享 fixture 放在 `tests/conftest.py` 中

## 21. QMT (xtquant) 数据获取与基础设施规范 (Infrastructure Constraints)

在使用 QMT (`xtquant`) 作为底层数据源或交易网关时，必须严格遵守以下 API 调用规范，以绕过底层 C++ 接口的常见陷阱：

### 21.1 历史行情获取接口规范 (Market Data API)

1. **禁用旧版 API**: 绝对禁止使用 `xtdata.get_market_data()`。该接口返回的数据结构（`{字段: DataFrame}`）极不符合常规数据处理逻辑。
2. **强制使用 EX 接口**: 必须使用 `xtdata.get_market_data_ex()`。该接口返回标准的 `{stock_code: DataFrame}` 结构，且 DataFrame 包含 open, high, low, close, volume 等完整字段。
3. **复权要求**: 在调用接口获取用于回测和技术指标计算的 K 线时，必须强制指定 `dividend_type='front'`（前复权）。

### 21.2 时间格式与解析规范 (Time Format & Parsing)

1. **请求参数时间格式**: QMT 的 C++ 底层对时间字符串要求极其严格。外部传入的 `YYYY-MM-DD` 格式（如 "2024-01-01"）在传递给 `download_history_data` 和 `get_market_data_ex` 之前，**必须**去除横杠，转换为紧凑型的 `YYYYMMDD`（如 "20240101"）或 `YYYYMMDDHHMMSS` 格式。
2. **返回结果时间解析**: `get_market_data_ex` 返回的 DataFrame 中，时间信息通常隐藏在 `index` 中。必须显式使用 `pandas.to_datetime(df.index)` 将其转换为标准的 datetime 对象，再向下游领域模型传递。

### 21.3 透明缓存与多维度隔离 (Transparent Caching)

1. **多粒度文件隔离**: 历史数据落盘保存时，必须将 `symbol` 和 `timeframe` 结合作为联合主键。缓存文件命名规范须为 `data/{symbol}_{timeframe}.csv`（例如 `000021.SZ_1d.csv` 或 `000021.SZ_5m.csv`）。
2. **透明读取机制**: 所有 `IHistoryDataFetcher` 的实现必须是防备性的。在向 QMT 发起耗时的下载请求前，必须先检查本地是否存在对应的缓存文件。若存在，则直接走本地 IO 并解析返回，避免重复调用 QMT 接口。

### 21.4 账户网关无状态连接 (Gateway Connection)

1. **行情模块 (xtdata)**: 纯数据获取属于无状态调用。在代码层面不需要（也不支持）编写连接、登录代码，直接 `import xtdata` 并调用即可。依赖前提是本地终端已开启。
2. **交易模块 (xttrader)**: 必须显式实例化 `XtQuantTrader`，提供 `qmt_path` 和 `session_id`，并严格执行 `connect()` 和 `subscribe()` 的握手流程。

### 21.5 多数据源支持

除 QMT 外，系统还支持 Tushare 数据源：

* **TushareHistoryDataFetcher**: Tushare 历史行情获取（需配置 `tushare.token`）
* **TushareFundamentalFetcher**: Tushare 基本面数据获取
* **TushareIndexFetcher**: Tushare 指数数据获取

## 22. 持久化层 (Persistence Layer)

`src/infrastructure/persistence/` 提供基于 SQLite 和内存的持久化能力：

1. **Database** (`database.py`): SQLite 数据库连接管理与表初始化。
2. **Repositories**:
   - `OrderRepository`（订单仓储）
   - `SnapshotRepository`（日终快照仓储）
   - `MemoryStrategyPoolRepo`（内存策略池仓储，实现 `IStrategyPoolRepository`）
3. **数据隔离**: 每个回测运行使用独立的数据库文件，避免交叉污染。
4. **状态持久化**: `AutoPauseManager` 将暂停状态持久化到 `data/pause_state.json`，附带 HMAC 签名。
5. **信号审核**: `ReviewStore` 持久化信号审核记录到 `resources/signal_reviews/`。

## 23. StockSnapshot 拆分规范

`StockSnapshot` 是截面策略的核心数据模型，必须遵循以下规范：

1. **子对象拆分**: 内部必须拆分为 `PriceVolumeData`、`FundamentalData`、`TechnicalIndicators` 三个不可变子对象，使用 `frozen=True`。
2. **向后兼容**: 通过 `__getattr__`/`__setattr__` 代理实现 flat 访问，避免破坏已有代码。
3. **字段归属**: 新增字段必须归入正确的子对象，不得在 `StockSnapshot` 顶层直接添加。
4. **`**_extra`**: 构造函数必须保留 `**_extra: object` 参数，忽略未知字段，提升数据兼容性。

## 24. ML 模型版本管理规范

1. **MLModelVersion**: 不可变值对象，包含 `version_id`、`model_type`、`trained_at`、`training_samples`、`feature_count`、`metrics`、`is_active`、`notes`。
2. **版本切换**: 通过 `with_active()` 返回新实例，禁止原地修改。
3. **版本回滚**: `rollback_model_version()` 将当前活跃版本设为非活跃，激活前一个版本。
4. **模型文件**: 保存为 `data/factors/models/{name}/model.joblib`，附带 `metadata.json`（含 feature_columns、训练/验证/测试周期、IC 值等）。
5. **horizon 统一**: 训练管道的 `forward_days` 参数必须与标签生成的 `LabelConfig.horizon` 保持一致，避免前瞻期不匹配。

## 25. 事件溯源 (Event Sourcing)

`src/domain/common/` 提供领域事件基类和事件存储能力：

### 25.1 DomainEvent 基类

* **DomainEvent**: 不可变值对象，使用 `@dataclass(frozen=True, slots=True, kw_only=True)`
  - `event_id`: 全局唯一事件 ID (UUID)
  - `event_type`: 事件类型标识（如 "OrderSubmitted"、"CircuitBreakerTriggered"）
  - `aggregate_id`: 聚合根 ID（如 order_id）
  - `aggregate_type`: 聚合根类型（如 "Order"、"CircuitBreaker"）
  - `timestamp`: 事件发生时间（UTC）
  - `payload`: 事件附加数据

### 25.2 事件产出

关键实体状态变更时自动产出领域事件：
* **Order**: `OrderCreated` → `OrderSubmitted` → `OrderFilled` / `OrderCanceled` / `OrderRejected`
* **CircuitBreaker**: `CircuitBreakerTriggered` → `CircuitBreakerCooldown` → `CircuitBreakerRecovered`

### 25.3 EventStore

* **EventStore 协议** (`src/domain/common/event_store.py`): ABC 接口，定义 `append()`、`append_batch()`、`get_events()`、`get_events_by_aggregate()`
* **SQLiteEventStore** (`src/infrastructure/persistence/event_store.py`): 基于 SQLite 的 append-only 实现
  - 支持按 `aggregate_id` / `event_type` / 时间范围查询
  - 索引优化：聚合根、事件类型、时间戳

## 26. 事务管理 (Unit of Work)

`src/domain/common/unit_of_work.py` 提供事务边界保证：

### 26.1 UnitOfWork 协议

* **UnitOfWork**: ABC 接口，上下文管理器模式
  - `__enter__()`: 开启事务
  - `__exit__()`: 自动提交或回滚
  - `commit()`: 手动提交
  - `rollback()`: 手动回滚

### 26.2 SQLiteUnitOfWork

* **SQLiteUnitOfWork** (`src/infrastructure/persistence/unit_of_work.py`): 基于 SQLite 的实现
  - 确保下单→冻结资金→撮合→扣款的原子性
  - 任何一步异常，自动回滚全部操作

## 27. 健康检查与监控 (Health Check)

### 27.1 HealthStatus 值对象

* **HealthStatus** (`src/domain/trade/value_objects/health_status.py`):
  - `status`: healthy / degraded / unhealthy
  - `heartbeat_time`: 最后心跳时间
  - `uptime_seconds`: 运行时长
  - `checks`: 检查项列表

### 27.2 IHealthGateway 接口

* **IHealthGateway** (`src/domain/trade/interfaces/gateways/health_gateway.py`): Protocol 接口
  - `check_heartbeat()`: 检查心跳
  - `get_uptime()`: 获取运行时长
  - `is_alive()`: 检查存活状态

### 27.3 HealthService

* **HealthService** (`src/application/health_service.py`): 应用服务
  - Watchdog 线程监控守护线程存活
  - 心跳写入文件，外部可检测
  - 异常时自动重启 + 通知

## 28. 通知子域扩展 (Notification Extension)

### 28.1 通知优先级

* **NotificationPriority** (`src/domain/notification/value_objects/notification_priority.py`):
  - `EMERGENCY`: 立即发送，不受静默时段限制
  - `CRITICAL`: 立即发送
  - `WARNING`: 队列发送，静默时段延迟
  - `INFO`: 批量合并，每小时摘要

### 28.2 通知去重

* **NotificationDeduplicator** (`src/domain/notification/services/notification_deduplicator.py`):
  - 基于 (title, category, level) 的滑动窗口去重
  - 相同事件 5 分钟内只发送一次
  - 累计计数，最后一次通知中附带"共 N 次"

### 28.3 通知回执

* **NotificationReceipt** (`src/domain/notification/value_objects/notification_receipt.py`):
  - `notification_id`: 通知 ID
  - `sent_at`: 发送时间
  - `delivered`: 是否送达
  - `confirmed`: 是否确认
  - `confirmed_at`: 确认时间
  - EMERGENCY 级别未确认时，5 分钟后重发

### 28.4 通知历史

* **NotificationHistory** (`src/domain/notification/value_objects/notification_history.py`): 通知历史值对象
* **INotificationHistoryRepository** (`src/domain/notification/interfaces/repositories/`): 仓储接口
  - 支持按日期/级别/类别查询
  - 支持统计（发送量、送达率、确认率）

## 29. 审计日志 (Audit Logging)

### 29.1 AuditLogEntry 值对象

* **AuditLogEntry** (`src/domain/common/value_objects/audit_log_entry.py`):
  - `log_id`: 日志 ID
  - `user_id`: 操作用户
  - `action`: 操作类型
  - `resource_type`: 资源类型
  - `resource_id`: 资源 ID
  - `timestamp`: 操作时间
  - `details`: 操作详情
  - `ip_address`: IP 地址

### 29.2 AuditService

* **AuditService** (`src/domain/common/services/audit_service.py`): 领域服务
  - 记录谁在什么时间执行了什么操作
  - 支持按日期/操作类型/用户查询
  - append-only 设计，禁止修改/删除

## 30. 策略生命周期管理 (Strategy Lifecycle)

### 30.1 StrategyLifecycleStatus

* **StrategyLifecycleStatus** (`src/domain/strategy/value_objects/strategy_lifecycle_status.py`):
  - `CANDIDATE`: 候选策略
  - `BACKTESTING`: 回测中
  - `EVALUATING`: 评估中
  - `ACTIVE`: 已上线
  - `PAUSED`: 已暂停
  - `RETIRED`: 已下线

### 30.2 StrategyLifecycleManager

* **StrategyLifecycleManager** (`src/domain/strategy/services/strategy_lifecycle_manager.py`): 领域服务
  - `register_and_backtest()`: 注册新策略并自动回测评估
  - `check_performance()`: 定期检查所有活跃策略表现
  - 与 `CapitalAllocationEngine` 联动
  - 评级下滑后自动降级（ACTIVE → PAUSED）或下线（RETIRED）

## 31. 因子研发流水线 (Factor Pipeline)

### 31.1 FactorLifecycleStatus

* **FactorLifecycleStatus** (`src/domain/strategy/value_objects/factor_lifecycle_status.py`):
  - `DISCOVERED`: 已发现
  - `TESTING`: 检验中
  - `VALIDATED`: 已验证
  - `ACTIVE`: 已上线
  - `DECAYED`: 已衰减
  - `RETIRED`: 已淘汰

### 31.2 FactorPipelineService

* **FactorPipelineService** (`src/domain/strategy/services/factor_pipeline.py`): 领域服务
  - FactorMiner → ICTest → LayerBacktest → 自动入库流程
  - 因子衰减监控 + 自动淘汰
  - 因子组合优化（正交化、逐步回归）

## 32. ML 模型灰度发布 (ML Model Deployment)

### 32.1 ModelDeploymentStrategy

* **ModelDeploymentStrategy** (`src/domain/strategy/value_objects/model_deployment_strategy.py`):
  - `FULL_ROLLOUT`: 全量切换
  - `CANARY`: 金丝雀发布（10% 流量）
  - `SHADOW`: 影子模式（只预测不交易）

### 32.2 ShadowModeService

* **ShadowModeService** (`src/domain/strategy/services/shadow_mode_service.py`): 领域服务
  - 活跃模型产出实际交易信号
  - 影子模型产出预测信号（不执行）
  - 记录两者差异到 `ShadowComparisonLog`
  - 影子模型持续优于活跃模型 → 自动提示升级

### 32.3 漂移自动重训练

* `MlModelAnomalyDetector` 检测到漂移 → 触发 `TrainingPipeline.walk_forward_train()`
* 新模型以 SHADOW 模式部署 → 影子验证通过后 → CANARY → FULL_ROLLOUT

## 33. 盘后自动对账 (Reconciliation)

### 33.1 ReconciliationReport

* **ReconciliationReport** (`src/domain/account/value_objects/reconciliation_report.py`):
  - `report_date`: 对账日期
  - `positions_match`: 持仓是否匹配
  - `cash_match`: 资金是否匹配
  - `differences`: 差异列表
  - `alerts`: 告警列表

### 33.2 ReconciliationService

* **ReconciliationService** (`src/domain/account/services/reconciliation_service.py`): 领域服务
  - 系统持仓 vs 券商持仓对比
  - 资金余额校验
  - 差异自动告警
  - 每日盘后自动执行

## 34. 实时风控 (Realtime Risk)

### 34.1 RiskAlert

* **RiskAlert** (`src/domain/risk/value_objects/risk_alert.py`):
  - `alert_type`: 告警类型
  - `severity`: 严重程度
  - `symbol`: 证券代码
  - `message`: 告警消息
  - `timestamp`: 告警时间
  - `action_required`: 需要的动作

### 34.2 RealtimeRiskMonitor

* **RealtimeRiskMonitor** (`src/domain/risk/services/realtime_risk_monitor.py`): 领域服务
  - Tick 级别价格监控
  - 实时止损检查
  - 异常成交检测

### 34.3 RealtimeStopLoss

* **RealtimeStopLoss** (`src/domain/risk/services/realtime_stop_loss.py`): 领域服务
  - 跟踪持仓价格变化
  - 触发止损时自动下单

## 35. 算法交易 (Algorithmic Trading)

### 35.1 IAlgoTrader 接口

* **IAlgoTrader** (`src/domain/trade/interfaces/gateways/algo_trader.py`): Protocol 接口
  - `execute_algo_order()`: 执行算法订单
  - `cancel_algo_order()`: 取消算法订单

### 35.2 算法策略

* **TWAPStrategy** (`src/domain/trade/services/algo_strategies/twap_strategy.py`): 时间加权平均价格
  - 将大额订单拆分为多个小单，按时间均匀执行
* **VWAPStrategy** (`src/domain/trade/services/algo_strategies/vwap_strategy.py`): 成交量加权平均价格
  - 根据历史成交量分布拆单
* **IcebergStrategy** (`src/domain/trade/services/algo_strategies/iceberg_strategy.py`): 冰山单
  - 隐藏真实意图，只显示部分数量
  - 成交后自动补充挂单

### 35.3 AlgoOrderManager

* **AlgoOrderManager** (`src/domain/trade/services/algo_order_manager.py`): 领域服务
  - 大额订单自动拆分
  - 算法执行进度跟踪
  - 使用 `match/case` 分发策略

## 36. 归因分析 (Attribution Analysis)

### 36.1 BrinsonAttribution

* **BrinsonAttribution** (`src/domain/backtest/services/attribution/brinson_attribution.py`): 领域服务
  - 配置效应（资产配置贡献）
  - 选择效应（个股选择贡献）
  - 交互效应（配置与选择的交互）

### 36.2 FactorAttribution

* **FactorAttribution** (`src/domain/backtest/services/attribution/factor_attribution.py`): 领域服务
  - 收益由哪些因子贡献
  - 因子暴露度分析

### 36.3 AttributionReport

* **AttributionReport** (`src/domain/backtest/value_objects/attribution_report.py`):
  - `total_return`: 总收益
  - `allocation_effect`: 配置效应
  - `selection_effect`: 选择效应
  - `interaction_effect`: 交互效应
  - `factor_contributions`: 因子贡献

## 37. 组合优化 (Portfolio Optimization)

### 37.1 MeanVarianceOptimizer

* **MeanVarianceOptimizer** (`src/domain/portfolio/services/optimization/mean_variance_optimizer.py`): 领域服务
  - 最大夏普比率优化
  - 最小方差优化
  - 约束条件：权重上下限、行业限制

### 37.2 BlackLittermanOptimizer

* **BlackLittermanOptimizer** (`src/domain/portfolio/services/optimization/black_litterman_optimizer.py`): 领域服务
  - 市场均衡收益 + 主观观点
  - 后验收益估计

### 37.3 RiskBudgetOptimizer

* **RiskBudgetOptimizer** (`src/domain/portfolio/services/optimization/risk_budget_optimizer.py`): 领域服务
  - 按风险贡献分配权重
  - 风险平价策略

### 37.4 OptimizationResult

* **OptimizationResult** (`src/domain/portfolio/value_objects/optimization_result.py`):
  - `weights`: 权重分配
  - `expected_return`: 预期收益
  - `expected_risk`: 预期风险
  - `sharpe_ratio`: 夏普比率

## 38. 配置热更新 (Config Hot Reload)

### 38.1 ConfigWatcher

* **ConfigWatcher** (`src/infrastructure/config/config_watcher.py`): 文件监听器
  - 使用 watchdog 监听 YAML 文件变更
  - 文件变更时触发回调

### 38.2 ConfigHotReloadService

* **ConfigHotReloadService** (`src/infrastructure/config/config_hot_reload.py`): 热更新服务
  - 运行时动态调整参数
  - 参数变更审计日志
  - 变更回滚机制

### 38.3 ConfigChangeLog

* **ConfigChangeLog** (`src/domain/common/value_objects/config_change_log.py`):
  - `change_id`: 变更 ID
  - `config_path`: 配置路径
  - `old_value`: 旧值
  - `new_value`: 新值
  - `timestamp`: 变更时间
  - `user_id`: 操作用户

## 39. 多账户支持 (Multi-Account)

### 39.1 AccountGroup

* **AccountGroup** (`src/domain/account/entities/account_group.py`): 账户组实体
  - `group_id`: 组 ID
  - `group_name`: 组名称
  - `accounts`: 账户列表
  - 全局风控视角（跨账户汇总）

### 39.2 MultiAccountService

* **MultiAccountService** (`src/domain/account/services/multi_account_service.py`): 领域服务
  - 策略间资金自动调配
  - 跨账户持仓汇总
  - 跨账户风控检查

## 40. 实时 Dashboard (Realtime Dashboard)

### 40.1 DashboardSnapshot

* **DashboardSnapshot** (`src/domain/backtest/value_objects/dashboard_snapshot.py`):
  - `total_asset`: 总资产
  - `daily_pnl`: 当日盈亏
  - `positions`: 持仓列表
  - `risk_status`: 风控状态
  - `strategy_status`: 策略状态

### 40.2 WebSocketManager

* **WebSocketManager** (`src/infrastructure/web/websocket_manager.py`):
  - 连接管理
  - 消息广播
  - 心跳检测

### 40.3 DashboardDataProvider

* **DashboardDataProvider** (`src/infrastructure/web/dashboard_data_provider.py`):
  - 持仓/盈亏/风控状态实时推送
  - 策略运行状态可视化数据
  - 历史收益曲线数据
