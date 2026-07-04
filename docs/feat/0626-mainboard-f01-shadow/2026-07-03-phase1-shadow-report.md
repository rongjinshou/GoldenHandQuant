# 主板 F01 影子盘 · 阶段 1 完成报告（2026-07-04）

> **一句话**：F01+趋势闸 dry-run 影子盘全链落地并在真实数据流上完成一致性闭环 ——
> **QMT 实时决策与 DuckDB 离线同输入重放逐位相等（selection/targets/gate 全一致，exit 0）**。
> 「实盘信号 == 回测信号，无前视/无漂移」从架构保证（0628 R4 单测层）升级为**真实数据流实证**。

## 一、交付（commit bddb60d..2f7faad，全 main）

| 批 | commit | 内容 |
|---|---|---|
| 设计/计划 | `bddb60d` `244dcf1` | 11 坑审计（K1-K11，5 路并行审计 82 条 file:line 证据）+ 10 项决策（DD-1~10）+ 5 批次 TDD 任务卡 |
| A 装配件 | `3e3efdd` | `AutoTradeSettings` 影子盘字段（strategy_params/mainboard_only/ceiling）；`DataHealthError`；盘前闸 ceiling 参数化（默认 5000 不变）；`FundamentalRegistry.latest_date_at_or_before/alias_date`；`QmtMarketGateway` prev_close 填充（修 K9：LimitUpBreakPolicy 实盘静默失效）+ `ensure_ready` 行情探针 |
| B 守卫快照 | `692728e` | `LiveSignalService`：数据健康守卫（DD-4）、`ScanSnapshot` 决策快照（DD-7）、strategy_params/clock 注入；`CrossSectionalStrategyRunner.prime_index_data`（显式注入口，evaluate 零行为变化）；wiring：主板过滤（DD-1）+ as-of 别名（DD-5）+ 装配 fail-fast |
| C 接线 | `db24815` | `signal_snapshots` 表（17 列，决策完整输入+输出）+ run_cycle 落库（成功/fault 双路径）+ CLI 探针 fail-fast + ceiling 透传 |
| D 配置/比对 | `1aca5c7` | trading.yaml 切 `micro_value`（**top_n=20 = gate PASS 口径**，修 K3）+ 闸重标定（9000/10000/320000/48，修 K5）；`scripts/shadow_consistency_check.py`（DD-8 同装配路径重放）；fetch_index_bars 动态窗口 |
| E 验证 | `c877727` `2f7faad` | 对抗复查新增**守卫 4**（个股行情抽样探测，堵"指数可得但个股全断→静默清仓"漏网，K1 红线）；比对脚本非交易日口径放宽 |

golden 全量回归 exit=0（新增 ~40 用例），ruff 干净。

## 二、端到端冒烟实证（2026-07-04 周六，QMT 双链路在线）

**auto-trade --once（dry_run）**：探针过 → 装配（全市场 4249 → 主板过滤 **1887** 只）→ 守卫过 → 决策 → 快照落库：

```
signal_snapshots: universe 4249→1887 | fundamental_date=2026-07-03(as-of 别名, staleness=1天)
fundamental_rows=4235 | index_bars=100 | gate_passed=1 | data_health=ok
positions=6只真持仓透传 | total_asset=176,598.18 | 非调仓日(周六): selection=[], targets=1笔SELL
执行段: 1单 REJECTED「非交易日: 2026-07-04 (周6)」— 盘外拒单=链路通的正确语义
```

**shadow_consistency_check --date 2026-07-04**：离线装载 1887 只 + 指数 → 同 clock/持仓/资产重放：

```
gate_passed: live=True offline=True → 一致
selection  : live 0 / offline 0     → 一致
targets    : 逐位(symbol,direction,volume) → 一致
meta 全对齐: universe/filtered/fundamental_date/rows/staleness/index_bars 六项 live==offline
结论: 全一致 (exit 0)
```

唯一自由变量是 bars 源（QMT 实时 vs DuckDB 存量），结果逐位相等 —— 数据路径无分叉。

## 三、安全语义（K1 清仓地雷的处置结果）

| 路径 | 行为 | 留痕 |
|---|---|---|
| 宇宙空 / 交集空 / 基本面滞后>7天 | 装配 fail-fast，进程不启动 | CLI 错误退出 |
| 当日基本面行数断崖 / 指数 bars<20 / **个股行情全空（守卫4）** | scan abort：本周期**不买不卖** | note=`scan failed` + fault 快照 |
| xtdata 服务断（58610） | `ensure_ready` 启动即拦，含诊断指引 | CLI 错误退出 |
| 趋势闸阻断日 / 1、4 月空仓月（数据完好） | **合法清仓照常放行**（gate 回测口径，回撤减半的来源） | 快照 gate_passed=False 可辨识 |

## 四、已知限制（诚实校准，非本阶段缺陷）

1. **守护模式跨日**：as-of 别名在装配期做一次；跨日长跑时次日 scan 会因当日无 fundamental 行 fault abort（fail-safe，不产生错误决策）。影子盘按 runbook 手动周二 `--once`（每次启动重新装配），无碍；真守护需求出现时再做每日重装配。
2. **跨 mode 日预算共享**：影子盘 dry_run 单占 `daily_notional_cap`（¥320k）且跨 mode 统计 —— 未来切 live 当日若影子盘先跑过，live 预算被占。真单 Spec 需裁定（分 mode 预算或切换日清界）。
3. **min_confidence 对截面是死闸**（confidence 恒 1.0）：不承担 F01 过滤职责，仅约束 bar 策略（design DD-3 已载明）。
4. **执行流水不作一致性口径**：dry_run 透传真账户持仓 + DRY_RUN 不成交 → targets 是"对真实持仓的差额单"且不收敛；一致性以决策快照（同输入重放）为准（DD-8/K6）。真实持仓与 F01 组合的差异属执行层，纸面组合状态跟踪（假想净值）留下一步。
5. **比对脚本预期差异白名单**：price 不进 diff（前复权基准日漂移）；fundamental 别名滞后使影子盘用 T-1 快照而 gate 原回测用 T 日快照（无前视方向，边界选股可能差 1-2 只——首个真实调仓周二观察）。
6. 冒烟当日为周六（非调仓日 hold 语义 + 盘外拒单）：**调仓日全流程（top20 选股 + 40 单滚动 + 0-diff 比对）待 2026-07-07 首个周二实跑确认**。

## 五、下一步

- **2026-07-07（周二）**：按 runbook §5 首跑正式调仓采样 → 比对 exit 0 确认 → 此后每周二例行，攒前向样本。
- 攒 4-8 周样本 + 行为符合预期 → 开**真单 Spec**（前置：实时 fundamental 装配、分 mode 预算、纸面组合净值跟踪、`cancel_order` 实盘验证）。
