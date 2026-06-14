# 列式向量化因子引擎 实现计划 — Phase 1（B8）

> **执行方式**：TDD，逐任务红→绿→提交。每个向量化单元都有 golden 等价测试对照对象式 oracle。
> 设计见同目录 `*-design.md`。等价陷阱见设计 §6（E1–E10），实现时逐条对照。

**Goal:** 因子检验离线路径全程列式向量化，绕开 580 万 `StockSnapshot` 物化；新路径判决与旧对象路径逐位一致。

**Architecture:** 平行列式引擎（strangler）。新增 `VectorizedEvaluator`(domain) + `FactorPanel`/`VectorizedSeriesBuilder`/`VectorizedRunner`(infra)，复用现有 AST/parser/field_mapping 与 `LayerBacktester` 的纯归约静态方法。旧路径保留为 golden oracle。

**Tech Stack:** Python 3.13 / pandas / numpy / pytest。

---

### Task 1：VectorizedEvaluator — 逐元素算子

**Files:**
- Create: `src/domain/strategy/factor_test/vectorized_evaluator.py`
- Test: `tests/domain/strategy/factor_test/test_vectorized_evaluator.py`

- [ ] **Step 1：写失败测试** — 对照对象式 `FactorExpressionEvaluator`：构造一个单日 `DataFrame`（含 date + market_cap/pe_ratio/return_20d 等列，含 None/0）与等价 `list[StockSnapshot]`，断言两者对 `pe_ratio`、`0 - log(market_cap)`、`earnings_growth / pe_ratio`（含除零股）、`abs(...)`、`sign(...)` 的输出 dict 一致（NaN 股两边都缺）。
- [ ] **Step 2：跑测试确认失败**（模块不存在）。
- [ ] **Step 3：实现** `VectorizedEvaluator.evaluate(expr, df) -> pd.Series`（index 对齐 df）：
  - `LiteralExpr` → `pd.Series(v, index=df.index, dtype=float)`
  - `FactorRefExpr` → `pd.to_numeric(df.get(resolve_field_name(name)), errors='coerce')`；列缺失→全 NaN（E10）
  - `BinOpExpr` → 逐元素；`/` 时 `right.replace(0, np.nan)` 后相除（E3）
  - `abs`/`sign`（`np.sign`）逐元素；`log` → `np.where(s>0, np.log(s), np.nan)`（E4）
  - 提供 `as_dict(series, df)` 辅助：`{symbol: val}` 丢 NaN，用于 golden 对照。
- [ ] **Step 4：跑测试确认通过。**
- [ ] **Step 5：提交** `feat(factor): VectorizedEvaluator 逐元素算子 + golden 等价`。

---

### Task 2：VectorizedEvaluator — 截面函数 rank / zscore

**Files:** 同 Task 1（追加）。

- [ ] **Step 1：写失败测试** — 多日面板，含并列值、全相等列、单股日。断言 `rank(pe_ratio)`、`zscore(return_20d)`、`rank(roe_ttm)*rank(1/pb_ratio)` 与对象式逐日 dict 一致。**显式覆盖 E1/E2**：rank 用 `(r-1)/(n-1)`、全等→0.5、n==1→0.5；zscore 用 ddof=0、std==0→0。
- [ ] **Step 2：跑测试确认失败。**
- [ ] **Step 3：实现** `rank`/`zscore` 走 `s.groupby(df['date'])`：
  - rank：`r = s.groupby(g).rank(method='average')`；`cnt = s.groupby(g).transform('count')`；`out = (r-1)/(cnt-1)`；`cnt==1` 处 → 0.5（全相等天然 → 0.5，见设计 §6 E1 推导）。
  - zscore：`mean = transform('mean')`；`std = transform('std', ddof=0)`；`out = (s-mean)/std`；`std==0`→0；组内 n==1 → 0。
- [ ] **Step 4：跑测试确认通过。**
- [ ] **Step 5：提交** `feat(factor): VectorizedEvaluator 截面 rank/zscore（E1/E2 等价）`。

---

### Task 3：FactorPanel — 列式面板 + 前向收益 + 切分

**Files:**
- Create: `src/infrastructure/factor_test/panel.py`
- Create: `src/application/` 改 `market_data_app.py` 增 `load_panel()`
- Test: `tests/infrastructure/factor_test/test_panel.py`

- [ ] **Step 1：写失败测试** — 用一个构造的 join DataFrame（多股多日 + 缺价日）建 `FactorPanel`，断言：(a) 前向收益与对象式 `_compute_forward_returns(prices_by_date)` 在每个 (实现日, symbol) 上一致（**E6 全局 next_date**）；(b) `slice_is(split)` / `slice_oos(split)` 行集与 `{d: ... if d<=split}` 一致。
- [ ] **Step 2：跑测试确认失败。**
- [ ] **Step 3：实现** `FactorPanel`：持 DataFrame（含 date/symbol/特征/价格列）；
  - `forward_returns()`：取各 date 排序，建 `date → next_date` 映射；按 symbol 对齐 `price[next]/price[cur]-1`，键入实现日(next)；`price[cur]<=0` 跳过。
  - `slice_is/slice_oos(split)`：布尔掩码切子 panel。
  - `MarketDataAppService.load_panel(symbols, start, end)`：`ensure 三连` 后 chunk 调 `load_feature_join_df` 拼 DataFrame，构 `FactorPanel`（**不建 StockSnapshot**）。
- [ ] **Step 4：跑测试确认通过。**
- [ ] **Step 5：提交** `feat(factor): FactorPanel 列式面板 + 前向收益（E6 等价）`。

---

### Task 4：VectorizedSeriesBuilder — IC 序列

**Files:**
- Create: `src/infrastructure/factor_test/vectorized_series.py`
- Test: `tests/infrastructure/factor_test/test_vectorized_series.py`

- [ ] **Step 1：写失败测试** — 对照 `ICCalculator.calculate_ic_series`：同一面板/收益下，向量化逐日 Spearman IC 序列与对象式一致（含 <3 股日 → IC=0，含并列）。
- [ ] **Step 2：跑测试确认失败。**
- [ ] **Step 3：实现** `ic_series(panel, factor_series, forward_returns)`：按实现日 join 因子(prev) 与收益(cur)，`groupby(date)` 内对 (factor, ret) 各自 `rank(method='average')` 再求 Pearson；组内共同股 <3 → 0（**E5**，复刻 `_rankdata` 平均并列）。
- [ ] **Step 4：跑测试确认通过。**
- [ ] **Step 5：提交** `feat(factor): 向量化 IC 序列（E5 Spearman 等价）`。

---

### Task 5：VectorizedSeriesBuilder — 分层日序列 + 复用归约

**Files:** 同 Task 4（追加）。

- [ ] **Step 1：写失败测试** — 对照 `LayerBacktester.run`：同面板/收益/num_layers/rebalance_days 下，向量化产出的 `LayerBacktestResult`（layer_returns / long_short_return / monotonicity / top_layer_return / benchmark_return / top_excess_return / excess_ir / excess_positive_rate）与对象式逐字段一致（1e-9）。覆盖 rebalance_days=1 与 >1。
- [ ] **Step 2：跑测试确认失败。**
- [ ] **Step 3：实现** `layer_series(panel, factor_series, forward_returns, num_layers, rebalance_days)`：
  - 按日 `groupby(date)`：对有因子值且有下期收益的共同股，按因子值排序，**整数切片分桶 `gs=n//L`、顶层吃余数（E7）**；调仓日(按 rebalance_days)才重排、算换手（新进占比，首次=1.0，E8）、持有期沿用成员（E9 状态机）；产 `layer_daily_gross/turnover`、`bench_daily/bench_daily_turnover`、`layer_annual_returns`。
  - **复用** `LayerBacktester._top_excess_net / _long_short_net / _monotonicity_score`（不改）算最终字段，返回 `LayerBacktestResult`。
- [ ] **Step 4：跑测试确认通过。**
- [ ] **Step 5：提交** `feat(factor): 向量化分层日序列 + 复用 L3/L4 归约（E7/E8/E9 等价）`。

---

### Task 6：VectorizedRunner — 整合 + 评分

**Files:**
- Create: `src/infrastructure/factor_test/vectorized_runner.py`
- Test: `tests/infrastructure/factor_test/test_vectorized_runner.py`

- [ ] **Step 1：写失败测试** — 对照 `FactorTestRunner.run`：小 fixture（~10 股 × 7 日）下，long_short 与 long_only 两 objective 的 `ScoredFactorTestReport` 全字段 + score + grade 一致。
- [ ] **Step 2：跑测试确认失败。**
- [ ] **Step 3：实现** `VectorizedRunner.run(...)` 签名对齐旧 runner：panel→factor_series→ic_series + layer_series→组装 `FactorTestReport`→复用现有评分函数→`ScoredFactorTestReport`。
- [ ] **Step 4：跑测试确认通过。**
- [ ] **Step 5：提交** `feat(factor): VectorizedRunner 整合 + 评分等价`。

---

### Task 7：向量化中性化

**Files:**
- Create: `src/infrastructure/factor_test/vectorized_neutralizer.py`
- Test: `tests/infrastructure/factor_test/test_vectorized_neutralizer.py`

- [ ] **Step 1：写失败测试** — 对照 `FactorNeutralizer.mean_neutralized_ic`：同面板下残差 IC 一致（含控制变量缺失日跳过、残差退化守门）。
- [ ] **Step 2：跑测试确认失败。**
- [ ] **Step 3：实现** `groupby(date)` 对 `[1, log(market_cap), return_20d]` `np.linalg.lstsq` 取残差（复刻 `_residualize` 的 y_scale/残差退化阈值），再走向量化 IC。
- [ ] **Step 4：跑测试确认通过。**
- [ ] **Step 5：提交** `feat(factor): 向量化中性化残差 IC 等价`。

---

### Task 8：接入 run_batch + 判决级 golden + 性能冒烟

**Files:**
- Modify: `src/application/factor_test_app.py`（`run_batch`/`run_single` 切向量化实现，保留对象路径开关）
- Test: `tests/application/test_factor_test_app_vectorized.py`

- [ ] **Step 1：写失败测试** — 从 market.duckdb 抽一个中等真实切片存小 parquet fixture（~300 股 × 250 日，一次性生成脚本），对 F01 + 全部 P3（9 因子）跑新旧两路 `run_batch`，断言每个因子 verdict 的 ic_mean/ir/top_excess/excess_ir/excess_positive_rate/monotonicity/score/grade/passed 逐位一致（1e-9）。
- [ ] **Step 2：跑测试确认失败。**
- [ ] **Step 3：实现** `run_batch` 走 `VectorizedRunner` + `load_panel`；保留 `engine="object"|"vectorized"` 开关（默认 vectorized），对象路径仍可走（回滚 + oracle）。
- [ ] **Step 4：跑测试确认通过；** 跑一次全窗口 F01 计时冒烟（`$WIN_PYTHON`），记录新耗时/内存对比旧 13min/12GB。
- [ ] **Step 5：提交** `feat(factor): run_batch 切列式向量化引擎（B8 关闭）+ 判决级 golden`。

---

### 收尾
- [ ] 全测试套件绿（`pytest tests/ --ignore=tests/infrastructure/gateway/`）+ `ruff check src/`。
- [ ] 更新 design doc 债务对账：B8 关闭、记录实测提速。
- [ ] 更新记忆 [[reuse-not-recompute]] / [[factor-funnel-status]]：B8 已关闭。
- [x] Phase 1 全绿提交后，再起 Phase 2（B7 回测复用列式源）。

---

## Phase 2（B7）实现计划 — 回测技术指标统一到 feature_engine（纠错）

**范围确认（Phase 1 后）**：`_compute_bar_metrics` 仅在 `CrossSectionalStrategyRunner`（**仅 BacktestAppService 实例化**，
实盘 `auto_trade_app`/`live_signal_service` 不经此路径）+ 因子检验对象路径(--no-store) + ml_train/data_loader 用到。
B7 聚焦**回测 runner**：把逐股 `_compute_bar_metrics`(手写, return_20d 口径 bug) 换成 `feature_engine`(向量化纠错版,
即 stock_features 的同一引擎)→ 回测与因子检验**指标口径统一**。F01/MicroValue `uses_bar_history=False` 不触发, 结论不变。

**关键对齐**：喂 `feature_engine.compute_symbol_features` **完整窗口**(`info_bars + [exec_bar]`, 末根=T),
取**末行**技术列 = `shift(1)` = as-of-T-1 → 正是快照(T-1 信息)语义, exec_close=T。与旧 `_compute_bar_metrics(info_bars)`
仅在 return_20d(纠错)+macd(~1e-6 EMA)处不同。

**决策**：`StoredFeatureSource`(离线读 stock_features 免重算)留作可插拔的后续性能项(抽象已就位), 本期不建(YAGNI;
回测非当前性能痛点, 痛点是因子检验已由 B8 解决)。

### Task B7-1：FeatureEngineSnapshotSource
- Create `src/domain/market/services/snapshot_feature_source.py`；Test 镜像。
- [ ] 测试: `features_for(symbol, window_bars)` 返回的技术列 dict == `feature_engine.compute_symbol_features(full_df).iloc[-1]` 的 TECHNICAL_COLUMNS(NaN 略去)。
- [ ] 实现: 把 list[Bar] → bars_df(symbol/date=timestamp/OHLCV/prev_close) → compute_symbol_features → 末行 TECHNICAL_COLUMNS dict。

### Task B7-2：build_cross_section 支持 precomputed_features
- [ ] 测试: 传 `precomputed_features={sym:{...}}` 时快照技术字段取自它(不调 _compute_bar_metrics); 不传时维持旧行为(回归)。
- [ ] 实现: `build_cross_section(..., precomputed_features=None)`; 有则用, 无则旧路径。

### Task B7-3：纠错等价（targeted diff）
- [ ] 测试: 同一窗口, 新(feature_engine 源)vs 旧(_compute_bar_metrics)产出的快照, **仅 return_20d 显著不同 + macd ~1e-6**, 其余技术字段一致 → 证明是定点纠错非回归。

### Task B7-4：接线 CrossSectionalStrategyRunner + 回测冒烟
- [ ] 测试/冒烟: runner 在 `uses_bar_history` 时用 FeatureEngineSnapshotSource(完整窗口)→ precomputed_features → build_cross_section; 跑一个用 return_20d 的截面策略小回测, 确认跑通且结果随纠错变化。
- [ ] 提交; 更新债务对账 B7 关闭。
