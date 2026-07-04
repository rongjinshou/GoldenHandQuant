# B1 退市股 akshare 近似回填 + F01 敏感性复跑 — 设计

| 项 | 值 |
|---|---|
| **状态** | 已定稿（用户批准 akshare 替代 Tushare 路线，2026-07-04） |
| **定位** | **近似修正 / 敏感性检验**，非干净点对点修正（干净版仍需 Tushare pro/Wind）。研究侧任务：把 F01 绝对收益的"生存者偏差高估量"从未知变成量化区间。**不碰影子盘/实盘链路。** |
| **前置** | B1 结构裁定（2026-06-14，factor-funnel memory）：趋势闸增益是同宇宙 ON−OFF 差值 → 偏差对冲，可投候选结论稳健；仅绝对数字是上界。本 Spec 量化该上界的折扣。 |

## 一、实测事实（2026-07-04，akshare 1.18.64）

| 项 | 结果 | 备注 |
|---|---|---|
| 退市清单 | SH 93 + SZ 123 = **216 只**（2021+） | `stock_info_sh_delist` / `stock_info_sz_delist`（后者 6-14 时不可用，已修） |
| 日线 qfq | 东财 `stock_zh_a_hist` 抽样 **15/15**；腾讯 `hist_tx` 15/15 | 6-14 的 ~8% 旧结论已过时；新浪 0/15 弃 |
| 财报三表 | `*_by_report_delisted_em` 抽样 **16/16**（SH+SZ） | 关键科目全可用：`PARENT_NETPROFIT` / `TOTAL_PARENT_EQUITY` / `SHARE_CAPITAL` / `NETCASH_OPERATE`，REPORT_DATE 齐全 |
| 不复权日线 | 待单发验证（探测时触发**东财限流** RemoteDisconnected） | 限流是硬约束 → DD-8；口径 fallback 链 → DD-3 |
| 消费侧硬门槛 | `filter_quality` 对 roe/ocf None **直接剔除** | 光回填 bars 无效，财务字段必须有（已验证可得） |

## 二、决策（DD）

### DD-1 · akshare = 静态回填源，不进 refresh 主链
新 `src/infrastructure/gateway/akshare_delisted_fetcher.py`（akshare import 只出现在此文件，domain 红线不破）。一次性回填脚本 `scripts/backfill_delisted_akshare.py`，幂等可重跑；QMT 仍是唯一活跃源。退市股数据是死的，不需要进 `data refresh` 编排。

### DD-2 · source='akshare' 物理隔离
三表 PK 均含 source，零新表零迁移。回填前防御校验：目标 symbol 在 `source='qmt'` 无行（防未来重叠双计）。

### DD-3 · 市值口径 fallback 链（防复权因子污染）
`market_cap = 不复权 close × SHARE_CAPITAL`（最近生效报告期的股本）。不复权价按序尝试：① 东财 `adjust=""` ② 腾讯 `hist_tx adjust=""` ③ 都不可得 → qfq 价近似并在 `instruments`/报告标注 `mcap_approx=qfq`（退市股无未来分红送转，qfq 基准=末日，多数票 qfq≈raw；有历史除权的个股市值失真，敏感性报告须列出该子集占比）。bars 表照旧存 **qfq**（回测撮合/收益口径与 QMT 活股一致）。

### DD-4 · 财报 as-of：REPORT_DATE + 90 天生效（防前视）
TTM 口径：利润表/现金流按报告期做 4 季滚动（Q 报缺失时用最近年报值近似，标注）；`roe_ttm = 净利润TTM / TOTAL_PARENT_EQUITY(期末)`、`ocf_ttm = NETCASH_OPERATE TTM`。**对齐检查**：实施时先读 `QmtFundamentalFetcher` 的 roe/ocf 计算口径，回填侧尽量逐项对齐，不一致处在报告注明。

### DD-5 · 每日 fundamental 行的日历 = 该股自身 bars 日期
有 bar 的交易日才有 fundamental 行（对齐 QMT 快照密度与 CrossSectionBuilder 的"bar+fund 同日才入宇宙"语义）；name=终名、list_date 来自清单/东财。

### DD-6 · name 用终名 + 两组 ST 口径敏感性
历史更名序列不可得。复跑出两组：**严格**（ST 闸照剔终名带帽者 → 修正量下界）与**宽松**（跳过 ST 闸 → 上界）。诚实给区间，不假装精确。

### DD-7 · 宇宙开关：默认行为零变化
`build_backtest_cross_section` 加可选参 `include_sources: tuple[str, ...] = ("qmt",)`；`MarketDataStore.load_symbols`/`DuckDBFundamentalFetcher` 相应支持多 source。影子盘/实盘装配（默认参数）字节级不变。

### DD-8 · 限流工程
请求间隔 ≥0.6s + 指数退避重试 ×3 + **symbol 粒度断点续传**（已入库的跳过，幂等 upsert 兜底）。216 只 × (日线 2 + 财报 3) ≈ 1100 请求 ≈ 15-25 分钟。

### DD-9 · 回测引擎退市强平（复跑可信的前提）
现状：持仓股 bars 断流后卖单无执行价发不出，持仓变僵尸（估值冻结、永不释放现金）。加**退市强平**：回测循环日终，持仓股 `current_time > 该股末根 bar 日期` → 按末根 close 全量强平（滑点/税费照常）。实现在 application 回测结算层（策略无关），默认开启但只有"末根日期 < 回测结束日"的股票会触发 —— 对纯 QMT 活股宇宙行为不变（活股末根=回测末日）。TDD 重点。

### DD-10 · 敏感性复跑矩阵
`scripts/b1_delisted_sensitivity.py`：F01+趋势闸（top20/¥146k/2021-01-01→2026-06-11/split 2024-06-30，同 gate 口径）×
{基线宇宙(qmt), 含退市宇宙(qmt+akshare)} × {严格 ST, 宽松 ST} × {闸 ON, OFF} 的 IS/OOS 指标并排表 +
退市股入选统计（被 F01 选中过的退市股次数/持有日/贡献损益）。产出 = 绝对数字折扣区间 + 防御画像/闸增益是否仍成立。

## 三、非目标
不做 Tushare/Wind 干净回填；不改影子盘与实盘任何路径；不做退市股 stock_features（F01 `uses_bar_history=False` 不需要）；不回填 2021 前退市（窗口外）。

## 四、验收
1. 回填核数报告：清单 216 vs 实际入库（bars 覆盖率/财报覆盖率/市值口径分布 raw vs qfq-approx）。
2. 双源对账：抽 20 只东财 vs 腾讯逐日 close 相对差 <0.1%。
3. 引擎强平 TDD：断流持仓在末根次一交易日被强平、现金释放、活股行为零变化（golden 全绿）。
4. 敏感性矩阵报告落 `docs/feat/0704-b1-delisted-backfill/`，结论写明：绝对收益折扣、MDD 变化、OOS 闸增益（ON−OFF）是否保留。
