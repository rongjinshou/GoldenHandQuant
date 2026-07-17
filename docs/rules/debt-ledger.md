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
| 债 D2 | 判决闸门阈值在 `verdict.py`、前端 `gates.ts`、CLI 输出三处独立硬编码，无单一真相源 | `docs/feat/0705-verdict-cards/2026-07-05-verdict-cards-design.md` §11 | 2026-06-11 | **✅ 2026-07-05 已核销**: 创建 `gates_config.py` 作为单一真相源，`verdict.py` 改为 import，新增 `/api/meta/gates` 端点，`gates.ts` 改为从 API 动态获取。**⚠️ 2026-07-05 全项目排查复核发现遗留缺口，已修复(commit `d958e12`)**：`judge_factor()` 的 IC 正率闸(§7.2 一致性)当时仍是硬编码字面量 `0.52`，压根没 import `IC_POSITIVE_RATE_MIN`——7 道闸门只迁移了 6 道。数值凑巧一致(都是0.52)所以无现症，但下次调阈值只改 `gates_config.py` 会静默漏改这一道。新增 `monkeypatch` 回归测试防再犯 |
| 真单前置 | `cancel_order` 撤单接口自 R1(0628) 补入协议后，从未经过真实盘中撤单验证 | `docs/feat/0704-live-prereqs/2026-07-04-live-prereqs-report.md` | 2026-07-04 | **🔧 2026-07-05 已增强**: 增加详细日志和 ValueError 分支处理，补充文档注释说明首次真单撤单需人工确认。仍需真实盘中验证 |
| TD-03 | `NotificationFactory.create_notification_gateway()` 无论配置几个通知渠道，永远只取 `notifiers[0]` | `src/infrastructure/notification/factory.py:38` | 2026-05-31 | **✅ 2026-07-05 已核销**: 创建 `CompositeNotificationGateway`，factory 改为遍历所有 notifiers 组合 |
| TD-04 | `RiskEventDispatcher.dispatch()` 用 `except Exception: pass` 吞掉全部通知异常，无日志无告警 | `src/domain/risk/services/risk_event_dispatcher.py:21-22` | 2026-05-31 | **✅ 2026-07-05 已核销**: 添加 `import logging` + `logger.warning()` 记录异常 |
| — | 应用层存在一套完整的 `NotificationHub`（去重/优先级队列/回执/历史，259 行）从未被任何 composition root 实例化接线；生产实际用的仍是更简陋的 `RiskEventDispatcher`/`notification/factory.py` 旧路径（即上方 TD-03/TD-04） | `src/application/notification_hub.py` | 2026-07-05 新发现 | **✅ 2026-07-05 已核销**: 在 `auto_trade.py` 的 `_build_service` 中实例化 NotificationHub，注入 `AutoTradeAppService`，交易执行时通过 `_notify()` 发送通知 |
| 阶段1设计项 | 等权 sizer 满仓边界反复触发"资金不足"（影子盘阶段1留痕 3281 次），需要现金 buffer 或按可用资金缩放，后续三份文档未回应处理结果 | `docs/feat/0626-mainboard-f01-shadow/2026-06-26-mainboard-f01-shadow-report.md` §四 | 2026-06-26 | **✅ 2026-07-05 已核销**: `EqualWeightSizer` 新增 `cash_buffer` 参数(默认 1%)，`calculate_target` 和 `calculate_targets` 均扣除预留现金后再均分。**⚠️ 2026-07-05 全项目排查复核发现遗留缺口，已修复(commit `01e792c`)**：批量法 `calculate_targets()` 除以 `target_value_per` 前有 `> 0` 守卫，但实盘路径唯一调用的单数法 `calculate_target()` 一直没有——`total_asset=0`(新账户尚未同步资金/被打光，均为真实可达状态)会让 `target_value_per_symbol` 精确为 0，直接 `ZeroDivisionError` 崩穿 `strategy_runner.py`/`live_signal_service.py` 整条信号生成链路(调用方无 try/except)。补齐守卫，行为改为返回 0(本次不调仓)而非崩溃 |
| DD-6 | Mock 回测对 ST 股票涨跌停幅度按板块普通比例处理（如 ±10%），未按 ST 应有 ±5%；`is_st` 硬编码 `False` | `docs/feat/0604-backtest-correctness/2026-06-04-backtest-correctness-design.md` §六 | 2026-06-04 | **🔧 2026-07-05 二次核实，问题比原记录更深，非"随手接线"级别**：`MockTradeGateway` 的 `stock_status_registry` 参数与 `get_price_limit_ratio(is_st=...)` 接口确实就绪；全仓 10 处（非 11 处，原数字有误）`MockTradeGateway(...)` 构造点（`run_backtest.py:66`/`commands/backtest.py:80`/`compare_strategies.py:114`/7 个 scripts）核实**无一传参**，`is_st` 恒 `False`——涨跌停校验在撮合里是"能否成交"闸门（不是限价），效果是**回测结果系统性偏乐观**：真实跌停应封死无法卖出时，回测按 ±10% 阈值判定"可卖"，允许 ST 持仓在跌停日"干净"止损离场，**低估了 ST 股票的尾部风险/回撤**（是资金正确性问题，方向明确对交易者不利地失真，不只是"策略层面被误判"）；买入方向对称地高估策略捕捉涨停行情的能力。**新发现同族缺口**：`src/domain/risk/services/risk_policies/limit_up_break_policy.py:24` 调用 `get_price_limit_ratio(pos.ticker)` **连 `is_st` 参数都未传**，比 MockTradeGateway 更原始。**根因不是"接线"而是数据源缺失**：`StockStatusRegistry`(`domain/market/value_objects/suspension.py`)除测试外生产代码从未被构造/`.add()` 过，是纯空壳；唯一可用的 ST 信号代理（`filter_st.py` 用 `StockSnapshot.name` 前缀匹配）不是时点正确数据——`qmt_fundamental_fetcher.py:161`/`akshare_delisted_fetcher.py:102` 把"当前名称"均匀回填到该股票全部历史日期，对 ST 状态发生过变化(摘帽/戴帽)的股票会产生方向不确定的历史误标；全仓无任何代码/脚本引用真实的历史 ST 状态数据源(如 akshare `stock_info_change_name` 类接口)。**完整修复量级**：新数据源(新表+新fetcher+全市场回填脚本，量级堪比 B1 退市股回填，非几行代码)→ loader 灌入 registry → 接 10+1 处构造点。是否现在做，取决于当前策略实际 ST 持仓敞口，需业务判断，未擅自处理。**🔧 2026-07-11 深市口径落地（E3，设计 `docs/feat/0711-st-honesty/`）**：`st_status_periods` 表+深交所官方简称变更流 1387 区间入库；三消费点全接线（Mock 撮合 ±5% 10 处/`LimitUpBreakPolicy(is_st_fn)`/截面名称 as-of 修正含部分覆盖防线 `has_symbol`）；F01 重验证实旧口径偏乐观（裸 top20 全窗 −31.9pp）但 **gate 重验 PASS**（OOS 回撤 11.30%<基准 14.78%、闸增益不蒸发、OOS Sharpe 1.73）→ 影子盘继续有效。**余债**：沪市主板数据源——公告标题法经交叉验证 FAIL（≤2td 仅 43%，均值 +81.5td）不准入；升级路径 ①`TUSHARE_TOKEN`→`namechange` 一次覆盖沪深（接线就位即插即用）②公告正文抽取另立。G7 完整核销待沪市落地后再重验。**✅ 2026-07-12 全口径核销**：临时 tushare 账号 `bak_basic`（逐日名称快照）补齐沪市——交叉验证 98.4% ≤2td/均值 0.12 天 PASS，入库 1861 区间（沪 469）；G7 终局 **PASS**（OOS ON 回撤 11.27%<基准 14.78%、Sharpe 1.89、闸增益不蒸发）。裸 F01 乐观偏差全链挤干：210.8%→159.8%（−51pp）。残余：停牌窗内帽日 ±数日模糊（该期无 bars 不可成交，无实质影响）、bak 起 2020（窗口内完整） |
| 已登记债 | factor-test 引擎对表达式中缺失的基本面字段静默按 0 分处理，F10（毛利率）曾因此被误判 FAIL | `docs/rules/data-layer.md` §4；`docs/feat/0610-factor-library/2026-06-11-night-round2-report.md` §三 | 2026-06-11 | **🔧 2026-07-05 部分已核销**: 新增 `resolve_and_validate_field_name()`（`field_mapping.py`），对象式/向量化两条求值路径均已接入——**未知字段名**（拼写错误/映射缺失）现在会立即抛 `UnknownFactorFieldError`，回归测试覆盖两条路径。**✅ 2026-07-10 剩余部分已核销（六西格玛体检 B3）**："面板级数据质量抽查"落地为 `quant data status --check` 门禁（`src/infrastructure/persistence/data_quality.py`）：特征成熟区 NULL 固化哨兵（零容忍，阈值经生产库实测校准为 0）、近 60 日全市场方差=0 退化列告警、新鲜度分级、features/fundamentals 对齐；进 `scripts/verify_all.py` 验收链，FAIL 退出码 1 |
| 已知限制 | 影子盘不支持守护模式跨日长跑：fundamental as-of 别名只在装配期算一次，跨日会 fault abort | `docs/feat/0626-mainboard-f01-shadow/2026-07-03-phase1-shadow-report.md` §四.1 | 2026-07-04 | **✅ 2026-07-05 已核销**: `LiveSignalService` 新增 `refresh_fundamental_alias()` 方法，每次 cross-sectional scan 前自动刷新别名 |

| H1 | **下单幂等崩溃窗口（live 专属）**：`execution_records` 在整单轮询完成后才写入（`auto_trade_app.py` `_execute_one` 返回后 `save_execution`），而 `place_order` 在轮询前已发出——两者之间最长≈30s；进程在此窗口崩溃/断电则券商已有真单但账本无行，重启后当日去重（`today_traded_keys`）查不到 → **重复下单**。audit_logs 的 place_order 行虽已落但去重不查它。建议：下单前先 INSERT PENDING 行、place 后 UPDATE + 启动时"券商未结委托↔账本"对账告警 | `src/application/auto_trade_app.py` | 2026-07-10 六西格玛体检 | **✅ 2026-07-10 当日核销(用户批复"有问题就修")**: 下单前预写 PENDING 行(占预算/去重)→place 后 `replace_execution_order_id` 换真单号→终态覆盖; `run_cycle` 开头 `_reconcile_stale_executions` 对账非终态残留并 audit 告警; 轮询异常且单已发出改标 FAILED_AFTER_SUBMIT(占用, 防追单重复); API 预算镜像同步。测试: SpyGateway 钉死"先落账后下单"时序 + 崩溃残留去重 + 对账告警, 3 用例 |
| M5 | **正式风控策略未接线实盘**：`PositionLimitPolicy`(单票≤30%)/`TotalPositionPolicy`(总仓≤80%)/`DailyLossPolicy`/`DrawdownPolicy`/`CircuitBreaker` 生产零实例化；`live_signal_service.py` 构造 runner 未传 circuit_breaker → 熔断实盘恒 None。实盘仓位约束仅剩 sizer 目标权重 + 单笔/日 notional cap + 2% 禁买，无单票/总仓/回撤的执行期硬闸 | `src/application/live_signal_service.py`；`src/domain/risk/services/risk_policies/` | 2026-07-10 六西格玛体检 | **✅ 2026-07-10 部分核销**: PositionLimitPolicy(单票≤30%)/TotalPositionPolicy(总仓≤80%)经 RiskChain 接入 `_execute_guarded` 执行期硬闸(无状态每单即时计算, --once 与守护同等有效), 阈值 trading.yaml 可配(`max_position_ratio`/`max_total_position_ratio`), 4 用例。**未接**: CircuitBreaker(时点判断见后)。**✅ 2026-07-11 熔断补齐(T6)**: 状态入 `trading.db.breaker_states`(按 mode 隔离), `restore_state` 跨进程续命, `_sync_breaker` 每周期恢复/日重置/评估/落库; TRIGGERED 禁全部(含卖出)、COOLDOWN 仅卖、次二日恢复, 与 2% 软禁买构成递进防线; 阈值 yaml 可配(breaker_*), 熔断同步失败 fail-open+高声告警(避免数据库抖动演变为交易瘫痪); 4 集成用例含跨进程恢复场景 |
| M6 | **半自动 `quant live` 绕过全部盘前闸直发真单**：`commands/live.py:96-102` 直接构造真 `QmtTradeGateway`（无 DryRun 包装、无三重确认），`place_confirmed_orders` 不过 `run_pre_trade_gates`（无金额cap/价格带/时段/ST/新鲜度闸），安全仅靠交互式 y/N | `src/interfaces/cli/commands/live.py`；`src/application/live_signal_service.py` | 2026-07-10 六西格玛体检 | **✅ 2026-07-10 当日核销**: `place_confirmed_orders` 强制过 `run_pre_trade_gates` 全闸(限价改由闸统一构造); **未配置报价源一律拒单**(裸奔路径关闭); 三个生产调用方(commands/live.py、live_trade.py 双路径、SignalReviewUI)全部装配 QmtRealtimeQuoteFetcher + auto_trade 同源金额上限; 3 新用例+2 旧用例按新契约改造 |
| M3 | **QMT 回报回调与断线重连缺失**：`register_callback` 注册的是 SDK 基类空实现，全仓 0 处重写 `on_stock_order/on_stock_trade/on_disconnected`——成交回报无处理（部成实际成交量无法回填 execution_records，见同批 M4）、断线无自动重连无告警，订单状态 100% 靠轮询 | `src/infrastructure/gateway/qmt_trade.py` | 2026-07-10 六西格玛体检 | **🔧 2026-07-10 保守版落地**: `GhqTraderCallback` 子类接管 on_disconnected(置不可用标志+place_order 拒单+高声告警)/on_order_error/on_stock_order(留日志); **不自动重连**(时序未经真实环境验证, 显性失败优于带病运行)。**遗留**: 成交回报回填 execution_records(M4 部成实际量)与自动重连, 需 QMT 实环境联测另立; 3 用例(Windows 侧验证, WSL skip) |
| M7 | **无交易日历**：时段闸只排除周末+时段窗，法定节假日（工作日）会通过；兜底仅报价新鲜度>180s 拒单 | `src/domain/trade/services/pre_trade_checks.py`；`src/application/trading_scheduler.py` | 2026-07-10 六西格玛体检 | **✅ 2026-07-10 当日核销(数据推导方案, 零手工维护)**: 新增 `TradingCalendar` 值对象(bars distinct date 推导, 上交所 6 年日历即权威数据); 已知休市(工作日节假日)拒单/不触发调度, 未来日 unknown 放行(报价新鲜度 180s 闸兜底, 新鲜度又受 data --check 门禁保障——体系闭环); 时段闸+调度器+auto_trade 装配全贯通, 9 用例 |
| C1-b | **factor-test 面板路径基本面腿仍为 T 日口径**：决策核心的基本面前视已修（见已核销 C1），但向量化面板 `load_feature_join_df` 的 SQL 直接按同日 join fundamentals——因子检验快照的 market_cap/PE/PB 仍是 T 收盘派生值。影响因子研究口径（与前向收益窗口重叠 1 日），不影响策略回测/实盘。修法需 as-of join + golden 重验（factor_verdicts 会漂移） | `src/infrastructure/persistence/market_data_store.py` `load_feature_join_df` | 2026-07-10 六西格玛体检 | 另立专项，重验后统一口径 |

| MC-1 | **市值口径失真（策略定义级, 2026-07-12 tushare 审计发现）**：`fundamental_snapshots.market_cap` = QMT 合约详情 `TotalVolume` × 收盘价，但实测 QMT 该字段**语义不一致且陈旧**（601939 恰为 A 股流通股本、603330 仅总股本 18%、600000 为 88%——对不上总股本也对不上流通股本），叠加"当前股本均匀回填全历史"（与名称回填同族缺陷）。**实测影响**：与 tushare 时点总市值对照，主板"最小市值 top50"中 46 只为口径低估混入（沪市 603 系重灾）；**top20 两口径重叠仅 3/20**——F01 实际选的不是"最小总市值"组合。**护栏**：回测/影子/实盘同口径，内部一致性完好，G7 PASS 对"现口径策略"依然成立；但策略定义/因子解释失真，且 QMT 字段未来若修复会使策略行为突变（持续经营风险）。**修正源已沉淀**：`ts_daily_basic.total_mv/total_share`（时点正确, 2010→今）。处置走 C→A（用户批）。**✅ 2026-07-12 当日核销**（`docs/feat/0712-mc1-cap-regime/`）：全库迁移（审计三抽样日中位比值 1.000000/>1%差 0，QMT 原值备份 `market_cap_qmt` 可回滚）+ 日增量 sync（tushare→akshare 兜底，双败退出 1，接影子盘上午链）+ 门禁 C8 跨源偏差/C9 名称新鲜度固化 + 正式口径 gate PASS（OOS ON +49.9%/回撤 11.00%/Sharpe 1.48）+ F01 新基线入库（cap=total_mv，top20 全窗 227.3%）。**连环核销**：instruments 5203 只退化名修复+upsert 防降级覆写；`_data_wiring` 离线分支（WSL factor-test import 安全）。**残余**：F01 verdict 换代挂 Windows 侧（interop 恢复后）；MC-2（pe/pb 同族）另挂观察 | `docs/feat/0712-mc1-cap-regime/` | 2026-07-12 |

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
| — | ~~EventStore/UnitOfWork 做了没接线~~ | 同右 | 2026-07-05 新发现 | **✅ 2026-07-10 核销(删除清偿, Q7)**: 四文件+两测试删除, `domain_event.py` 保留(circuit_breaker 在用); 审计职责已由 audit_logs 承担, 复活坐标见 REVIVAL.md §五#15 |
| — | ~~资金分配子系统去留未决~~ | `docs/feat/0604-spec3-breadth-trim/` §10 | 2026-06-04 | **✅ 2026-07-10 核销(删除清偿, Q7)**: 悬置两轮无人复活即答案——engine(311L)+算法树+再平衡树+kelly_sizer+两实体+两接口+对应测试全删(生产 0 引用逐一验证), 复活坐标 REVIVAL.md §五#14 |
| — | CSV/Tushare 旧数据路径与 DuckDB 新数据层长期并存，未做退役清理 | `docs/feat/0611-market-data-store/2026-06-11-market-data-store-design.md` §7/§9 | 2026-06-11 | — |
| 新发现 | `MockTradeGateway.cancel_all_open_orders()`/`daily_settlement()` 是从未被生产路径调用的重复死代码：`BacktestAppService`(`backtest_app.py:234`) 实际走的是 domain 层 `DailySettlementService.process_daily_settlement()`，后者才正确实现了撤单+解冻+T+1；`MockTradeGateway` 自己这两个方法的冻结资金解冻分支是纯 `pass` 桩子(注释自称"接口完整性"，但两条注释互相矛盾——一条说"部分成交场景会有残留"，另一条说"不存在挂单")。**资金侧无风险**：`place_order()` 唯一可能让订单以非终态滞留 `self.orders` 的路径(`_simulate_fill` 内 "Overdraw prevented" 异常)，其 except 块已正确解冻资金；且该异常路径依赖 `actual_cost≠frozen_amount`，在上方双重折扣 bug 修复后已是浮点误差级别、实际不可达。唯一残留影响是订单对象会以 `SUBMITTED` 滞留到日终才被 `cancel_all_open_orders()` 扫成 `CANCELED`(语义上更应是 `REJECTED`)，属订单历史记录语义问题，非资金正确性问题 | `src/infrastructure/mock/mock_trade.py` | 2026-07-05 | **✅ 2026-07-10 核销(Q7)**: 两桩方法删除, 唯一测试使用点迁移为逐持仓 `settle_t_plus_1()`(语义等价), 全套件绿 |
| FD-1 | **B2 特征校验拒入全市场（研究线断供, 2026-07-15 尸检发现）**: 未提交的 `_defective_feature_symbols` 用"库内首根 bar + WARMUP_DAYS"判成熟区, 但重算只装载 `_warmup_start(start)` 起的窗口——老股窗头 rolling NaN 必然落在"成熟区"→整只拒入不履约, 且不履约导致每轮 refresh 全量重算重拒(浪费+日志刷屏)。实测 5,113 只特征停 2026-07-03, 仅 82 只次新推进到 07-15。交易链不消费 stock_features(07-14 采样在特征停摆下正常, 实证), 仅 ML/因子研究线受影响。修法候选: 成熟区判定改用"本轮装载窗首根 bar + 20 交易日", 或 NaN 检查只覆盖本轮 upsert 目标区间 [start,end] | `src/application/market_data_app.py` `_defective_feature_symbols` | 2026-07-15 | 校验本意(防 NaN 覆盖好数据)正确且当晚立功——bars 断流期间它拦住了残缺特征入库; 修的是判定窗口, 不是撤防线 |
| 2026-05-31 批次 | 一次代码深度评审记录的架构级问题合集（领域事件缺失、`DailySettlementService` 无测试覆盖、两套通知接口不兼容 `INotificationGateway` vs `IRiskNotifier`、~~`CircuitBreaker.evaluate()` 依赖哨兵条件静默跳过检查~~(已独立复核并核销，见下)、熔断器状态无持久化、20+ frozen dataclass 含可变默认值、ML 训练管道多项风险等约 20 项 | `docs/feat/0530-system-roadmap/2026-05-31-code-review-{deep-dive,final,report}.md`；`risk-circuit-breaker-design.md` | 2026-05-31 | `code-review-final.md` 自评多数"✅已修复"，但这是 35 天前的自我核验，本轮**抽样独立复核了其中一项**（结果见下方"已核销"表 CircuitBreaker 一行——抽样这一项证实确未修复，其余约 19 项仍未逐条独立复核）。若近期重启 ML 预测或大改风控链路，建议继续抽样验证。**2026-07-10 二次抽样 3 项**: ①"DailySettlementService 无测试"——已有 `test_settlement_service.py` 10 用例(后续修复未回写台账的文档滞后案例); ②"20+ frozen dataclass 可变默认值"——AST 全仓扫描(frozen=True 且字段默认为 list/dict/set 字面量)命中 **0 处**, 已修或原判偏重; ③"两套通知接口不兼容"——`risk_notifier_adapter.py` 适配器已收敛, 架构可接受。三项均可视为关闭 |

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
| ~~幸存者宇宙口径~~ | **✅ 2026-07-10 当日闭环(Q6 获批)**: F01 主跑已切 `include_sources=("qmt","akshare")` 含退市宇宙并重跑新基线(top_n 20/10/30 全窗口, run_id 20260710-2334xx~2341xx, 含 repro 块+survivorship 标注); 新基线口径 = 含退市 + C1 基本面 T-1, 与旧入库结果不可直接对比 | `scripts/run_f01_investability.py` | 2026-07-10 |
| 标量/向量化双实现 | factor_test 的 runner/neutralizer/evaluator 三对并存。**2026-07-11 裁定保留**: 标量路径是 `quant factor-test --no-store` 的显式回退通道(旧内存管道, 用户可见开关), 非死代码; golden 等价在案(0614)。若未来退役 --no-store 再一并删 | `src/domain/strategy/factor_test/` | 2026-07-11 |
| ~~MC-2 pe/pb 同族失真观察~~ ✅2026-07-12当日核销(0712-mc1 report §六: 全库迁移+审计中位1.0+judgments换代) | `fundamental_snapshots.pe_ratio/pb_ratio` 为 QMT 派生列, 疑与 MC-1 同用错误股本(未审计)。F01 不消费 pe/pb 故不阻塞主线; **F20/F21 等因子消费——研究线重启前必须先用 `ts_daily_basic.pe/pb`(已沉淀)对照审计**, 失真则同法迁移 | `docs/feat/0712-mc1-cap-regime/` 非目标节 | 2026-07-12 |
| SELL 金额闸与旧持仓过渡(真单 Spec 议题) | 2026-07-13 彩排实证: 旧持仓清仓单被 per_order_notional_cap(9000) 拦 2 笔、主板白名单拦 3 笔(002x)。真单前须裁定: ①SELL 是否豁免金额闸(退出通道不应被钱数卡死) ②旧持仓切换方案(手动清/分批/白名单临时放行) | `docs/feat/0711-shadow-control/` G6/G7 同批 | 2026-07-13 |
| 上帝仓储缓拆 | `market_data_store.py`(600+行/7表)。**2026-07-11 裁定本轮不拆**: 质量检查已外置 `data_quality.py` 泄洪; 7 表内聚源自单 DuckDB 连接+单写锁的真实约束, mixin 拆分只是视觉分文件; 待 C1-b(as-of join)专项动此文件时顺势拆, 避免两次大 diff | `src/infrastructure/persistence/market_data_store.py` | 2026-07-11 |
| 日亏闸 fail-open | 实盘唯一日亏防线（2% 禁买）在取不到资产/当日基准时跳过（fail-open 仅 warning）；M5 熔断未接线前这是唯一日亏保护。连接侧已由 H2 fail-fast 缓解（连不上根本进不了循环），残余为运行中读账户瞬断场景 | `src/application/auto_trade_app.py:255-257` | 2026-07-10 |

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
| 新发现 | `MockTradeGateway._simulate_fill()` 买入部分成交(流动性限制生效)时，解冻金额被按 `volume/order.volume` 比例二次折算，与冻结时已用 `fill_volume` 算好的金额重复打折——满额成交时 ratio=1 掩盖问题，只在部分成交时暴露，表现为超额资金永久卡在 `frozen_cash`（该订单终态 `PARTIAL_CANCELED`，不在任何后续撤单/日终解冻扫描范围内），可用资金被永久低估，严重时触发不该触发的"Overdraw prevented"熔断误拒真实可承受的订单 | 2026-07-05 全项目排查发现，commit `af94207`；`test_capacity_limit` 补 `frozen_cash` 断言，重写 `test_buy_partial_fill_with_tight_capital_settles_cleanly`（原名 `..._overdraw_protection`，此前测的其实是这个 bug 的症状而非正确行为） | — |
| 新发现 | `quant auto-trade`（--once/守护循环，dry_run/live 任意模式）装配期必现崩溃：`_build_notification_hub` 读 `settings.notification`，但 `AppSettings` 顶层无此字段（嵌在 `settings.risk.notification`），100% 触发 `AttributeError`，自动交易入口完全不可用；同批发现 `load_trading_config()` 从未解析 `risk` 配置段 | 2026-07-05 全项目排查发现，commit `6f004bc`；新增 `test_auto_trade_notification.py`（3例）+ `test_load_trading_config_parses_risk_section` | — |
| 新发现 | 前端"幽灵点击"同一 bug 三处独立实例：候选点选/"显示全部"展开按钮 用 `v-if` 使触发元素点击后消失，表格因行数变化增高会让新出现的可点击元素占据其原屏幕位置——浏览器对该次点击手势的 `mouseup` 坐标命中测试发生在 DOM 更新之后，会对新元素补发一次原生 `click`，误触发无关的选中/展开/收起 | `useSymbolChips.ts`(commit `f3e178d`，时间窗口守卫法) / `CyclesTable.vue`(commit `3f22d3d`，按钮常驻切换法) / `DataTable.vue`(commit `9faf251`，同常驻切换法，当前无消费者接 `rowClick`，隐患休眠但根上已消除) | 2026-07-05 全项目排查发现；三处独立实测确认同一机制后总结为可复用模式 |
| 新发现 | `CircuitBreaker.evaluate()` 哨兵跳过静默——`set_initial_capital()`/`reset_daily()` 均未先调用(或传入非正值)时，两道风控检查(单日亏损/总回撤)各自静默跳过，返回看似正常的 `NORMAL` 状态，实际未做任何风险评估；接线时序错误此前完全无声，真出险情才会发现熔断器形同虚设 | 2026-07-05 全项目排查**独立复核 2026-05-31 批次同名条目**，证实确未修复；commit `2d06fd7` 补 `logger.warning`(同 TD-04 惯例，不静默、记日志)，行为不变(仍返回原状态) | 见上方"2026-05-31 批次"行——是该批次~20项中被抽样验证仍未关闭的一项 |
| 2026-07-10 批次 | **六西格玛体检修复合集（7 项实盘/数据安全缺陷 + 门禁体系）**：① 清仓路径负限价——QMT 真账户止盈摊薄后 `average_cost` 可为负（2026-06-30 dry-run 实证 000021.SZ=-0.32165 已产出负价卖单入 execution_records），两条清仓分支补 `p<=0` 弃单防线 + `strategy_name` 误记 sizer 类名改为策略归因（`equal_weight_sizer.py`，5 个新测试含实证复现）；② QMT `connect()/subscribe()` 非 0 曾只记日志仍 `_initialized=True`，半死网关照样进下单路径——改 fail-fast 抛错（`qmt_trade.py`，2 新测试）；③ 下单后审计写库异常曾把真单误标 FAILED 且跳过撤单轮询——审计改为观测面吞异常高声留日志（`auto_trade_app.py`，1 新测试）；④ trading.db 无 `busy_timeout`，跨进程写者立即 locked——补 5s（`database.py`，2 新测试）；⑤ `seed_paper_trading` 默认清空生产留痕库——加 `--yes` 确认闸（实测无 --yes exit 2 且库未动）；⑥ `ensure_bars`/`ensure_features` 无条件 `mark_fulfilled`（10 万行 NULL 固化事故根因）——空返回仅上市窗外才履约、特征预热充足区 NULL 则不入库不履约留待重试（`market_data_app.py`，6 新测试含事故模式复现）；⑦ 截面回测基本面腿 as-of T 前视（market_cap 为 T 收盘派生却于 T 开盘执行；实盘本就 T-1 alias）——决策核心统一 as-of T-1，顺带消除"单日基本面缺口→空宇宙→防御性清仓"误伤（`strategy_runner.py`/`cross_section_builder.py`，2 新测试）。**注意 ⑦ 会改变截面策略回测数字（更诚实），历史入库结果与新跑不可直接对比** | 全部经 TDD（先红后绿），`scripts/verify_all.py` 全绿取证 | 2026-07-10 六西格玛体检（`docs/feat/0710-six-sigma-evolution/`）|
| 2026-07-11 批次 | **架构张力清偿合集(六西格玛第三轮, 「按6sigma排查改进」获批)**: ① 双 live 入口退役——rich 审核台迁入 `commands/live.py --review-mode rich` 后删 `live_trade.py`(275行, 05-09 引入被 05-31 统一 CLI 复制后未退役, M6 双倍改动实付维护税的根源); ② 履约元数据收敛(P6 债)——`QmtHistoryDataFetcher` CSV 透明缓存改默认关闭的显式开关(`csv_cache=True`), `_fetch_meta.json` 不再默认维护, DuckDB `fetch_meta` 成唯一履约真相源; data/ 根 5212 个散落 CSV 归档 `_legacy_csv/qmt_cache_retired_20260711/`; ③ 死入口 `cli/factor_test.py`(276行, quant.py 从未分发)删除; ④ factor_test 引擎 8 文件(纯 numpy/pandas 计算, 零 I/O)自 infrastructure **归位 domain**(`domain/strategy/factor_test/`, Spec2 build_cross_section 同款修复), 测试镜像同迁——application 顶层 infra import 就此清零; ⑤ `scripts/run_gateway_tests_wsl.py`——假 xtquant 模块驱动, WSL 也能回归 38 个 gateway 用例(Windows verify_all 仍是权威); ⑥ 架构分层纯度守卫 `tests/architecture/test_layer_purity.py`(AST 扫描三条红线, 纯度从人肉 grep 变自动门禁) | 全部 TDD; 顺带揪出一个测试暗依赖真实 data/ 目录状态的假绿用例(归档 CSV 后暴露, 已根治) | 2026-07-11 六西格玛第三轮 |
| 2026-07-10 批次 | **门禁与工程卫生合集**：⑧ gateway 30 测试被 `--ignore` 连坐（本就 mock SDK 不需真 QMT）——加 `conftest.py` importorskip 守卫（Windows 全跑/WSL 跳过），标准命令去掉 --ignore；⑨ `check_frontend_fresh` mtime 机制 git checkout 后必误报（当日实测 exit 1 假失败）——升级源码内容哈希（`write-stamp.js` 与 python 双端同规格，交叉验证哈希一致）；⑩ `ruff check tests/ scripts/` 268 处违规清零并纳入门禁（含 N806 真名变量、E501/E702 手修）；⑪ `backtest_runs` 入库统一注入 repro 块（git_sha/git_dirty/feature_version/bars 行数+最新日）与 survivorship 宇宙口径（未标注显式记 unspecified；F01 主跑已标 qmt_only）；⑫ 零覆盖实盘模块补测（`order_poller` 超时撤单/撤单被拒分支、`trading_sessions` 边界值，13 新测试）；⑬ domain 测试 MagicMock 违规清理（risk 两文件换手写 Fake）；⑭ WSL conda 环境缺 duckdb/scipy/sklearn/lightgbm 与文档"WSL 可跑回测"承诺不符——补装对齐；⑮ 一键验收链 `scripts/verify_all.py`（ruff+pytest+fresh+data --check，~30s 全绿退出 0） | 同上 | 同上 |

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
| 演进点清单 E3-E9（DD-6 ST 重验→G7 / M4 联测→G6 / 真单 Spec 本体 / C1-b / 驾驶舱影子证据可视化 / 全自动无人值守 / ML 长线） | 0710 六西格玛设计 §11 第四轮识别（2026-07-11），用户裁定主攻「通往小资金实盘」；E1/E2 已落地为 `quant shadow status --gate` 过闸判据（G1-G5 机器判 + G6/G7 人工判），设计 `docs/feat/0711-shadow-control/` |

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
