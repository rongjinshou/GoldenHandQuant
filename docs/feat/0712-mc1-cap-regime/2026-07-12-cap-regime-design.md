# MC-1 清偿：市值口径统一为时点总市值 设计

| 项 | 值 |
|---|---|
| **状态** | 已定稿（全自主模式，决策自裁记 `docs/rules/decision-log.md`） |
| **创建日期** | 2026-07-12 |
| **前置** | MC-1 立案（debt-ledger）：QMT 股本字段语义不一致+当前值回填历史 → top20 两口径重叠仅 3/20；方案 C 离线重验总市值版 gate=**PASS**（OOS 回撤 10.87%<基准 14.78%、闸增益不蒸发）→ 按 A 切换。修正源已沉淀：`ts_daily_basic.total_mv`（时点正确，2010→今，含退市） |
| **时间约束** | 周二 07-14 影子盘首采前完成 → 新口径从第一采起算，日历零成本 |

## 一、目标与范围

把 `fundamental_snapshots.market_cap` 的语义从"QMT 股本×价"统一为**时点总市值**：历史一次性迁移 + 日增量同步 + 门禁跨源固化 + 判决/基线重跑。存储单点已确认（`stock_features` 无市值冗余列），修一列全链生效（回测/因子/影子/实盘同源）。

**非目标**：pe_ratio/pb_ratio 同族失真（QMT 派生列可能用同一错误股本）——挂 **MC-2 观察**（F01 不消费 pe/pb，F20/F21 因子消费——重启研究线前必须先审计，`ts_daily_basic.pe/pb` 对照源已在手）；C1-b 面板口径（另案）；前复权事实层（E10 另案）。

## 二、设计决策（DD，自裁留痕）

- **DD-1 存储**：`ALTER TABLE fundamental_snapshots ADD COLUMN market_cap_qmt DOUBLE`——迁移前把原值备份进新列（可回滚/可审计），`market_cap` 升级为总市值语义。qmt 与 akshare（退市回填）两源行同样处理。
- **DD-2 历史迁移**（`scripts/migrate_market_cap.py`，幂等）：
  1. 备份：仅当 `market_cap_qmt IS NULL` 时 `SET market_cap_qmt = market_cap`（重复跑安全）；
  2. 直配：按 (symbol, date) 用 `ts_daily_basic.total_mv×1e4` 覆写；
  3. 缺口（停牌日等 tushare 无行）：该股 **≤10 交易日内最近前值 as-of** 填充；
  4. 仍缺：保留 QMT 值 + 计数，报告 `data/mc1_migration_report.json`（覆写/回填/保留三段统计 + 抽查样例）。
- **DD-3 日增量**（`scripts/sync_market_cap.py`）：对 bars 最新交易日拉 `daily_basic(trade_date=该日)` 覆写当日行；tushare 不可用 → akshare `stock_zh_a_spot_em` 总市值兜底（盘后≈收盘口径）；双败 → **退出码 1 高声告警**（口径漂移风险必须显性，不静默回退 QMT 口径）。接线：`shadow_tuesday` 编排上午段 refresh 之后、auto-trade 之前新增一步；CLAUDE.md 命令区收编。
- **DD-4 门禁跨源固化**（`data_quality.py` 增两项，Control）：
  - **C8 市值跨源偏差**：最新共同日抽样对照 tushare，`|ours/theirs−1|>2%` 的占比 >1% → FAIL；tushare 库不可用 → SKIP（不绑死外部依赖）；
  - **C9 名称新鲜度**：instruments.name 与 `ts_stock_basic`/bak 最新名不一致计数，>50 只 WARN（观察级不 FAIL）。
  同批做掉名称刷新：`scripts/refresh_instrument_names.py` 用 ts_stock_basic(上市)+bak 末日名更新 instruments.name。
- **DD-5 重跑与等价性验证**：① 主 gate 脚本重跑（读迁移后库）——判据结论须与 overlay 版一致（PASS），四格数字容差 ±2pp 内（迁移含 as-of 回填、overlay 无，允许微差）；② `quant factor-test --factors P0` 重跑换代 verdict；③ `run_f01_investability` 三组重跑立新基线（params 标 `"cap": "total_mv"`）。
- **DD-6 影子盘**：live 装配读同一列，代码零改动；07-14 首采即新口径。`f01_totalmv_gate.py` 完成历史使命后保留（作口径对照工具）。

## 三、数据流（迁移后稳态）

```
历史: ts_daily_basic(tushare 沉淀) ──migrate──▶ fundamental_snapshots.market_cap
日增: data refresh(QMT 写 market_cap_qmt 口径) ──sync_market_cap──▶ 覆写当日 market_cap
                                                    │ tushare 主 / akshare spot 兜底 / 双败告警
消费: FundamentalRegistry → 回测/因子/影子/实盘(同一列, 全链自动新口径)
门禁: C8 跨源偏差 每次 data status --check 拦截漂移回归
```

**注意**：refresh 的 QMT fetcher 不改（它写的值将被 sync 覆写；保留其值进 `market_cap_qmt` 的语义由迁移列承担——fetcher 写 market_cap 后 sync 覆写前的短窗口只存在于运维链内部，编排器保证顺序）。

## 四、验收

1. TDD：迁移合并规则（直配/as-of 回填 ≤10td/保留计数）、sync 源选择与双败退出、C8/C9 门禁判定——先红后绿；
2. 迁移实跑：覆写率 ≥99%（主板近满覆盖），报告落盘；审计复查（07-10 中位比值 → 1.000）；
3. 等价性：主 gate PASS 且与 overlay 数字容差内；factor-test/investability 重跑入库；
4. `verify_all` 全绿（含新 C8/C9）；
5. 文档：本设计+plan+report、debt-ledger MC-1 核销/MC-2 挂账、decision-log、CLAUDE.md、runbook（shadow_tuesday 新步骤）。

## 五、风险与诚实校准

- **口径切换=策略定义换代**：新旧基线并存于 backtest_runs（repro 标签区分），禁止跨口径比较收益数字；0626 阶段0 gate 的历史结论标注"旧口径"。
- **tushare 账号死亡**：日增量自动落到 akshare spot 兜底；C8 门禁在两源都漂移时报警。akshare spot 与 tushare 收盘口径的微差（盘后快照）计入 C8 的 2% 容差内。
- **as-of 回填 ≤10td**：长停牌股市值冻结在停牌前值——与"停牌不可交易"的现实一致，无前视。
- MC-2（pe/pb 同族失真）在研究线重启前是已知未审计区，台账明示。
