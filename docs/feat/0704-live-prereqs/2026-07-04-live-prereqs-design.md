# 真单 Spec 前置三件套 — 设计（分 mode 预算 / 纸面净值 / 实时 fundamental 裁定）

| 项 | 值 |
|---|---|
| **状态** | 已定稿（用户点名三件，2026-07-04；决策自裁留痕） |
| **定位** | 影子盘攒样本期间（07-07 起每周二）并行准备的真单前置；**不含真单 Spec 本体**（三重确认流程/首单 runbook/cancel_order 实盘验证等，攒够样本再开） |
| **前置** | 0626 影子盘阶段 1（signal_snapshots/比对闭环）；0611 closed-loop（TradingStore/盘前闸）；0704 B1（回测数字置信度上调） |

## DD-1 · 分 mode 日预算与同日去重（修"影子盘吃掉 live 预算"的坑）

**现状**：`TradingStore.today_submitted_notional` / `today_traded_keys` 跨 mode 统计（0611 设计意图："dry_run/live 背后是同一真实账户，切换模式不得重置日级预算防线"）。

**重裁定**：该意图成立于"dry_run 是偶尔试跑"的时代。影子盘常态化后，dry_run 是**每周二 ~¥29 万的例行意向流**且永不成交（无真实敞口）——它占用 live 真钱预算是错误语义：切 live 当日预算立即"耗尽"、同 symbol 被去重拒单。**改为按 mode 隔离**：两方法加 `mode` 参数（`WHERE mode=?`），调用点传 `self._cfg.mode`。live 自身的日预算/去重防线完整不变；dry_run 意向不再污染。调用点仅 `auto_trade_app.py` 两处，旧数据零迁移。

## DD-2 · 纸面组合净值 = 周度理论净值入库（复用回测基建，不造纸面账本）

**问题**：影子盘 dry_run 单不成交，没有"跟着 F01 做会到哪"的净值曲线可看。

**裁定**：不做纸面账本（那是第二套撮合逻辑 = 第二事实来源）；**理论净值 = 只主板 F01+趋势闸回测**（gate 同款装配，被 golden 锁定的撮合语义，[[reuse-not-recompute]]）。新脚本 `scripts/shadow_paper_equity.py`：

- 窗口 = 影子盘上线日 **2026-07-04 → 当日**，¥146k、top20、趋势闸 ON、只主板（`check_symbol_scope`）；
- 产出经 `build_backtest_run_row` → `insert_backtest_runs` 入库，`run_id = SHADOW-PAPER-<YYYYMMDD>`（每周覆盖式新增一行，历史周留档可回看漂移）→ **驾驶舱回测页天然可见，零 UI 改动**；
- 挂 runbook §5 周二流程第 ⑤ 步（收盘 refresh 之后）；窗口早期只有数根 bar、指标无统计意义——脚本如实输出不装样子。

## DD-3 · 实时 fundamental：裁定真单继续 T-1 as-of 口径 + 补一个真风险防御（实时 ST 闸）

**裁定不升级实时市值口径**，理由：
1. 影子盘一致性验证的就是「DuckDB T-1 as-of」口径——换实时口径 = 推翻已完成的验证重来；
2. T-1 收盘市值 vs 盘中实时市值的差异 = 一夜涨跌对微盘排序的扰动，方向无偏、量级小（微盘隔夜 ±3% 通常不实质改变 top20 成员）；
3. 回测口径本身用 T 日收盘市值（含轻微前视），实盘 T-1 反而更保守无前视。

**留档触发条件**：影子盘周二比对若持续出现"选股边界股因隔夜涨跌错位"类 diff，再议实时口径（届时需同步升级比对基准）。

**但补一个 T-1 口径挡不住的真风险**：当日刚戴帽（ST/*ST）的股票 —— DuckDB T-1 的 name 还是旧名，F01 的 ST 过滤失效，可能对其发买单；现有盘前六闸不查名称（`check_symbol_scope` 只查板块）。**加实时 ST 闸**：
- domain：`pre_trade_checks.check_st_name(name: str | None) -> str | None` 纯函数（None=放行——名称不可得时不误拦，与报价新鲜度闸的职责分离；前缀口径同 `filter_st`：ST/*ST/SST/S*ST）；`run_pre_trade_gates` 加可选 `instrument_name: str | None = None`，仅 **BUY** 方向检查（卖出退出不该被拦）；
- infrastructure：`QmtRealtimeQuoteFetcher.get_instrument_name(symbol) -> str | None`（`xtdata.get_instrument_detail` 的 `InstrumentName`，异常返 None——fail-open 交给闸的 None 语义，名称拿不到时由报价闸兜底）;
- application：`_execute_guarded` 在取报价处顺带取名称传入闸。dry_run 同样生效（QMT 在线时可得，影子盘即可观察该闸行为）。

停牌的实时防御**不需要新做**：现有「拿不到有效报价/报价过期 180s」闸已覆盖（停牌股无新鲜 tick → 拒）。

## 验收

1. TDD：分 mode 预算（同日 dry_run 单不占 live 预算/不触发 live 去重；同 mode 防线回归）；ST 闸（ST/*ST/SST/S*ST 拒买、正常名放行、None 放行、SELL 不拦）；
2. golden 全量 + ruff 干净；
3. `shadow_paper_equity.py` 实跑一次入库（窗口 7-04→当日，bars 尚少属预期）+ 驾驶舱回测页可见；
4. runbook §5 补第 ⑤ 步；报告 + memory 更新。
