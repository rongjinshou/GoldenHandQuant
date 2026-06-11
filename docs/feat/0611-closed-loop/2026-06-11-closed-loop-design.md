# 全闭环 v1 — 端到端自动交易 · 回测留痕 · 驾驶舱全景 — 设计文档

| 项 | 值 |
|---|---|
| **状态** | 已定稿（整夜全权委托模式：决策以文档留痕，晨间补审） |
| **创建日期** | 2026-06-11 |
| **文档类型** | 需求 + 技术设计 / SDD Spec |
| **前置** | Spec 1 回测正确性（已合入 `c6e9057`）、投研驾驶舱 v1（`0611-dashboard`）、受控单笔实单（`0611-realtime-order`，首单 601006.SH 已验证） |
| **配套** | `2026-06-11-closed-loop-plan.md`（实施计划）、`2026-06-12-morning-runbook.md`（晨间补审手册） |

---

## 一、背景与现状盘点

用户目标：**全闭环的工程化产品**。本次开工前对三大用例做了全面现状核查：

| 用例 | 现状 | 结论 |
|---|---|---|
| **回测系统** | Spec 1 正确性修复已全部落地（2 P0 + 4 P1 + 金标准测试，commit `c6e9057`）；两 runner 共用 `BarWindow`，无前视；多策略对比、50+ 指标、绘图齐备 | ✅ 可信可用。**缺：结果不入库**，跑完即丢，驾驶舱看不到 |
| **Dashboard** | 投研驾驶舱 v1 按设计 100% 交付（数据资产 / 因子判决 / 个股查看三页签，FastAPI + 原生 JS + ECharts，只读） | ✅ 投研侧闭环。**缺：回测页、实盘监控页**（设计文档明确列为 future） |
| **实盘交易** | 受控单笔链路已实盘验证（五道安全闸 + 实时行情 + 状态轮询 + JSON 审计）。但 `auto_trade.py` CLI 是**空骨架**（engine 调用全注释）；策略信号→自动下单未接线；成交/持仓/循环结果**零持久化**；audit 仓储写好未提交未使用 | ❌ **最大缺口** |

**全闭环的定义**（本 Spec 的北极星）：

```
数据(market.duckdb) → 因子判决(factor_verdicts✅) → 策略(registry✅)
   → 回测(可信✅ + 入库🆕) → 实盘自动循环(🆕 dry-run=纸面前向 / live=小资金)
   → 交易留痕(trading.db🆕) → 驾驶舱全景可视(🆕回测页+实盘页) → 回到研究
```

与主线漏斗的关系：漏斗当前在「P0 因子 0/5，找第一个 edge」阶段，下一相位是**纸面前向**。
本次交付的 dry-run 自动循环**就是纸面前向的载体**——基础设施先行，edge 找到后翻配置即上。

---

## 二、需求（Requirements）

- **R1 端到端自动交易**：`quant auto-trade` 一条命令拉起完整循环——策略扫描 → 信号过滤 → 安全闸 → 下单 → 状态轮询 → 超时撤单 → 全程留痕。支持 `--once` 单循环与守护循环两种形态。
- **R2 双模式**：`dry_run`（默认，读真实行情与账户，下单只模拟记录）/ `live`（真实下单，三重显式确认才生效）。
- **R3 资金安全**：复用已实盘验证的盘前闸（标的范围/时段/报价新鲜度/涨跌停带/单笔金额/可用资金），新增**循环级与日级预算闸**（单循环最大单数、当日累计金额上限、当日亏损禁买）。任何一道失败=拒单留痕，绝不静默。
- **R4 交易留痕**：循环结果、每笔执行记录、账户/持仓快照、审计日志全部入库（SQLite `data/trading.db`），可追溯任意一单的来龙去脉。
- **R5 回测留痕**：每次回测（含多策略对比）自动写入 `market.duckdb` 的 `backtest_runs` 表：策略、参数、区间、核心指标、净值曲线。
- **R6 驾驶舱全景**：新增「回测」页（历次回测列表 + 净值曲线 + 指标）与「实盘」页（今日循环 / 执行记录 / 持仓 / 账户权益曲线），保持只读轮询风格。
- **R7 工程留痕**：设计文档（本文）+ 实施计划 + 晨间运行手册；README / CLAUDE.md 同步；逐逻辑单元 commit 直推 main。

### 非目标（Non-Goals，白纸黑字不做）

- ❌ **多策略并行**自动交易（v1 单策略，配置切换；`SignalPipeline` 多策略聚合留作扩展位）
- ❌ **异常检测指标体系**（`AnomalyDetector` 仅保留挂点；策略失效判定标准属漏斗 Phase 4 独立 Spec）
- ❌ **通知渠道**（邮件/IM 推送；v1 日志 + 留痕表即可，驾驶舱可见）
- ❌ **Web 端下单/撤单按钮**（驾驶舱保持只读，写操作只走 CLI）
- ❌ **因子判决→策略权重自动晋级**（P0 因子 0/5，无可晋级对象；链路打通后这是配置层动作）
- ❌ **盘口级/分钟级策略**（v1 维持日线策略 + 盘中限价执行）

---

## 三、关键设计决策（Decision Records）

### DD-1 · 自动循环的脊柱 = `LiveSignalService` 路径，新建 `AutoTradeAppService`

**决策**：自动循环复用 `quant live` 已验证的 `LiveSignalService.scan()`（拉行情→跑策略→仓位计算→`SignalDisplay`），在其上新建 `AutoTradeAppService` 完成「过滤→闸→下单→轮询→留痕」。**不接线** `AutoTradingEngine`/`TradingOrchestrator`。

**理由**：
- 实读 `TradingOrchestrator.execute_cycle` 发现：它把 runner 产出的 `OrderTarget` **退化回 `Signal`**（`confidence_score` 硬编码 1.0、丢弃 sizer 已算好的价格数量），再让 `SignalPipeline` 重算——往返失真，置信度过滤形同虚设。
- 其依赖的 `StrategyRunner` 是回测语义（`BarWindow`：T 日**开盘价**成交）。盘中 14:50 执行时开盘价早已过时，实盘应按**最新价±滑点**挂限价单——这正是 `LiveSignalService` 的语义。
- `quant live` 半自动路径已经过人工实测，是三条路径中唯一摸过真实行情的。在它上面加自动化 = 最短可信路径。

**代价与登记**：`AutoTradingEngine`/`TradingOrchestrator`/`SignalPipeline` 暂成旁路（测试保留、不删除）。登记为治理债：闭环跑稳后由后续 Spec 决定「合并或归档」（参照 Spec 3 归档手法）。**本次不动它们**——既不接线也不重构，避免一次变更两个变量。

### DD-2 · 安全模型：默认 dry-run + 三层防线 + live 三重确认

**决策**：

1. **模式**：`auto_trade.mode: dry_run | live`，默认 `dry_run`。dry-run 用 `DryRunTradeGateway` 包装真实网关——行情/资产/持仓读真实，`place_order` 只生成 `dry-` 前缀订单号并记录，不触达 QMT 下单接口。
2. **三层防线**（逐单依次过，任一失败拒单留痕）：
   - **第一层 · 盘前闸**（复用首单验证过的六道闸，提取为 domain 纯函数，见 DD-3）：标的范围（主板）、交易时段、报价新鲜度、涨跌停带、单笔金额上限、可用资金（买）/可用持仓（卖）。
   - **第二层 · 预算闸**（循环/日级，新增）：`max_orders_per_cycle`（默认 3）、`daily_notional_cap` 当日累计成交意向金额上限（默认 ¥3000，从 trading.db 当日已提交记录累计）、当日重复标的去重（同标的同方向当日只下一次）。
   - **第三层 · 当日亏损禁买**：当日权益回撤超 `daily_loss_limit_ratio`（默认 2%，基准=当日首个账户快照）→ 只允许卖出信号通过。
3. **live 三重确认**：配置 `mode: live` **且** 配置 `enabled: true` **且** CLI `--live` 旗标，三者齐备才走真实网关；任何缺失自动降级 dry-run 并在日志与循环记录中醒目标注。
4. **执行价**：买入 `min(ask1, last×1.002)`、卖出 `max(bid1, last×0.998)`（沿用首单验证过的定价并对称扩展）；轮询超时（默认 30s）未终态 → **主动撤单**并记录（网关无撤单能力时留痕告警，不静默）。

**理由**：账户 ¥146k、策略尚无已验证 edge——自动化的价值是把「纸面前向」跑成基础设施，真金白银必须显式三重开闸。单笔上限沿用 `MAX_NOTIONAL_CEILING=5000` 硬顶。

### DD-3 · 盘前闸提取为 domain 纯函数，单笔与自动共用（消「两套尺子」）

**决策**：把 `OrderTicketAppService` 内联的六道闸提取为 `src/domain/trade/services/pre_trade_checks.py` 纯函数集（输入：symbol/now/quote/volume/价格上限/可用资金或持仓 → 输出：通过或带原因拒绝 + 建议限价）。`OrderTicketAppService` 与 `AutoTradeAppService` 共同调用；ticket 现有测试**必须保持全绿**（行为等价重构）。新增卖出方向检查（可用持仓量、卖出限价构造）。

**理由**：Spec 1 的教训——同一约定两处实现必然跑偏。安全闸是最不容跑偏的代码。

### DD-4 · 交易留痕：SQLite `data/trading.db`（WAL），新建 `TradingStore`

**决策**：交易侧持久化独立于行情库，落 SQLite `data/trading.db`（WAL 模式），新建 `TradingStore`（infrastructure）持有 schema 与读写：

```sql
trading_cycles(cycle_id TEXT PK, cycle_time TEXT, mode TEXT, strategy TEXT,
               signals_generated INT, orders_submitted INT, orders_rejected INT,
               orders_failed INT, notional_submitted REAL, note TEXT, created_at TEXT)
execution_records(order_id TEXT PK, cycle_id TEXT, symbol TEXT, direction TEXT,
               signal_price REAL, exec_price REAL, volume INT, notional REAL,
               status TEXT,            -- DRY_RUN/SUBMITTED/FILLED/PARTIAL/CANCELED/REJECTED/FAILED/TIMEOUT
               reject_reason TEXT, strategy_name TEXT, confidence REAL,
               submitted_at TEXT, final_status_at TEXT, status_trail TEXT)  -- JSON
account_snapshots(snapshot_time TEXT, mode TEXT, total_asset REAL,
               available_cash REAL, frozen_cash REAL, market_value REAL)
position_snapshots(snapshot_time TEXT, mode TEXT, symbol TEXT, total_volume INT,
               available_volume INT, average_cost REAL, last_price REAL)
```

审计日志复用已实现的 `AuditLogRepository`（SQLite，同一 db 文件），关键动作（cycle 开始/结束、每单提交/拒绝/撤单、模式降级）写 `audit_logs`。该仓储此前未提交未使用，本次补测试、提交、正式启用。

**理由**：
- **不放 market.duckdb**：DuckDB 单写者，守护进程长期持写锁会挡 `data refresh` 与因子测试；行情库是「研究资产」，交易库是「运行日志」，生命周期与备份策略不同。
- **选 SQLite 而非新 DuckDB 文件**：现有 `Database`/`OrderRepository`/`AuditLogRepository`/`SnapshotRepository` 全是 SQLite 栈，WAL 下「交易进程写 + 驾驶舱读」并发安全；行级 upsert（订单状态推进）是 OLTP 形态，SQLite 比 DuckDB 合适。
- v1 不复用 `orders` 表（`OrderRepository`）：`execution_records` 已覆盖订单全生命周期，双表记账徒增不一致风险。

### DD-5 · 回测留痕：`market.duckdb` 新表 `backtest_runs`，CLI 跑完自动入库

**决策**：`MarketDataStore` 增 `backtest_runs` 表与 `insert_backtest_run` / `load_backtest_runs`：

```sql
backtest_runs(run_id VARCHAR, created_at TIMESTAMP, strategy VARCHAR,
              start_date DATE, end_date DATE, initial_capital DOUBLE,
              params VARCHAR,        -- JSON
              total_return DOUBLE, annualized_return DOUBLE, max_drawdown DOUBLE,
              sharpe_ratio DOUBLE, sortino_ratio DOUBLE, calmar_ratio DOUBLE,
              win_rate DOUBLE, trade_count INT, turnover_rate DOUBLE,
              equity_curve VARCHAR,  -- JSON {dates:[], values:[]}
              PRIMARY KEY (run_id, strategy))
```

`run_backtest` / `compare_strategies` / `quant backtest|compare` 跑完即写（`--no-store` 可关）；多策略对比 = 同 `run_id` 多行。写入用短连接（开-写-关），与 `factor_verdicts` 同模式，避免占写锁。

**理由**：回测是研究产物，归研究库，驾驶舱已有该库的只读通道；与 `factor_verdicts` 形成「因子判决 ↔ 策略回测」同库对照——这正是闭环的研究侧账本。净值曲线 JSON 列对日线规模（每年约 244 点）完全够用，YAGNI 不建明细表。

### DD-6 · 驾驶舱扩两页签，沿用 research 只读 REST 风格

**决策**：
- **回测页** `/api/research/backtests`：runs 倒序分组列表（同 run 多策略并排）+ 点击展开 ECharts 净值曲线 + 指标表。读 `market.duckdb`（read_only，复用现有依赖注入）。
- **实盘页** `/api/live/overview|cycles|executions|positions|equity`：今日循环统计、执行记录表（含拒单原因）、最新持仓、账户权益曲线（来自 `account_snapshots`）。读 `data/trading.db`（read-only URI 连接）；库不存在/空 → 显式空态文案（与现有 503/空态风格一致）。
- 前端在现有 `index.html`/`app.js` 上加两个页签（hash 路由），ECharts 复用已 vendor 的版本。**不引入**新依赖、token、WebSocket。既有 `dashboard.py`（WS+token 旧路由）不动不扩。

**理由**：v1 驾驶舱的成功经验就是「只读 + 轮询 + 零构建链」；实盘页轮询周期 5s 足够人看，WS 是过度工程。

### DD-7 · 调度复用 `TradingScheduler`，CLI 形态 = `--once` / 守护

**决策**：守护模式复用现有 `TradingScheduler`（分钟检查 + `execution_times` 命中触发，默认 `["09:35", "14:50"]`），回调挂 `AutoTradeAppService.run_cycle`；`--once` 立即执行一个循环后退出（不校验 execution_times，但盘前闸的时段检查照常生效——非交易时段的 `--once` 会产出「全拒单」循环记录，本身就是接线冒烟）。SIGINT/SIGTERM 优雅停止。`quant auto-trade` 与 `python -m src.interfaces.cli.auto_trade` 同入口。

**理由**：调度器是现成且独立测试过的组件，职责单一（线程+时间），与 DD-1 弃用的编排器无耦合。开盘后 5 分钟与收盘前 10 分钟是 A 股日线策略的常规执行窗口。

### DD-8 · 配置：`trading.yaml` 新增 `auto_trade` 段

```yaml
auto_trade:
  enabled: false              # 默认关闭；--enable 临时覆盖仅对 dry_run 生效
  mode: dry_run               # dry_run | live；live 还需 CLI --live
  strategy: dual_ma
  symbols: ["600000.SH", "601006.SH", "600096.SH", "000021.SZ"]   # 主板白名单内
  execution_times: ["09:35", "14:50"]
  min_confidence: 0.6
  max_orders_per_cycle: 3
  per_order_notional_cap: 1500.0    # 硬顶 5000 仍生效
  daily_notional_cap: 3000.0
  daily_loss_limit_ratio: 0.02
  poll_timeout_seconds: 30
  position_ratio: 0.1
  bar_lookback: 100
  db_path: "data/trading.db"
```

设计要点：symbols 默认值全部位于盘前闸主板白名单内（`002xxx` 中小板暂不在 v1 范围，沿用首单设计 D4）；`enabled` 与 `mode` 双字段分离「要不要跑」与「跑什么模式」。

---

## 四、组件与数据流

```
quant auto-trade (--once | 守护)
  └─ AutoTradeWiring(配置) ──► QmtTradeGateway / DryRunTradeGateway(包装)
                              QmtMarketGateway · QmtRealtimeQuoteFetcher
                              TradingStore(trading.db) · AuditService(AuditLogRepository)
  └─ AutoTradeAppService.run_cycle(now)
       1. LiveSignalService.scan(strategy, symbols)        # 已验证路径
       2. 过滤: min_confidence → 当日已交易去重 → 截断 max_orders_per_cycle
       3. 当日亏损禁买检查(account_snapshots 当日基准)
       4. 逐单: pre_trade_checks(六道闸, 实时报价重定价) → 预算闸(日累计)
       5. trade_gateway.place_order → 轮询至终态(30s) → 超时撤单
       6. TradingStore: cycle + execution_records + 账户/持仓快照
          AuditService: 全程审计
  └─ TradingScheduler(守护模式, execution_times 触发)

run_backtest / compare ──► BacktestReport ──► MarketDataStore.insert_backtest_run(market.duckdb)

dashboard(8501)
  ├─ /api/research/* (market.duckdb 只读)  + /api/research/backtests 🆕
  └─ /api/live/*     (trading.db  只读) 🆕
```

**错误处理**：循环内任何异常不杀守护线程（调度器已捕获）；单 symbol 扫描失败跳过该标的；下单异常按 FAILED 留痕；trading.db 写失败是致命错误（停止循环并审计——宁停不漏记）；驾驶舱对两库的缺失/锁冲突均显式空态或 503。

**测试策略**：domain 闸函数纯单测（无 mock）；`TradingStore`/`AuditLogRepository` 用临时 db 文件；`AutoTradeAppService` 注入 mock 网关 + 假时钟，覆盖「全链路下单成功 / 各闸拒单 / 亏损禁买 / 预算耗尽 / 超时撤单 / dry-run 不触真网关」；API 端点用 TestClient + 临时库；ticket 既有测试全绿守护 DD-3 重构。

---

## 五、验收清单

- [ ] `quant auto-trade --once`（dry-run）产出完整循环留痕：cycle 行 + execution_records + 快照 + 审计
- [ ] dry-run 模式下 QMT 下单接口零调用（mock 断言）
- [ ] live 缺任一确认（mode/enabled/--live）自动降级 dry-run 且留痕
- [ ] 六道盘前闸 ticket 与 auto 共用同一实现，ticket 原测试全绿
- [ ] 预算闸：第 4 单被 max_orders_per_cycle=3 截断；当日累计超 cap 拒单；亏损超限只放行卖出
- [ ] 回测跑完 `backtest_runs` 有行，驾驶舱回测页可见净值曲线
- [ ] 驾驶舱实盘页展示循环/执行/持仓/权益，trading.db 缺失时显式空态
- [ ] 全量测试绿（`WIN_PYTHON -m pytest tests/ --ignore=tests/infrastructure/gateway/`）+ `ruff check src/` 干净
- [ ] README / CLAUDE.md 更新；晨间运行手册就绪

## 六、已知限制与晨间补审项

- **live 首跑留给晨间**：代码与闸全就绪，但 `--live` 首次真实自动下单按约定由用户晨间按运行手册亲自触发（与首单同规格：单笔 ≤¥1500）。
- **撤单依赖网关能力**：若 `QmtTradeGateway` 无 `cancel_order`，超时单留痕告警为 `TIMEOUT_UNCANCELED`（实现时确认补齐）。
- **持仓快照是轮询快照**而非增量回报：两次循环间的盘中变化不可见，v1 接受（执行窗口仅 2 个/日）。
- **dual_ma 默认策略仅为基础设施验证用**，无收益预期——漏斗找到 edge 前，live 模式不应启用（这是流程约束，非代码约束）。
- **治理债登记**：`AutoTradingEngine`/`TradingOrchestrator`/`SignalPipeline`/`AnomalyDetector` 旁路保留，待闭环稳定后独立 Spec 处置。
