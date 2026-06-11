# 回测接入 DuckDB 数据源 — 设计文档

| 项 | 值 |
|---|---|
| **状态** | 已定稿（整夜委托，文档留痕） |
| **创建日期** | 2026-06-11（夜） |
| **动机来源** | 夜审「巩固回测系统」：回测与因子研究两套数据路径（QMT fetcher 自带缓存 vs market.duckdb），口径分裂 + 回测依赖 QMT 在线 |

## 一、需求

- **R1**：回测可直接消费 `data/market.duckdb` 的前复权日线（与因子研究同一份数据，刚刷到 2026-06-11）。
- **R2**：QMT 不在线也能跑全市场回测（研究库自给自足）。
- **R3**：库内缺失的标的（如指数 000852.SH 等非股票池数据）可回退既有 QMT fetcher，不破坏 SystemRiskGate。
- **非目标**：分钟线（库仅日线）；CSV/Tushare 路径退役（保留并存）。

## 二、设计决策

- **DD-A 形态**：`DuckDBHistoryDataFetcher(IHistoryDataFetcher)`，放
  `src/infrastructure/gateway/duckdb_history_data.py`（与 tushare/qmt fetcher 同级同模式）。
  构造持有**单条 read_only 连接**（fetch 一次开一条连接在全市场回测下是 5000+ 次开销；
  read_only 与其他读者共存，仅与写进程互斥——回测期间不跑 refresh/factor-test，可接受并文档化）。
- **DD-B 查询**：逐 symbol `SELECT date, open, high, low, close, volume, prev_close FROM bars
  WHERE symbol=? AND date BETWEEN ? AND ? ORDER BY date` → `list[Bar]`（前复权，timeframe=DAY_1）。
- **DD-C 回退链**：`fallback: IHistoryDataFetcher | None`。命中条件：库内该 symbol 区间零行，或
  timeframe ≠ DAY_1。回退结果**不回写**库（库的写入权归 refresh 管道，单写者纪律）。
- **DD-D 接线**：`run_backtest.py` 的 `history_fetcher_type` 加分支
  `DuckDBHistoryDataFetcher`——默认带 QMT 回退（QMT 初始化失败则无回退、日志警告）。
  `compare_strategies.py` 同分支。
- **DD-E 错误处理**：库文件不存在/被写进程锁住 → 构造时抛明确异常（与「回测期间勿跑刷数」的
  运行纪律对应）；单 symbol 零行 → 回退或空列表 + warning（与 QMT fetcher 行为一致，回测主循环
  自然跳过无数据标的）。

## 三、测试策略

tmp DuckDB 用 `MarketDataStore.upsert_bars` 造数：①基本读取（行数/字段/前复权值/排序）；
②日期窗口裁剪；③缺失 symbol 走 fallback；④无 fallback 返回空；⑤非日线 timeframe 走 fallback；
⑥Bar.prev_close 透传。

## 四、验收

- [ ] 单测全绿；`ruff` 干净
- [ ] 真实回测冒烟：`run_backtest`（DuckDB 源）跑通并入库 `backtest_runs`，驾驶舱回测页可见净值曲线
