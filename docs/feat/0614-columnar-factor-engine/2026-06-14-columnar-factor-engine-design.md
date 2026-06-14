# 列式向量化因子/回测引擎 设计文档（B7+B8）

> 状态：设计稿（2026-06-14）。本 Spec 由用户在主线分叉处点名升格：
> "架构上是不是得优化了" + "逐日建全市场截面每次卡这里" → 决议「做列式向量化重构（独立 Spec，合并 B7+B8）」。

## 1. 背景与问题（卡顿的根因）

因子检验与回测的离线数据路径入口是 `MarketDataAppService.prepare → load_cross_sections`
（`src/application/market_data_app.py:136`）。它分两步，快慢天差地别：

1. **（快）DuckDB 一条 SQL 出列式截面。** `MarketDataStore.load_feature_join_df`
   （`market_data_store.py:309`）把 `stock_features ⋈ fundamental_snapshots` JOIN、按 `(date, symbol)`
   排序，`.df()` 直接吐出 pandas DataFrame。C++ 向量化、内部多线程，**返回的 DataFrame 本身已是按日排好的全市场截面**。
2. **（卡死处）把列式 DataFrame 反向量化成对象。** 紧接着 `for row in df.itertuples(): StockSnapshot(...)`，
   约 **4500 股 × ~1300 交易日 ≈ 580 万个 `StockSnapshot` 对象**，逐行、纯 Python、单线程、GIL 锁死单核。
   这是 36 核只用 1 核、13 分钟、12GB 内存的全部来源；itertuples 循环期间不打 stdout（管道块缓冲），所以"看着卡死、其实在磨"。

下游同样是对象式单线程：`ICCalculator.calculate_ic_series` 与 `LayerBacktester.run` 各自对每个日期调
`FactorExpressionEvaluator.evaluate(expr, snapshots[date]) → dict[symbol, float]`，再逐日算 Spearman IC / 排序分层。
`run_batch` 对每个因子重跑 IS + OOS + 中性化，全部串行。

**一句话定性：一次向量化的列式读，被立刻拆成 580 万个 Python 对象，再用单线程对象数学处理。**
这是 [[reuse-not-recompute]] 记录的 B8（单核）与 B7（回测 `_compute_bar_metrics` 手写重算 `stock_features` 已有指标）的共同根因。

### 关键重构边界（让范围收干净）

`LayerBacktester._top_excess_net` / `_long_short_net` / `_monotonicity_score` 是**纯 list 数学、已 L3/L4 正确、且很快**。
贵的只是"逐日建截面 + 求值 + 分层装桶"这段生成日序列的过程。因此本 Spec 的核心边界是：

> **只向量化「日序列的构建」（求值 → IC → 分层日收益/换手），复用已正确的「序列 → 记分牌」归约（`_top_excess_net` 等静态方法）。**

这把等价校验面缩到最小，记分牌数学逐位一致，性能瓶颈一刀切除。

## 2. 目标 / 非目标

**目标**
- B8：因子检验离线路径全程列式向量化，不再物化 `StockSnapshot`；全窗口单因子从 ~13min/12GB 降到秒级 / 百 MB 级。
- B7：截面回测（`CrossSectionBuilder` / `CrossSectionalStrategyRunner`）复用同一列式特征读，消除 `_compute_bar_metrics` 对 `stock_features` 已有指标的手写重算与口径不一致。
- **零行为漂移**：新路径产出的判决（IC/IR/分层/Top 超额/中性化/评分/grade）与旧对象路径在固定 fixture 上**逐位一致**（golden test 守门）。

**非目标（YAGNI）**
- 不改领域 `StockSnapshot` 契约、不删对象式 `FactorExpressionEvaluator`/`ICCalculator`/`LayerBacktester`——它们保留为单元测试契约 + golden-test 的 oracle。
- 不引入新依赖、不上 Spark/Polars；用已在用的 pandas/numpy + DuckDB。
- 跨因子多进程并行**先不做**：向量化本身的 ~100× 提速大概率已让批次进入分钟内；多进程留作 Phase 3 选项（behind a flag），先测后加。

## 3. 方案选型

| 方案 | 描述 | 取舍 |
|---|---|---|
| **A. 平行列式引擎 + golden 等价（推荐）** | 在对象路径旁新建列式引擎，DB 快路径切到新引擎；旧路径保留为 oracle + 单测契约 | 经典 strangler；爆炸半径小、可逐位校验、可回滚（切回入口即可）；多一份代码（可接受，旧路径本就是测试用小数据） |
| B. 原地重写对象路径 | 直接把 evaluator/IC/layer 改成列式，删 StockSnapshot 路径 | 一次到位无冗余，但爆炸半径大、破坏大量现有单测、无 oracle 可对照、回滚难 |
| C. 仅多进程并行对象路径 | ProcessPoolExecutor 把对象循环铺多核 | 创可贴：580 万对象物化 + 12GB 照旧，prepare 段不受益；杠杆低 |

**选 A。** 列式引擎是新增（strangler），对象路径不动，用作等价 oracle；证明等价后切生产入口，旧路径继续服务现有单测与小数据场景。

## 4. 架构设计

依赖方向不变（`interfaces → infrastructure → application → domain`）。新增物：

```
domain/strategy/factor_test/
  vectorized_evaluator.py     # 新：AST → pandas 列运算（纯计算, pandas 在 domain 红线允许）
infrastructure/factor_test/
  panel.py                    # 新：FactorPanel —— 列式面板 + 前向收益 + 日期轴
  vectorized_series.py        # 新：逐日 IC 序列 + 分层日收益/换手/基准序列（向量化）
  vectorized_runner.py        # 新：编排 panel → series → 复用 _top_excess_net 等 → FactorTestReport
application/
  factor_test_app.py          # 改：DB 快路径走 vectorized_runner（保留对象路径开关）
  market_data_app.py          # 改：新增 load_panel()（返回 FactorPanel，不建 StockSnapshot）
```

### 4.1 FactorPanel（列式面板）
- 由 `MarketDataStore.load_feature_join_df` 的 DataFrame 直接构造（chunk 拼接），列含：`symbol, date,
  <技术特征 _FEATURE_VALUE_COLS>, market_cap, roe_ttm, ocf_ttm, pe_ratio, pb_ratio, earnings_growth, revenue_growth, <价格列>`。
- 前向收益向量化：`returns[cur][sym] = price[cur]/price[prev] − 1`，键入实现日，**严格复刻全局 next_date 语义**
  （非 per-symbol shift；某日某股的前向收益 = 该股在**全局下一交易日**的收益）。实现：把每个 date 映射到全局下一个 date，按 (symbol, cur_date) 左连接价格差分。
- IS/OOS 切分 = panel 上的 `date <= split` / `date > split` 布尔掩码（替代字典推导深拷贝）。

### 4.2 VectorizedEvaluator（AST → 列）
walk 与对象式**同一份 AST/parser/lexer/field_mapping**（domain，复用），仅换求值后端为 pandas：
- `LiteralExpr` → 广播标量列。
- `FactorRefExpr` → `panel[resolve_field_name(name)]`（DSL 名解析后即 DataFrame 列名，无需重映射）；缺失 = NaN。
- `BinOpExpr` → 逐元素 Series 运算；`/` 除零 → NaN（对应旧版"丢弃该股"，下游 NaN 自动出局）。
- `UnaryFunc`：`abs`/`sign` 逐元素；`log` 仅 `v>0`（其余 → NaN）；`rank`/`zscore` 为**截面函数**，`groupby(date)` 变换。

### 4.3 VectorizedSeriesBuilder（日序列，向量化）
对 panel 一次性产出与旧 `LayerBacktester.run` 内循环**同形**的中间序列：
- `ic_series`：`groupby(date)` 对（因子列, 前向收益列）求 Spearman（秩 → Pearson，≥3 股守门，复刻 `_rankdata` 平均并列）。
- `layer_daily_gross[L][t]` / `layer_daily_turnover[L][t]`、`bench_daily[t]` / `bench_daily_turnover[t]`、`layer_annual_returns`：
  按日 `groupby(date)` 排序装桶（复刻整数切片分桶：`gs=n//L`，第 L−1 层吃余数）、等权日收益、相对上次调仓的换手率、覆盖池基准腿。支持 `rebalance_days`（持有期内沿用成员）。
- **随后把这些序列原样喂给现有 `LayerBacktester._top_excess_net` / `_long_short_net` / `_monotonicity_score`**（不动），得 L3/L4 记分牌——保证记分牌数学逐位一致。

### 4.4 VectorizedRunner（编排）
等价替换 `FactorTestRunner.run`：panel + expr → series → 归约 → `FactorTestReport` → 复用现有 `score_report` 评分 → `ScoredFactorTestReport`。签名与产物与旧 runner 对齐，`run_batch` 仅切换实现。中性化（`mean_neutralized_ic`）同样向量化：`groupby(date)` 对 `[1, log(market_cap), return_20d]` 最小二乘取残差再算 IC（复刻 `_residualize` 的退化守门）。

### 4.5 Phase 2：B7（回测复用列式源）
`CrossSectionBuilder._compute_bar_metrics` 改为从 `load_feature_join_df`/FactorPanel 读取 `stock_features` 已算指标，删手写重算；`CrossSectionalStrategyRunner` 对接。golden 等价：同一历史回测窗口，新旧 `BacktestReport` 关键指标（收益/回撤/Sharpe/每日权益）一致（容差仅来自浮点累加顺序，设 1e-9 相对容差）。

## 5. 等价性策略（正确性的核心）

**Golden 等价测试**是本 Spec 的守门人，不是附属。每个向量化单元都对照对象式 oracle：

1. **算子级**：随机/构造截面上，`VectorizedEvaluator` vs `FactorExpressionEvaluator` 对每个 AST 节点类型逐元素一致。
2. **序列级**：固定 fixture（多日、含并列/缺失/除零/单股层）上，向量化 `ic_series`、`layer_daily_gross/turnover`、`bench_daily/turnover` 与旧 `LayerBacktester.run` 内部序列一致。
3. **判决级**：对 F01 + 全部 P3（9 因子）在一个**中等真实切片**（如 300 股 × 250 日，来自 market.duckdb）上，新旧 `ScoredFactorTestReport` 的 ic_mean/ir/top_excess/excess_ir/excess_positive_rate/monotonicity/score/grade **逐位一致**（浮点 1e-9）。
4. **回测级（Phase 2）**：同窗口新旧 `BacktestReport` 一致。

## 6. 等价性陷阱清单（必须逐条复刻，否则静默漂移）

| # | 语义 | 旧实现 | 向量化复刻要点 |
|---|---|---|---|
| E1 | `rank` 百分位 | `rank/(n−1)`，全相等→0.5，n==1→0.5 | **不是** pandas 默认 `rank(pct=True)`（那是 `/n`）；用 `(rank(method='average')−1)/(n−1)` + 全等/单股特判 |
| E2 | `zscore` | 总体标准差（÷n） | pandas `.std()` 默认 ddof=1，须 **ddof=0**；std==0→0 |
| E3 | `/` 除零 | 丢弃该股 | → NaN，下游 dropna |
| E4 | `log` | 仅 v>0 保留 | v≤0 → NaN |
| E5 | Spearman | 平均并列秩 + 共同股 ≥3 守门 | 复刻 `_rankdata`；`groupby` 内 <3 股 → IC=0 |
| E6 | 前向收益 next_date | **全局**下一交易日（非 per-symbol） | date→全局 next date 映射后连接，勿用 `groupby(symbol).shift` |
| E7 | 分层装桶 | 排序后整数切片，`gs=n//L`，**顶层吃余数** | 复刻整数切片，**非** `qcut`（qcut 边界/并列不同） |
| E8 | 换手率 | 相对上次调仓新进成员占比，首次=1.0 | 调仓日才更新成员，持有期内沿用 |
| E9 | 截面不足 | `len(common) < num_layers` 时：无持仓跳过 / 有持仓过渡 | 严格复刻 has_membership 状态机 |
| E10 | 字段缺失 | `getattr(s, field, None)` 跳过 None | DataFrame 列 NaN 自动出局，须确认列存在（缺列 = 全 NaN，与旧"全跳过"一致） |

## 7. 性能预期
- 求值/IC/分层从 580 万对象 + Python 循环 → 单个 DataFrame 的 groupby 向量运算：内存 12GB → 数百 MB；单因子全窗口 13min（含共享 prepare）→ 秒级；批次 9 因子从 13min → 目标 <1min（无需多进程）。
- 若实测仍偏慢，Phase 3 才考虑 `ProcessPoolExecutor` 按因子并行（因子间独立）。

## 8. 测试策略
- 新增 golden 等价测试（§5）为主；算子/序列/判决三级。
- 复用真实切片 fixture 从 market.duckdb 抽取一次、存为小 parquet（避免每次连库）。
- 现有对象路径单测全部保留绿。
- ruff 干净；domain 新增 `vectorized_evaluator.py` 仅用 pandas/numpy 纯计算（红线允许）。

## 9. 风险与回滚
- **风险**：等价陷阱漏复刻 → 静默判决漂移。**缓解**：判决级 golden 对 9 因子逐位校验 + 算子/序列级细测；CI 守门。
- **回滚**：生产入口（`run_batch` 的实现选择）一行切回对象路径即可；新引擎为旁路，删除不影响旧路径。
- **风险**：浮点累加顺序差异。**缓解**：归约段复用旧静态方法（同序），求值段以 1e-9 相对容差断言。

## 10. 债务对账
- **B8（单核/物化）**：✅ **Phase 1 已关闭**（commit 5e4f9de…e7a8b82）。列式向量化绕开 StockSnapshot 物化。
  实测全窗口真实数据（5207 股 × 1316 日 = 597 万行，`scripts/perf_smoke_vectorized.py` 只读 market.duckdb）：
  - 装载 5.8s，**DataFrame 1.9GB**（旧 ~12GB，↓6×）；F01 long_only IS 跑 28.3s；**合计 34s**（旧对象路径 ≈13min，↑~23×）。
  - 等价：295 个 golden 测试逐位一致（算子/面板/IC/分层/衰减/中性化/runner/判决七级）+ IC=0.0212 与历史判决吻合。
  - 残留：分层日序列仍是单核轻量循环（无对象物化/无逐日 AST walk，已非瓶颈）；若需可后续向量化或按因子多进程（YAGNI，已达标）。
- **B7（回测重算）**：Phase 2 关闭——回测复用 `stock_features` 列式读，删 `_compute_bar_metrics` 重算。
- 关联记忆：[[reuse-not-recompute]]、[[factor-funnel-status]]。原 F01 Spec 债表 `docs/feat/0613-f01-investability/` B7/B8 标记 → 本 Spec。

## 11. 分期交付
- **Phase 1（B8，核心，先独立交付并提交）**：FactorPanel + VectorizedEvaluator + VectorizedSeriesBuilder + VectorizedRunner + 三级 golden 等价 + 切 `run_batch` 入口。可独立验证、独立提交。
- **Phase 2（B7）**：回测复用列式源 + 回测级 golden 等价。
- Phase 1 绿灯并提交后再起 Phase 2，各自独立全绿。
