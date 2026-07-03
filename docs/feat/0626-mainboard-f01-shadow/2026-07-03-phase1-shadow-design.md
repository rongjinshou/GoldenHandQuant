# 主板 F01 影子盘 · 阶段 1 设计（dry-run 影子盘落地）

| 项 | 值 |
|---|---|
| **状态** | 已定稿（用户全权委托，决策自裁留痕） |
| **创建日期** | 2026-07-03 |
| **前置** | 阶段 0 gate PASS（同目录 report，OOS Sharpe 1.69）；0628 回测/实盘决策核心归一（R1-R4 + 0630 三债收口）——阶段 1 原骨架里最重的「截面引擎接 auto-trade」已被该重构**超额完成**（共享决策核心 + R4 一致性守门） |
| **审计依据** | 本设计基于 5 路并行架构审计（gate 口径 / live 执行流 / domain 日历 / 白名单配置 / 留痕比对，82 条带 file:line 证据的事实）+ 3 项实测（market.duckdb 新鲜度、risk 配置等价性、registry 日期语义） |

---

## 一、目标与范围

把 F01+中证1000趋势闸（阶段 0 gate PASS 的**唯一 OOS 验证可投候选**）以 **dry-run 影子盘**形态接入 auto-trade 链路，达成：每个调仓周二在真实数据流（QMT 行情 + 真实时钟）下产出决策快照，且**可与 DuckDB 离线同输入决策逐位比对** —— 验证"实盘信号 == 回测信号，无前视/无漂移"。

**非目标**：真单（下一 Spec）；纸面持仓模拟网关（PaperTradeGateway）；QMT 实时 fundamental 装配（真单 Spec）；驾驶舱 UI 展示快照；主板域扩 002/003（需重跑 gate）；守护调度模式适配（QMT 需人工拉起，先手动）。不删 dual_ma 路径。

## 二、审计定位的关键坑（设计必须逐一处置）

| # | 坑 | 证据 |
|---|---|---|
| K1 | **清仓地雷**：空宇宙/当日无基本面行/趋势闸阻断 都落入 `EqualWeightSizer` 空 buy_signals 分支 → 对账户全部持仓生成全额清仓 SELL；「数据故障」与「闸阻断=设计内全清仓」不可区分 | equal_weight_sizer.py:60-72; strategy_runner.py:233-234 |
| K2 | **fundamental 精确日期匹配**：`get_all_at_date` 无 as-of 回退；实测 market.duckdb 快照到 2026-06-11（每交易日 ~5190 行），当日无行则宇宙必空 → 触发 K1 | fundamental_registry.py:34-36; 实测 |
| K3 | **top_n 口径断裂**：gate PASS 验证 top_n=**20**，live 装配锁死 registry 默认 top_n=**9**，trading.yaml 无配置通道（AutoTradeSettings 无 strategy_params；scan 内 `create_strategy(name)` 也不带 params） | mainboard_f01_gate.py:33; registry.py:237; _auto_trade_wiring.py:66; live_signal_service.py:80 |
| K4 | **主板过滤缺位于装配层**：宇宙是 DuckDB 全市场，主板约束只在逐单 `check_symbol_scope` 拒单 →「全市场排名+事后拒单」≠ gate 的「先过滤再排名」，实际持仓 < top_n 且与只主板回测系统性偏离 | _auto_trade_wiring.py:55-64; pre_trade_checks.py:114-115 |
| K5 | **风控闸全不适配**：per_order_notional_cap=1500 + domain 硬顶 `MAX_NOTIONAL_CEILING=5000`（¥146k/20≈¥7.3k 全拒）；daily_notional_cap=3000（调仓日双向 ~¥29 万）；max_orders_per_cycle=3（调仓需 ~40 单） | pre_trade_checks.py:17; trading.yaml:39-41 |
| K6 | **dry-run 持仓透传真账户**：DryRunTradeGateway 读真实 QMT 持仓/资产、DRY_RUN 单永不成交 → 差额订单（targets）受真持仓污染且不收敛，执行流水不可作为一致性口径 | dry_run_trade.py:44-48 |
| K7 | **目标组合零留痕**：execution_records 只存被 `_select` 截断后的 ≤N 单；完整 targets/选股名单/闸状态/宇宙规模均无落库点 | trading_store.py:11-36; auto_trade_app.py:157-163 |
| K8 | **趋势闸 fail-open**：指数 bars<20 或取数失败 → 静默 pass_buy=True，无日志（回测 OFF 格正是靠此机制实现，不能改 domain） | system_risk_gate.py:26-30 |
| K9 | **`LimitUpBreakPolicy` 实盘静默失效**：QMT 实时 bars 的 prev_close 恒 0.0 → 涨停破板卖出只在回测生效，已知决策分叉 | qmt_market.py:87-97; limit_up_break_policy.py:22-25 |
| K10 | **xtdata 断连静默为 0 信号**：get_recent_bars 吞异常返回空，与休市/真无信号不可区分（QMT 断链 memory 的已知故障模式） | qmt_market.py:102-104 |
| K11 | **symbols 交集陷阱**：切 micro_value 时若保留现有 4 只 symbols，宇宙被交集缩到 4 只；交集为空则静默 symbols=[] 直通 K1 | _auto_trade_wiring.py:60-64 |

## 三、设计决策（DD）

### DD-1 · 主板过滤前移到宇宙装配层（修 K4，还 0626 DD-2 债）
`build_live_signal_service` cross_section 分支：universe 过滤 `[s for s in universe if check_symbol_scope(s) is None]`。**单一事实来源 = `pre_trade_checks.check_symbol_scope`**（60/000/001，与 gate 脚本 `is_mainboard` 同口径；依赖纯净，interfaces 层可直接 import）。开关 = `AutoTradeSettings.mainboard_only: bool = False`（默认关，不影响现有行为；影子盘配置 `true`）。不扩 002/003 —— gate 阶段 0 是在 60/000/001 域上验证的，扩板需重跑 gate。

### DD-2 · strategy_params 配置通道（修 K3）
`AutoTradeSettings` 加 `strategy_params: dict`（默认 `{}`）。两处消费必须同源：
1. wiring：`merged = {**config.default_params, **at.strategy_params}`，`top_n = int(merged["top_n"])` 配 `EqualWeightSizer(n_symbols=top_n)`；
2. `LiveSignalService` 构造加 `strategy_params` 参数，scan 内 `create_strategy(strategy_name, self._strategy_params)`。

影子盘配置 `top_n: 20`（gate PASS 口径）。不改 registry 默认值（避免影响既有回测/报告口径）。

### DD-3 · 风控闸重标定（修 K5；trading.yaml 配置值 + 一处 domain 参数化）
- `MAX_NOTIONAL_CEILING` 从常量改为 `run_pre_trade_gates(..., notional_ceiling: float = 5000.0)` 参数，`AutoTradeSettings.per_order_notional_ceiling: float = 5000.0`。**默认值不变**（0611 首单验证的安全语义保留），影子盘显式配 `10000.0` —— 抬顶留痕在配置，可审计。
- 影子盘配置值：`per_order_notional_cap: 9000`（¥146k/20≈¥7.3k + 波动余量）、`daily_notional_cap: 320000`（调仓日双向 ~2×¥146k + 余量）、`max_orders_per_cycle: 48`（≤20 买 + ≤20+ 卖 + 余量）、`symbols: []`（全宇宙→主板过滤，K11 陷阱在 runbook 写明）。
- 不动：`min_confidence 0.6`（截面信号 confidence 恒 1.0，是死闸，文档写明其不承担截面过滤职责）、`daily_loss_limit_ratio 0.02`、`execution_times`。

### DD-4 · 数据健康守卫：区分「数据故障」与「合法清仓」（修 K1/K8/K10 的 scan 侧）
新增 `DataHealthError(RuntimeError)`。守卫全部在 **application/装配层**，domain 不动（`SystemRiskGate` 的 fail-open 是回测 OFF 格的实现机制，改它会破坏 gate 脚本）：

- **装配期 fail-fast**（`build_live_signal_service`）：主板过滤后 universe 为空 → 抛；fundamental as-of 别名（DD-5）滞后 > 7 个日历日 → 抛（拒绝用陈腐数据决策）。
- **scan 期 abort-cycle**（`_scan_cross_sectional`，调 runner **之前**）：① universe 为空；② 当日（别名后）fundamental 行数 < 500（正常 ~5190，容忍部分缺失但拒绝断崖）；③ 趋势闸指数 bars < 20（将静默 fail-open）—— 任一命中抛 `DataHealthError`。复用现有异常路径：scan 抛异常 → `run_cycle` catch → note 留痕 → **本周期零下单**（既不买也不卖，正是数据故障时的正确姿势）。
- **合法清仓不拦截**：数据完好时 runner 产出的清仓单（趋势闸阻断日 / 1、4 月空仓月）是 F01+趋势闸的设计内行为（gate 回测的回撤减半正来自它），照常放行。

### DD-5 · fundamental as-of 别名（修 K2，装配层 hack，不动 domain）
registry 构造后若 today 无行：取 `<= today` 的最近快照日 D，把 D 日的行以 today 为 date_key **别名注册**进 registry（`FundamentalRegistry.register` 现成可用，snapshot 复制改 date）。滞后天数写进决策快照留痕；> 7 天触发 DD-4 fail-fast。理由：不改 domain 精确匹配语义（回测零影响）；实盘用最近一期快照**无前视**（回测用 T 日收盘市值排序反而更"乐观"）；口径差异（市值滞后 ≤ 数天）计入比对预期差异白名单。runbook 要求跑前 data refresh，把滞后压到 ≤1 交易日。

### DD-6 · xtdata 健康探针（修 K10 的启动侧）
`IMarketGateway` Protocol 加 `ensure_ready() -> None`（不可用抛 RuntimeError）；`QmtMarketGateway` 实现 = `xtdata.get_instrument_detail('000001.SZ')` 空则抛（同 test_qmt_connection Step1 口径，轻量不触发下载）；`MockMarketGateway` 空实现。auto_trade CLI 装配后调用，失败打印诊断指引（`scripts/test_qmt_connection.py` + runbook 故障条目）退出 —— 把「无法连接xtquant服务」从半程抛栈/静默 0 信号前移为一次性可读 fail-fast。

### DD-7 · 决策快照留痕表 `signal_snapshots`（修 K7，比对的数据地基）
trading.db 新表，cycle 级一行，记录**决策的完整输入与输出**：
`cycle_id, snapshot_time, mode, strategy, universe_size, universe_filtered_size, fundamental_date（别名源日）, fundamental_rows, index_bars_count, gate_passed, positions_json（scan 时刻持仓）, total_asset, selection_json（策略 top_n 选股名单）, targets_json（runner 差额单全集）, data_health, note`。
写入机制：`LiveSignalService` 暴露 `last_snapshot` 属性（scan 后填充，`ScanSnapshot` dataclass），`run_cycle` 在 scan 后读取落库（`TradingStore.save_signal_snapshot`）—— **不改 scan 签名**，`AutoTradeAppService` 改动最小。bar 路径 last_snapshot=None 不写。`selection_json` = targets 中 BUY 方向反推的目标池（gate 剥离前的策略内部名单不透出——那要改共享决策核心，违反最小侵入）；「闸阻断」与「选股为空」的区分靠 `gate_passed` 字段：DD-4 守卫已为检查拉取指数 bars，顺手按同一 MA20 口径判定记录（与 runner 内部判定同 gateway 同参数同源）。

### DD-8 · 一致性比对脚本 `scripts/shadow_consistency_check.py`（阶段 1 的验证闭环）
口径裁定（修 K6）：**比对在决策快照级，不在执行流水级**。执行流水受真持仓透传 + 风控截断 + DRY_RUN 不成交影响，天然不可比；而 R4 已在单测层保证「相同输入 → scan == runner.evaluate」，剩下唯一要验的是**真实数据流下输入是否一致** —— 故比对 = 同输入喂离线决策核心，diff 输出：

1. 读 trading.db `signal_snapshots` 指定日快照（输入：positions/total_asset/宇宙口径/fundamental 别名日；输出：selection/targets）；
2. 离线侧：DuckDB bars 装 `MockMarketGateway` + 同一 fundamental 别名口径 registry + Mock trade/account gateway 注入快照持仓资产 → `CrossSectionalStrategyRunner.evaluate`（current_time=快照时间）；
3. diff：selection 集合、targets `(symbol, direction, volume)` 逐位；报告打印 + 存 `data/shadow_checks/YYYY-MM-DD.json`。

唯一自由变量 = bars 源（QMT 实时 vs DuckDB 存量）。**预期差异白名单**（报告须标注而非误报）：前复权基准日漂移（比成员/股数不比绝对价）、盘中末根 bar 形态（开盘价 09:35 已定型，sizer 用 T 开盘价 → 应收敛）、fundamental 别名滞后、节假日周二（实盘无交易日历判断）。

### DD-9 · QmtMarketGateway 补 prev_close（修 K9）
`get_recent_bars` 返回序列内以前一根 close 填充 prev_close（首根保持 0.0）。与 DuckDB 历史 bars 的前复权口径自洽（两侧同为前复权序列内 prev(close)），使 `LimitUpBreakPolicy` 在实盘路径恢复生效，消除「回测有涨停破板卖单、影子盘没有」的系统性分叉。

### DD-10 · 调度与 runbook：手动周二 --once 起步
QMT 客户端需人工拉起，守护模式暂无意义。影子盘节奏（写入 morning-runbook）：
调仓周二 09:30 后 → ① 开 QMT 极简端（确认**行情**面板有跳动数据，不只交易登录）→ ② `data refresh`（bars+fundamental 增量到最新）→ ③ `auto-trade --once --enable`（dry_run）→ ④ 收盘后再 `data refresh` + `shadow_consistency_check`。非调仓日不需跑（非周二策略语义 = hold 真持仓，方案下无比对价值）。1/4 月为空仓月，跑则预期全清仓信号（合法）。

## 四、验收标准

1. 新增/修改路径全部 TDD 单测绿；golden 全量回归 0 failed；ruff 干净。
2. 装配单测覆盖：主板过滤口径（与 gate 脚本 is_mainboard 一致）、strategy_params 透传两处同源、as-of 别名（有当日行/无当日行/滞后超限）、空宇宙 fail-fast。
3. scan 守卫单测覆盖：三种数据故障 abort（不产生清仓单）+ 数据完好时闸阻断清仓照常放行（合法路径回归）。
4. 端到端冒烟（QMT 已恢复）：refresh 后 `auto-trade --once` 跑通全链，`signal_snapshots` 落库且 data_health=ok；随后 `shadow_consistency_check` 对当日快照 diff=0（白名单差异外）。今天（周四）冒烟预期：非调仓日 hold 语义，链路照走、快照照落。
5. 阶段 1 report 落档；memory 更新。

## 五、风险与诚实校准

- **比对口径的极限**：本阶段验证的是「决策核心在真实数据流下与离线同输入等价」；影子组合长期画像跟踪（假想净值 vs 回测净值）不在本阶段 —— 需先攒数周快照，且真单前应做（记入真单 Spec 前置）。
- **execution 流水仅作链路证据**：DRY_RUN 单证明风控闸/下单路径走得通，不进入一致性判定。
- **fundamental 别名 = 用最近一期快照**：无前视但与回测「T 日快照」口径存在 ≤1 交易日差，边界处选股可能差 1-2 只 —— 比对脚本用同一别名口径喂离线侧，故 diff 仍应为 0；与「gate 回测原口径」的差异属画像跟踪议题。
- **趋势闸阻断日 = 全清仓**（非"停新买"）：这是 gate 验证过的设计内语义（sizer 空 buy 分支），MA20 附近反复穿越会有整仓进出 churn —— 阶段 0 回测已含此行为，影子盘如实复刻，不"优化"。
