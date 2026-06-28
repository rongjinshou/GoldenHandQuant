# 回测/实盘决策核心归一 — 架构重构设计文档

| 项 | 值 |
|---|---|
| **状态** | 已定稿（设计阶段；待用户审 → writing-plans） |
| **创建日期** | 2026-06-28 |
| **文档类型** | 架构重构 / SDD Spec |
| **触发** | F01+趋势闸 推 dry-run 影子盘时发现「信号一致性」**结构性不可能** → 用户质疑「为何回测/实盘实现不一致」→ 4-agent 架构审计 + 溯源 |
| **前置/关联** | `docs/rules/architecture.md`（宪法 §3「回测实盘共用 domain」）；`docs/rules/live-trading.md`（**债 D9**：AutoTradingEngine 归档候选）；`docs/feat/0604-spec2-architecture-governance/`（架构剧场治理先例）；`docs/feat/0626-mainboard-f01-shadow/`（F01 影子盘，**其阶段 1 被本重构接管**） |
| **北极星** | 回到宪法精神：回测与实盘**共用同一套决策逻辑**，差异只在执行层的真实性 |

---

## 一、背景与动机

主线（给 ¥146k 找可投 edge）推进到「F01+趋势闸 上 dry-run 影子盘」、要验「信号一致性」（实盘目标组合 == 回测同日输出）时，审计发现：**当前架构下信号一致性结构性不可能成立** —— 回测和实盘的决策逻辑漂移成两套，实盘截面路径缺趋势闸、基本面装配（`market_cap=0`）、风控信号、批量 sizer。

这违反架构宪法 `architecture.md` §3「**接口隔离 (DIP)**：回测/实盘共用 domain」。本 Spec 系统消除分叉，既是 F01 影子盘的前置，更是还一笔结构性架构债。

## 二、问题诊断（4-agent 审计结论）

### 2.1 根本结构 — 两套 application 编排，只共用最内层策略

```
回测:  BacktestAppService → StrategyRunner.evaluate ─┐
                                                      ├─ 只在这里共用 → generate_(cross_sectional_)signals
实盘:  AutoTradeAppService → LiveSignalService.scan ─┘
```

两条线各自把「装配→风控→sizer→产出→执行」重写一遍，所有分叉从这道裂缝长出。

### 2.2 分叉分两类（关键 — 不能一锅端）

**A. 合理差异（数据源/执行真实性，保留）**

| 分叉 | 回测 | 实盘 | 为何合理 |
|---|---|---|---|
| 时间 | `set_current_time` 注入 | `datetime.now()` | 回测要时间旅行 |
| 成本结算 | `DailySettlementService` 模拟 | 券商真实扣费 | 实盘真扣，无需模拟 |
| 订单安全闸 | 无 | `run_pre_trade_gates` 六道 | 实盘防失控下单 |
| 留痕 | `BacktestReport` | `AuditService`/`TradingStore` | 用途不同 |

**B. 漂移债（决策逻辑本应回测==实盘，却在实盘缺失/走样 — 消除）**

| 分叉 | 回测 | 实盘截面路径 | 证据 / 后果 |
|---|---|---|---|
| **趋势闸** `SystemRiskGate` | 有 | **无** | `strategy_runner.py:210` vs `live_signal_service.py:_scan_cross_sectional` 无；F01 价值主源丢失 |
| **截面装配** `CrossSectionBuilder`(基本面+指标) | 有 | 简化快照 **market_cap=0.0** | `live_signal_service.py:179`；**实盘连最小市值都选不对** |
| **风控信号** `RiskSignalGenerator`(止损/涨停破板) | 有 | **无** | 实盘无自动止损 |
| **批量 sizer** `calculate_targets`(截面集中度) | 批量 | 逐个 `calculate_target` | 实盘无截面级风控 |
| **输出格式** | `OrderTarget` | `SignalDisplay` | 决策/执行边界两线不一致 |
| **网关契约** | — | `cancel_order`/`query_order_status`/`is_dry_run`/`get_stock_snapshots` **不在 Protocol**，靠 duck typing/fallback | Mock 不能跑实盘循环 → 两边无法同编排测试 |

### 2.3 三条根因

1. **缺一个共享的「决策编排」核心**：回测 `StrategyRunner.evaluate` 其实是单日决策编排（装配→趋势闸→风控→sizer→目标组合），只依赖 Protocol、本可被实盘复用 —— 但实盘另写 `LiveSignalService.scan`。
2. **网关接口契约不完整**：关键方法不在 domain Protocol，逼上层 duck typing/fallback（`market_cap=0` 即 fallback 恶果）。
3. **「决策」与「执行」职责边界两线画法不同**：回测产 `OrderTarget`、实盘产 `SignalDisplay`，决策逻辑混进各自的执行编排。

### 2.4 第二套实盘编排（僵尸，债 D9）

实盘侧除在用的 `AutoTradeAppService`，还躺着旁路的 `AutoTradingEngine`（=`TradingScheduler`+`TradingOrchestrator`+`SignalPipeline`+`OrderExecutor`/`ExecutionMonitor`/`AnomalyDetector`/`NotificationHub`）。`live-trading.md` §1 已判其「**不再接线，归档候选，债 D9**」。

**惊人对比**：被旁路的 `TradingOrchestrator` 决策段**恰恰做对了** —— 它 `runner.evaluate(DayContext)` 复用 `StrategyRunner`（=方案 A 要做的）；而在用的 `AutoTradeAppService` 决策段反而走了分叉的 `LiveSignalService`。两套各完善一半：Orchestrator 决策段对、AutoTradeAppService 执行段安全（六道闸/撤单/留痕/dry_run 校验）完善。

## 三、溯源 — 为什么成这样

| 时间 | 事件 | 性质 |
|---|---|---|
| 05-09 | `LiveSignalService`（半自动信号） | 半自动起点 |
| 05-31~06-01 | 「4.x 全自动」`AutoTradingEngine` + SRP 重构（精细分层） | **理想架构先行，未接通真单脏活**（无 QMT 真单/六道闸/留痕/dry_run 安全） |
| 06-04 | 架构治理 Spec 抓「架构剧场」 | 见下 |
| **06-11** | 上 dry-run，4.x 不能安全下单 → 重写落地的 `AutoTradeAppService`，旧套旁路（D9） | **落地实现抄近道**：决策段图快走 `LiveSignalService`，未复用 `StrategyRunner` → 趋势闸/装配丢失 |

**根本毛病（项目文档自陈）**：
- `0604` 治理 design：「EventBus 回测空壳…事件被静默丢弃…**架构剧场（~100 行复制粘贴+误导）**」。
- `architecture.md` §6 v4.0：「剔除虚构内容：v3.0 将**规划误写为现状**…78 条路径 **32 条不存在**…已移除」。

即：项目反复「搭精致架构外壳却不接通」，外壳成死代码/空壳；文档一度把规划当现状。**文档与代码两头漂移过** —— 这是「有架构文档却仍偏离」的原因。

**两类债**：① 两套编排 = **已登记未还的 D9**（`live-trading.md` 明记归档候选）；② 回测/实盘决策分叉（趋势闸/装配缺失）= **本次审计才挖出、文档未登记的新债**。

## 四、方案选择

| | 消除根因 | 复用已验证代码 | 改动面 | 风险 |
|---|---|---|---|---|
| **A 决策核心归一（选定）** | ✅ | ✅（StrategyRunner 跑过 F01/B2；TradingOrchestrator 是现成实盘样板） | 集中实盘侧 | 中（动共用代码，回归守门） |
| B 另起中立 DecisionEngine | ✅ | ❌ 重写决策层 | 回测+实盘都改 | 高 |
| C 逐项对齐补丁 | ❌ 治标 | — | 最小 | 低但治本失败（用户明确反对） |

**选 A**。强化依据：`StrategyRunner.evaluate` 经核实**只依赖通用 Protocol**（`get_recent_bars`/`get_positions`/`get_asset`），内部不碰 `set_current_time`/`load_bars` —— 本就接近中立；且 `TradingOrchestrator` 已是「StrategyRunner 跑实盘」的**现成参考实现**（连 `DayContext` 构造、targets 转换都有，带测试），R3 不必从零写。

## 五、目标架构 — 决策/执行分层

```
                ┌────────── 决策核心（共享，回测==实盘）──────────┐
  注入网关 ───▶ │ StrategyRunner.evaluate(DayContext)             │ ──▶ list[OrderTarget]
 (回测/实盘不同) │ 装配截面(CrossSectionBuilder,含基本面)→趋势闸    │     (唯一决策输出)
                │ →策略→风控信号(RiskSignalGenerator)→批量sizer   │
                └─────────────────────────────────────────────────┘
                                      │
              ┌────────────────────────┴────────────────────────┐
        回测执行段                                     实盘执行段（合理差异，各自保留）
   MockTradeGateway 撮合                          pre_trade_gates 六道闸 → 下单 → _poll 撤单
   + DailySettlement 模拟成本                     + DryRun/QMT + AuditService/TradingStore 留痕
   → BacktestReport                               + dry_run/网关配对校验
```

`OrderTarget` 成为决策段唯一输出；`SignalDisplay` **降级**为从 `OrderTarget` 派生的 **UI 展示 DTO**（驾驶舱/半自动确认用），不再承载决策逻辑。

## 六、关键设计决策

| DD | 决策 |
|---|---|
| **DD-1 决策核心定位** | `StrategyRunner`（截面/时序两 runner）确立为唯一决策核心。提纯：`circuit_breaker` 可选化、`DayContext` 实盘可构造（`today`+主板宇宙+DAY_1）、确认无回测专属硬依赖 |
| **DD-2 网关接口契约补全** | `cancel_order`/`query_order_status`/`is_dry_run`/`get_stock_snapshots` **写进 domain Protocol**；`MockTradeGateway` 实现撤单/查单 → Mock 能跑实盘循环 = 回测/实盘同编排可测 |
| **DD-3 fundamental 装配抽象** | 决策核心要 `fundamental_registry`：回测/dry-run 影子盘从 **DuckDB 同源**装（复用 `build_backtest_cross_section`）；真实 QMT 实盘的实时基本面留真单 Spec |
| **DD-4 实盘接核心 + 僵尸归档** | `AutoTradeAppService` 决策段改调 `StrategyRunner.evaluate` 取 `targets`；删 `LiveSignalService._scan_*` 决策重写（退化为 `OrderTarget→SignalDisplay` 的 UI 转换薄层）。**参照 `TradingOrchestrator` 决策段样板**，**裁决吸收**其治理特性（`pause_manager`/`anomaly_detector`/多策略/通知），再**归档** AutoTradingEngine 那套空壳（还 D9） |
| **DD-5 回归守门** | 归一**前后回测结果逐位不变**（golden 净值/targets 对拍），是动共用代码的安全绳 |

## 七、要还的债清单

| 债 | 来源 | 还法 | 阶段 |
|---|---|---|---|
| **D9 两套实盘编排** | `live-trading.md` 已登记 | 吸收 Orchestrator 决策样板/治理特性 → 归档空壳 | R3 |
| **决策分叉**（趋势闸/装配/风控/批量sizer 实盘缺失） | 本次审计新挖 | 实盘接共享决策核心 | R3 |
| **网关契约不完整** | 本次审计 | 关键方法进 Protocol + Mock 实现 | R1 |
| **治理特性去留**（pause/anomaly/多策略/通知） | Orchestrator 独有 | 逐个裁决纳不纳入 | R3 |

## 八、分阶段路径（每阶段独立可验证、可 commit）

- **R1 网关接口契约补全**（DD-2）—— 地基，低风险，解锁「Mock 跑实盘循环」。先确认 `dashboard.py` 对 AutoTradingEngine 的引用是否仅占位。
- **R2 决策核心提纯 + 回归守门**（DD-1/DD-5）—— `StrategyRunner` 提纯为名正言顺的共享核心，回测 golden 逐位不变。
- **R3 实盘接决策核心 + 僵尸归档**（DD-4）—— `AutoTradeAppService` 决策段调核心；删 `LiveSignalService` 决策重写；参照 `TradingOrchestrator` 样板、裁决吸收治理特性；归档 AutoTradingEngine 空壳（还 D9）。实盘**只剩一套编排**。
- **R4 F01 dry-run 影子盘**（接管 `0626` 阶段 1）—— 重构后**自然接对**（趋势闸/基本面装配/批量sizer 都在）；决策核心跑 `today` + auto-trade 执行段 dry-run，验信号一致性==回测（此时是**架构保证**）。

## 九、非目标

- ❌ **不改回测业务行为**（纯归一，回归 golden 守门）。
- ❌ **不上真单**（R4 是 dry-run 影子盘；真单 live 是下一 Spec）。
- ❌ **不重构 factor-test / 判决链路**。
- ❌ **真实 QMT 实盘的实时 fundamental 装配**留真单 Spec（dry-run 用 DuckDB 同源）。
- ❌ **不做合理差异的「对齐」**（时间注入/模拟结算/订单安全闸/留痕按各自真实性需求保留）。

## 十、风险与缓解

| 风险 | 缓解 |
|---|---|
| 动共用决策代码改变回测行为 | R2 golden 逐位对拍守门；每步 TDD 小提交 |
| 归档僵尸误删仍在用的东西 | 先确认 `dashboard.py`/`monitor.py` 仅占位引用；保留其测试作样板参考再删 |
| 治理特性（pause/anomaly）有价值却被一删了之 | R3 逐个裁决，有价值的吸收进归一后的执行编排，非无脑删 |
| `StrategyRunner` 提纯遗漏回测耦合 | R1 先补 Mock 撤单/查单使 Mock 能跑实盘循环，提纯后用「Mock 跑 auto-trade 循环」交叉验证 |

## 十一、与 0626 F01 Spec 的关系

- F01 影子盘从 `0626-mainboard-f01-shadow` 的「阶段 1」**升级为本重构的 R4**。
- `0626` 阶段 0 gate（主板域 F01+趋势闸 **PASS**，OOS Sharpe 1.69）成果**保留有效**，是 R4 的对照基准。

## 十二、验收标准

1. **回测 golden 逐位不变**（R2 守门通过）。
2. **实盘决策段 == 回测决策段**（同一 `StrategyRunner`，趋势闸/基本面装配/风控/批量 sizer 都在）。
3. **实盘只剩一套编排**（AutoTradingEngine 空壳归档，`live-trading.md` D9 关闭）。
4. 关键网关方法进 Protocol，`MockTradeGateway` 能跑 `AutoTradeAppService` 循环（同编排可测）。
5. **R4：F01 dry-run 影子盘目标组合逐日 == 只主板回测同日输出**（信号一致性=架构保证）。
6. 全套测试绿 + `ruff check src/` 干净。
