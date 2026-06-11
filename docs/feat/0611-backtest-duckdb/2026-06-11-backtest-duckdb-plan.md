# 回测接入 DuckDB 数据源 — 实现计划

> 单任务小型 Spec，TDD 一轮完成。设计：同目录 design 文档。

## Task 1: DuckDBHistoryDataFetcher（TDD）

**Files:**
- Create: `src/infrastructure/gateway/duckdb_history_data.py`
- Create: `tests/infrastructure/gateway_offline/test_duckdb_history_data.py`（离线目录，不依赖 xtquant）

步骤：
- [ ] 失败测试（六个场景见设计 §三；fallback 用栈式 fake 记录调用）
- [ ] 实现：read_only 连接 + 逐 symbol 查询 → Bar 列表；DAY_1 之外与零行走 fallback
- [ ] 测试绿 + ruff
- [ ] Commit: `feat(backtest): DuckDB 历史数据源 — 回测与研究共库, 离线可跑`

## Task 2: CLI 接线 + 真实冒烟

**Files:**
- Modify: `src/interfaces/cli/run_backtest.py`（fetcher 分支）
- Modify: `src/interfaces/cli/compare_strategies.py`（同分支）

步骤：
- [ ] 分支代码（QMT 回退可选，初始化失败降级无回退）
- [ ] 等 factor-test 批次释放写锁后冒烟：`run_backtest`（DuckDB 源, dual_ma）→ `backtest_runs` 有行 → 驾驶舱回测页可见
- [ ] Commit: `feat(cli): 回测默认支持 DuckDB 数据源 (--fetcher 经 backtest.yaml)`
