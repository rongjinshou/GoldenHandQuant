# 债务台账 (Debt Ledger)

> **首次生成**: 2026-07-05 | **方法**: 并行扫描 `docs/feat/` 全部 25 个专题目录（约 90 份
> 设计/计划/报告文档）+ `docs/rules/` 规范文档 + 全代码库 TODO/FIXME/XXX/HACK 标记
> （结果：0 处真实代码内标记，债务均以文档形式登记），并对关键结论做了代码现状抽样核实。
>
> **本表是当前已知债务的单一真相源**——历史设计文档各自为政，同一笔债可能在三份不同
> 文档里各说各话（见下方"文档滞后案例"），这正是本表要解决的问题：新发现的债随手加一行，
> 处理完随手把状态改成「已核销」并注明证据，不要只在某个 `docs/feat/MMDD-xxx/` 里悄悄写完就完事。
>
> **状态含义**：待清偿=需要处理的开放项；挂账观察=已知且被判定不影响结论/不构成缺陷的限制，
> 不用修但要记得；已核销=有明确证据关闭；未动工=从设计提出后从未开始实施的远期规划，
> 不是"债"而是"选项"；待勘校=文档本身内容与代码现状不符。

## 一、待清偿 · 资金与正确性（P0）

| 债务 | 描述 | 位置 | 登记日期 | 备注 |
|---|---|---|---|---|
| 债 D2 | 判决闸门阈值在 `verdict.py`、前端 `gates.ts`、CLI 输出三处独立硬编码，无单一真相源 | `docs/feat/0705-verdict-cards/2026-07-05-verdict-cards-design.md` §11 | 2026-06-11 | **✅ 2026-07-05 已核销**: 创建 `gates_config.py` 作为单一真相源，`verdict.py` 改为 import，新增 `/api/meta/gates` 端点，`gates.ts` 改为从 API 动态获取 |
| 真单前置 | `cancel_order` 撤单接口自 R1(0628) 补入协议后，从未经过真实盘中撤单验证 | `docs/feat/0704-live-prereqs/2026-07-04-live-prereqs-report.md` | 2026-07-04 | **🔧 2026-07-05 已增强**: 增加详细日志和 ValueError 分支处理，补充文档注释说明首次真单撤单需人工确认。仍需真实盘中验证 |
| TD-03 | `NotificationFactory.create_notification_gateway()` 无论配置几个通知渠道，永远只取 `notifiers[0]` | `src/infrastructure/notification/factory.py:38` | 2026-05-31 | **✅ 2026-07-05 已核销**: 创建 `CompositeNotificationGateway`，factory 改为遍历所有 notifiers 组合 |
| TD-04 | `RiskEventDispatcher.dispatch()` 用 `except Exception: pass` 吞掉全部通知异常，无日志无告警 | `src/domain/risk/services/risk_event_dispatcher.py:21-22` | 2026-05-31 | **✅ 2026-07-05 已核销**: 添加 `import logging` + `logger.warning()` 记录异常 |
| — | 应用层存在一套完整的 `NotificationHub`（去重/优先级队列/回执/历史，259 行）从未被任何 composition root 实例化接线；生产实际用的仍是更简陋的 `RiskEventDispatcher`/`notification/factory.py` 旧路径（即上方 TD-03/TD-04） | `src/application/notification_hub.py` | 2026-07-05 新发现 | **✅ 2026-07-05 已核销**: 在 `auto_trade.py` 的 `_build_service` 中实例化 NotificationHub，注入 `AutoTradeAppService`，交易执行时通过 `_notify()` 发送通知 |
| 阶段1设计项 | 等权 sizer 满仓边界反复触发"资金不足"（影子盘阶段1留痕 3281 次），需要现金 buffer 或按可用资金缩放，后续三份文档未回应处理结果 | `docs/feat/0626-mainboard-f01-shadow/2026-06-26-mainboard-f01-shadow-report.md` §四 | 2026-06-26 | **✅ 2026-07-05 已核销**: `EqualWeightSizer` 新增 `cash_buffer` 参数(默认 1%)，`calculate_target` 和 `calculate_targets` 均扣除预留现金后再均分 |
| DD-6 | Mock 回测对 ST 股票涨跌停幅度按板块普通比例处理（如 ±10%），未按 ST 应有 ±5%；`is_st` 硬编码 `False` | `docs/feat/0604-backtest-correctness/2026-06-04-backtest-correctness-design.md` §六 | 2026-06-04 | **🔧 2026-07-05 部分实现，未接线**: `MockTradeGateway` 新增 `stock_status_registry` 参数、`get_price_limit_ratio(is_st=...)` 已支持——但 2026-07-05 核实全仓 11 处 `MockTradeGateway(...)` 构造点（`run_backtest.py`/`commands/backtest.py`/`compare_strategies.py`/7 个 scripts）**无一传入** `stock_status_registry`，默认 `None` 下 `is_st` 恒为 `False`，效果等同未修复。根因仍是原 DD-6 指出的"缺真实 ST 数据源"——接口就绪不等于生效，需要接入真实数据源(如从 stock_features/akshare 抓 ST 名单)并在至少 `run_backtest.py`/`commands/backtest.py` 装配 |
| 已登记债 | factor-test 引擎对表达式中缺失的基本面字段静默按 0 分处理，F10（毛利率）曾因此被误判 FAIL | `docs/rules/data-layer.md` §4；`docs/feat/0610-factor-library/2026-06-11-night-round2-report.md` §三 | 2026-06-11 | **🔧 2026-07-05 部分已核销**: 新增 `resolve_and_validate_field_name()`（`field_mapping.py`），对象式/向量化两条求值路径均已接入——**未知字段名**（拼写错误/映射缺失）现在会立即抛 `UnknownFactorFieldError`，回归测试覆盖两条路径。**未覆盖部分**：F10 原始场景是字段名合法但底层数据全链路恒为 0（数据populate问题，非命名问题），这类"已知字段但数据退化"的侦测仍未实现，需要另立面板级数据质量抽查（如整窗口方差=0/全 NaN 告警），本轮未做 |
| 已知限制 | 影子盘不支持守护模式跨日长跑：fundamental as-of 别名只在装配期算一次，跨日会 fault abort | `docs/feat/0626-mainboard-f01-shadow/2026-07-03-phase1-shadow-report.md` §四.1 | 2026-07-04 | **✅ 2026-07-05 已核销**: `LiveSignalService` 新增 `refresh_fundamental_alias()` 方法，每次 cross-sectional scan 前自动刷新别名 |

## 二、待清偿 · 架构与可观测性（P1）

| 债务 | 描述 | 位置 | 登记日期 | 备注 |
|---|---|---|---|---|
| 债 D1 | ticket 手动下单与 auto-trade 自动循环各写一套超时轮询逻辑，行为已分叉（前者不撤单/后者撤单） | `docs/feat/0611-closed-loop/2026-06-11-night-review.md` §二 | 2026-06-11 | **✅ 2026-07-05 已核销**: 抽取共享 `src/domain/trade/services/order_poller.py`（`poll_order_until_terminal`，`cancel_on_timeout` 参数区分两种调用方），`auto_trade_app.py`/`order_ticket_app.py` 均已改用；全套件绿 |
| 债 D3 | 调度器时段判断（9:25）与安全闸时段判断（9:30）用两套独立定义 | 同上 | 2026-06-11 | **✅ 2026-07-05 已核销**: 抽取共享 `src/domain/trade/services/trading_sessions.py`（`CONTINUOUS_SESSIONS` 9:30 起 / `SCHEDULER_SESSIONS` 9:25 起，两套定义集中一处并写明差异原因），`trading_scheduler.py`/`pre_trade_checks.py` 均已改用；刻意保留 5 分钟差异（调度预备 vs 下单强制闸），非"统一成一个值" |
| 债 D4 | 自动循环逐信号候选串行调用行情订阅，每单最坏 3 秒，未批量拉取 | 同上 | 2026-06-11 | **✅ 2026-07-05 已核销**: `run_cycle` 循环前一次性 `get_quotes(symbols)` 批量拉取（已有的批量接口，此前未被此处调用），`_execute_guarded` 改从预取字典查询；批量调用本身包一层 try/except 退化空字典（不炸穿整循环）；测试改用下单网关注入异常验证单笔隔离（原用报价异常，批量后不再适用） |
| 债 D5 | 驾驶舱实盘页每 5 秒全量拉取 5 个端点并全量重渲染；`/backtests` 净值曲线未分页 | 同上 | 2026-06-11 | "runs>30 后处理" |
| 债 D7 | factor-test 相关测试直连真实 `market.duckdb`，与 `data refresh` 并发写锁冲突产生环境性假失败 | `docs/rules/testing.md` §7 | 2026-06-11 | **✅ 已核销(非本轮修复，发现时已解决)**: 2026-07-05 逐一核实全仓引用 `MarketDataStore(`/`DuckDBHistoryDataFetcher(` 的测试文件，全部已用 `tmp_path`/`:memory:` 隔离，无一处直连默认 `data/market.duckdb`。应是后续测试重构顺带解决，未见对应文档专门标注关闭 |
| TD-05 | `StockSnapshot` 用 `__slots__` + `__getattr__`/`__setattr__` 兼容层维持扁平字段访问 | `src/domain/market/value_objects/stock_snapshot.py` | 2026-05-31 | P2 可维护性债；2026-07-05 已核实仍如此 |
| TD-07 | `load_backtest_config()`/`load_trading_config()` 手动解析嵌套字典，易与 `AppSettings` 结构脱节 | `src/infrastructure/config/settings.py` | 2026-05-31 | 2026-07-05 已核实函数仍在 |
| TD-08 | `TrainingPipeline.prepare_dataset()` 隐式依赖 `extract_base_features()` 的字段顺序/来源 | `src/infrastructure/ml_engine/training_pipeline.py` | 2026-05-31 | 2026-07-05 已核实调用仍在 |
| — | `EventStore`（`SQLiteEventStore`）与 `UnitOfWork`（`SQLiteUnitOfWork`）协议与实现均已写好，但从未被 `BacktestAppService`/`AutoTradeAppService` 或任何 composition root 接线使用 | `src/domain/common/event_store.py`、`unit_of_work.py`；`src/infrastructure/persistence/event_store.py`、`unit_of_work.py` | 2026-07-05 新发现 | 与上方 NotificationHub 同一模式：基础设施建好了，没人接线用。不是"没做"，是"做了但没上线" |
| — | 资金分配子系统（`capital_allocation_engine`/`allocation_algorithms`/`strategy_allocation`/`strategy_performance`）Spec3 瘦身后去留未决，两处文档均写"留待下轮评估"，此后无下一轮文档回应 | `docs/feat/0604-spec3-breadth-trim/2026-06-04-breadth-trim-design.md` §10 | 2026-06-04 | — |
| — | CSV/Tushare 旧数据路径与 DuckDB 新数据层长期并存，未做退役清理 | `docs/feat/0611-market-data-store/2026-06-11-market-data-store-design.md` §7/§9 | 2026-06-11 | — |
| 2026-05-31 批次 | 一次代码深度评审记录的架构级问题合集（领域事件缺失、`DailySettlementService` 无测试覆盖、两套通知接口不兼容 `INotificationGateway` vs `IRiskNotifier`、`CircuitBreaker.evaluate()` 依赖哨兵条件静默跳过检查、熔断器状态无持久化、20+ frozen dataclass 含可变默认值、ML 训练管道多项风险等约 20 项 | `docs/feat/0530-system-roadmap/2026-05-31-code-review-{deep-dive,final,report}.md`；`risk-circuit-breaker-design.md` | 2026-05-31 | `code-review-final.md` 自评多数"✅已修复"，但这是 35 天前的自我核验，本轮未逐条独立复核。若近期重启 ML 预测或大改风控链路，建议先抽样验证 |

## 三、挂账观察（已知且接受的限制，非缺陷）

| 事项 | 描述 | 位置 | 裁定日期 |
|---|---|---|---|
| 单一 OOS regime | F01+趋势闸的 OOS 验证窗口只覆盖一段小盘牛市，结论建立在单一样本上 | `docs/feat/0626-mainboard-f01-shadow/design.md` §六；`docs/feat/0704-b1-delisted-backfill/report.md` §四（二次重申） | 2026-06-26 / 2026-07-04 |
| B1 残余近似 | 退市股回填市值是近似值（不复权价×最近报告期股本）；历史更名不可得；9 只缺席；2021 年前窗口外 | `docs/feat/0704-b1-delisted-backfill/2026-07-04-b1-delisted-backfill-report.md` §四 | 2026-07-04 |
| 实盘 fundamental T-1 | 继续用 T-1 as-of 近似，非实时市值；已重新评估裁定"不升级"，留有触发条件（比对持续隔夜错位） | `docs/feat/0704-live-prereqs/2026-07-04-live-prereqs-design.md` DD-3 | 2026-07-04 |
| 债 D6 | 深市 002/003 序列不在 v1 实盘白名单；`check_symbol_scope` 只放行 60xxxx/000xxx/001xxx | `src/domain/trade/services/pre_trade_checks.py:32-38`；`docs/rules/live-trading.md` §2 | 核实于 2026-07-05 |
| `_scan_bar` 分叉 | 实盘时序策略路径未被"回测/实盘决策核心归一"重构统一，裁定为"正当执行层边界" | `docs/feat/0628-backtest-live-unification/2026-06-28-report.md` §四 | 2026-06-30 |
| 微服务拆分 | 评估结论"非紧迫需求"，四阶段迁移计划全部暂缓 | `docs/feat/0601-microservice-assessment/2026-06-01-microservice-assessment-design.md` §9 | 2026-06-01 |
| `factor_pipeline.py` | 手写高斯消元是风格债，YAGNI 原则下暂不重构，待因子规模扩大出现性能瓶颈再评估 | `docs/feat/0604-spec2-architecture-governance/2026-06-04-architecture-governance-design.md` §七 | 2026-06-04 |
| 通知不重试 | 风控通知失败静默不重试，是主动设计（"避免通知风暴"），非疏漏 | `docs/feat/0530-system-roadmap/2026-05-31-risk-circuit-breaker-design.md` §3.6 | 2026-05-31 |
| DuckDB 单写者 | 回测期间不可并发跑 refresh/factor-test，无代码层强制防护，需人工遵守（违反时抛异常非静默） | `docs/rules/data-layer.md` §3 | 2026-06-11 |
| 债 L3 | `excess_ir` 隐含日超额 IID 假设，N 日调仓自相关会使 IR 虚高（估算真值 0.7–0.9，仍超阈值 0.50） | `docs/feat/0611-longonly-rejudge/2026-06-11-longonly-rejudge-design.md` §八.8 | 2026-06-11 |
| 债 L4 | 基准腿 costless 与 Top 腿扣成本不对称，方向性抬高超额/信息比 | `docs/feat/0611-longonly-rejudge/design.md` §八.7；`0613-f01-investability/report.md` §六.3 | 2026-06-11 / 2026-06-14 |
| DD-5 | 因子检验（裸因子 costless）与可投性回测（真实成本）非 like-for-like，并排展示须注明区别（已遵循） | `docs/feat/0613-f01-investability/2026-06-13-f01-investability-design.md` DD-5 | 2026-06-13 |

## 四、已核销（含"文档滞后"典型案例）

> 前几条是"历史文档仍标待处理、代码早已修复"的真实案例——证明了"关键时刻忘记债务"确实会发生，
> 只是这几次是文档没跟上代码。这正是维护本台账的意义：处理完债务后，回来把状态改掉。

| 债务 | 描述 | 关闭凭证 | 文档滞后说明 |
|---|---|---|---|
| 债 D9 | 僵尸编排链 `AutoTradingEngine`/`TradingOrchestrator`/`SignalPipeline` 被旁路 | 0628 R3a，commit `fd89097`；2026-07-05 已用 `find` 核实三文件已不存在 | `0611-closed-loop` 的 design/夜审/晨间手册三份文档（2026-06-11/12）仍标"待归档" |
| 债 D8 | `LiveSignalService` 注入 `trade_gateway` 未使用；`ITradeGateway` 缺 `cancel_order`/`query_order_status` | 0628 R1，commit `c77d890`；2026-07-05 已读 `trade_gateway.py` 核实三方法均存在 | `0611-closed-loop night-review`（2026-06-11）标"仍开放" |
| 债 B7 | 回测截面 runner 手写 `_compute_bar_metrics` 与 `stock_features` 口径不一致（`return_20d` bug） | 0614 Spec Phase 2，commit `44d4bed` 等；统一到 `feature_engine` | `0613-f01-investability`（2026-06-13）标"待关闭" |
| 债 B8 | 因子检验单线程物化 580 万对象，13 分钟/12GB | 0614 Spec Phase 1，commit `5e4f9de`…`e7a8b82`；列式向量化后 34 秒/1.9GB（提速约 23×） | 同上 |
| 债 B2 | 中证1000 指数 bars 缺失导致离线趋势闸 inert | 2026-06-14 入库 + A/B 验证，闸增益 IS/OOS 两窗泛化 | — |
| 债 B1 | 生存者偏差：早期仅 5207 只活跃标的入库 | 2026-07-04 回填 203/216 只退市股，含退市全窗收益不降反升，"绝对数字上界"折扣取消 | — |
| — | Spec2 架构治理（G1-G5）：删除 EventBus 回测空壳与死代码（对应 TD-06）、`build_cross_section` 归位 domain、`RiskSettings`/`config_app`/`dashboard_app`/`backtest_app` 依赖抽象化 | 2026-06-04，`docs/feat/0604-spec2-architecture-governance/` | — |
| — | 2026-06-11 夜审当晚 11 项 P0 bug：SQLite 跨线程写异常被吞、调度器采样漂移、单笔异常炸穿 `run_cycle`、亏损禁买闸首循环无基准、部成部撤未占预算、卖出误套 100 整数倍限制、dry 单号重启覆盖、资金游标未逐单扣减、日级防线未跨 mode 统计、mode 与网关可任意失配、报价新鲜度闸缺时间戳 | 2026-06-11 当晚修复，`docs/feat/0611-closed-loop/2026-06-11-night-review.md` §一 | 修复前风险等级极高，本次盘点中最密集的一批高危已核销项 |
| — | 影子盘"跨 mode 日预算共享"+"执行流水缺一致性口径（无纸面净值跟踪）" | 2026-07-04，`docs/feat/0704-live-prereqs/`，golden 全量绿 | — |
| — | 主板域过滤逻辑收敛为 `check_symbol_scope` 单一事实来源 | 2026-06-26 提出 → 2026-07-03 落地 | — |
| — | 全仓 CRLF→LF 统一 + `.gitattributes` 防复发 | 2026-06-30，0628 report §四 | — |
| — | QMT 网关签名不匹配（缺 `account_id`）；账户 ID/token 明文入库；Dashboard API 无鉴权 | 2026-05-31 当批次内修复，`code-review-final.md` | — |
| — | 因子假设漏斗早期"0/10 通过"结论 | 后续 `0611-longonly-rejudge` 改用长多头记分牌重判，F01 过闸，结论已被推翻 | 研究进度快照，非债务 |

## 五、未动工（远期规划，非当前债务）

> 从 2026-05-31 提案到今天从未开始实施，性质是"未来可选项"，不是"正在积累利息的债"。
> 与「四、已核销」中的 EventStore/UnitOfWork/NotificationHub 不同——那三个是**写了代码但没接线**，
> 这里列的是**连代码都没写**（`docs/rules/codebase-map.md` 的"已知幽灵目录"已逐路径核查确认）。

| 事项 | 核查依据 |
|---|---|
| 策略全生命周期自动化（`StrategyLifecycleManager`：注册→回测→评级→自动上线/下线） | `codebase-map.md` strategy/pool/ 仅有 `pool_manager`/`rating_engine`，无自动流转 |
| ML 模型灰度发布/影子模式（CANARY/SHADOW 部署策略） | `codebase-map.md` ml_engine/ 的 `MLModelVersion` 仅支持 `with_active` 切版本，无灰度机制 |
| 风控日志聚合（`RiskLog` 聚合根 + 每日风控报告） | `codebase-map.md` risk/ 域未见对应聚合根或仓储 |
| 盘后自动对账（系统持仓 vs 券商持仓） | 未见对应组件 |
| 算法交易 TWAP/VWAP/冰山单 | `codebase-map.md` 幽灵目录：`domain/trade/services/algo_strategies/` 仅剩 `__pycache__` |
| Brinson 归因分析 | 幽灵目录：`domain/backtest/services/attribution/` 仅剩 `__pycache__` |
| 组合优化器（均值方差/Black-Litterman） | 幽灵目录：`domain/portfolio/services/optimization/` 仅剩 `__pycache__` |
| 配置热更新、多账户支持 | 未见对应组件 |

## 六、待勘校（文档本身失真，建议顺手修订）

| 事项 | 位置 |
|---|---|
| 用户手册"算法交易"/"组合优化"两节仍有指向已删除模块 `algo_strategies.twap_strategy` 的示例代码 | `docs/helper/user-guide.html`（页面标注 v2026.06.01） |
| 用户手册"实时看板"描述的 `ws://localhost:8000/ws/dashboard` 与当前驾驶舱实际入口（`http://127.0.0.1:8501/ui/`）不一致 | 同上 vs `README.md` §快速开始 |
| 2026-05 一批 plan 文档的交付检查清单 checkbox 大量未勾选，只反映撰写时点，不代表功能现状 | `docs/feat/0530-system-roadmap/*-plan.md` |

## 七、在办（进行中，非债务，供状态确认）

| 事项 | 位置 | 状态 |
|---|---|---|
| 研究流水线叙事层重构（总览页流水线地图/run 人话命名/数据血缘标注） | `docs/feat/0705-research-narrative/` | 待评审，需拍板 4 个决策点 |
| ~~因子判决页卡片化重构~~ | `docs/feat/0705-verdict-cards/` | **2026-07-05 已完成并提交**（commit c49abb0…5a00071，gates.ts/sort.ts/FactorCard/FactorDetailModal/FactorTestForm 全部落地，前端 198 测试绿）；实施计划补记 `2026-07-05-verdict-cards-plan.md`（此前误落在 `docs/superpowers/plans/`，本轮已挪回 `docs/feat/` 并删除误建目录） |
| 研究记录退役清理：dry-run 已验证精确命中 27 轮回测+9 轮判决 | `docs/feat/0705-research-retire/2026-07-05-research-retire-plan.md` Task5 | 存量清理待手动加 `--yes` 确认执行 |

---

**维护方式**：新发现的债随手加一行到对应分类；处理完之后把整行剪到「四、已核销」并写清关闭凭证
（commit / 后续文档 / 代码现状核实方式）——不要只删掉，历史凭证本身有价值（见本表多个
"文档滞后案例"）。下次大重构前建议重新核对「一、二」两个待清偿分类。
