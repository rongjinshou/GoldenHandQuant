# Market Data Store 设计文档（DuckDB + 向量化特征引擎）

> 状态：已批准（用户授权"自己拍板，一路到底"，2026-06-11）
> 关联：`docs/feat/0610-factor-library/2026-06-11-p0-verdict-report.md`（动机来源）

## 1. 背景与动机

第一轮 P0 因子判决暴露了两个结构性问题：

1. **算力浪费**：截面特征（18 个技术指标 × 5207 只 × 1212 日 ≈ 565 万行）每次
   `factor-test` 都在内存重算（纯 Python 逐日逐股，~2 小时），进程结束即丢弃。
   Phase 1 要反复跑漏斗，这个成本不可接受。
2. **正确性缺陷**：`CrossSectionBuilder._compute_bar_metrics` 中
   `return_20d = (closes[-1] - closes[0]) / closes[0]`，在 120 根窗口下实际是
   ~119 日收益（对照 `return_5d` 用 `closes[-6]`、`return_60d` 用 `closes[-61]`）。
   F02 短期反转与中性化控制变量都建立在这个错误特征上。

用户拍板的两个架构决定：

- **打破 domain 第三方库红线**（允许纯计算库）
- **市场数据落库，后续只做刷新**（存储引擎选型 DuckDB，用户确认）

## 2. Domain 红线变更

红线的真实意图是"领域逻辑无副作用、可独立测试、不依赖外部环境"，而非"不能用
高性能数值库"。变更为：

| | 旧规则 | 新规则 |
|---|---|---|
| 纯计算库 numpy / pandas / scipy | ❌ | ✅（无 I/O、无网络、无全局状态） |
| 数据源 SDK（xtquant / tushare） | ❌ | ❌（infrastructure） |
| 存储引擎（duckdb / sqlite3 包装） | ❌ | ❌（infrastructure） |
| Web 框架 / 可视化 / ML 训练库 | ❌ | ❌（interfaces / infrastructure） |

落地动作：更新 `CLAUDE.md` 与 `docs/rules/architecture.md` 对应条款。

## 3. 存储引擎选型

**DuckDB**（用户确认）。理由：列存分析型，全表扫描比 SQLite 快 1-2 个数量级；
`.df()` 零拷贝进 pandas，与向量化引擎天然衔接；单文件零运维。备选项 SQLite
（零依赖但行存扫描慢）、Parquet 分区文件（读快但无 UPSERT/SQL）被否。

- 库文件：`data/market.duckdb`（与现有 csv 缓存同目录）
- 现有 SQLite（`data/backtest.db`，orders/trades/positions 事务型数据）**不动**——
  两种负载形态不同，各用各的引擎
- 并发模型：DuckDB 单写者。本项目所有写路径都是单进程 CLI，可接受；
  同时跑两个写进程会得到明确的锁错误而非静默损坏

## 4. 表设计

五张表，全部带 `source` 列支持多数据源（'qmt' / 'tushare'）。日期统一 DATE 类型，
API 边界转 `"YYYY-MM-DD"` 字符串（与现有代码约定一致）。

```sql
CREATE TABLE IF NOT EXISTS instruments (        -- 股票池（离线可跑全市场）
    symbol      VARCHAR NOT NULL,
    source      VARCHAR NOT NULL,
    name        VARCHAR NOT NULL,
    list_date   DATE,
    delist_date DATE,                            -- NULL = 未退市
    updated_at  TIMESTAMP NOT NULL,
    PRIMARY KEY (symbol, source)
);

CREATE TABLE IF NOT EXISTS bars (                -- 前复权日线
    symbol     VARCHAR NOT NULL,
    date       DATE NOT NULL,
    source     VARCHAR NOT NULL,
    open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
    volume     DOUBLE,
    prev_close DOUBLE,                           -- 前收（涨停价计算用）
    PRIMARY KEY (symbol, date, source)
);

CREATE TABLE IF NOT EXISTS fundamental_snapshots (  -- 日度基本面
    symbol VARCHAR NOT NULL,
    date   DATE NOT NULL,
    source VARCHAR NOT NULL,
    name VARCHAR, list_date DATE,
    market_cap DOUBLE,
    roe_ttm DOUBLE, ocf_ttm DOUBLE,
    pe_ratio DOUBLE, pb_ratio DOUBLE,
    earnings_growth DOUBLE, revenue_growth DOUBLE,
    PRIMARY KEY (symbol, date, source)
);

CREATE TABLE IF NOT EXISTS stock_features (      -- 截面特征（无前视约定固化）
    symbol VARCHAR NOT NULL,
    date   DATE NOT NULL,                        -- 快照日 T
    feature_version INTEGER NOT NULL,
    -- T-1 信息 bar（特征只许用 T-1 及更早）
    open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
    volume DOUBLE, prev_close DOUBLE,
    exec_close DOUBLE,                           -- T 日收盘 = 执行价
    -- 18 个技术指标（全部算自 T-1 及更早）
    return_5d DOUBLE, return_20d DOUBLE, return_60d DOUBLE,
    volatility_20d DOUBLE, volatility_60d DOUBLE,
    turnover_rate DOUBLE, avg_turnover_20d DOUBLE,
    rsi_14 DOUBLE, macd DOUBLE, macd_signal DOUBLE,
    ma_5 DOUBLE, ma_20 DOUBLE, ma_60 DOUBLE,
    high_20d DOUBLE, low_20d DOUBLE, atr_14 DOUBLE,
    skewness_20d DOUBLE, illiquidity_20d DOUBLE, obv_slope_20d DOUBLE,
    PRIMARY KEY (symbol, date, feature_version)
);

CREATE TABLE IF NOT EXISTS fetch_meta (          -- 履约区间（只刷缺口的依据）
    source     VARCHAR NOT NULL,                 -- 'qmt' / 'tushare' / 'engine'
    table_name VARCHAR NOT NULL,                 -- 'bars' / 'fundamental_snapshots' / 'stock_features:v1'
    symbol     VARCHAR NOT NULL,                 -- 基本面整批拉取用 '*'
    fulfilled_start DATE NOT NULL,
    fulfilled_end   DATE NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (source, table_name, symbol)
);
```

设计要点：

- **`stock_features` 行键是快照日 T，特征算自 T-1**——与
  `tests/application/test_factor_test_app.py` 钉死的三个约定（无前视 / T-1 信息 /
  warmup）一致，约定固化进表结构而非散落在管道代码里
- **基本面不冗余进特征表**：读取时 join（DuckDB 毫秒级）。基本面刷新不触发特征重算
- **特征版本化**：特征定义变更 → bump `FEATURE_VERSION` → 全量重算为新版本行，
  新旧版本可共存对比。`feature_version=1` 的口径 = 修复 `return_20d` 之后
- **多源不静默混合**：单次查询固定一个 source（按配置优先级），v1 不做跨源合并

## 5. 刷新机制（只拉缺口）

`fetch_meta` 记录每 (source, table, symbol) 的已履约闭区间。请求 [start, end] 时：

- 无记录 → 全量拉取
- 有记录 → 只拉 [start, fulfilled_start) 和 (fulfilled_end, end] 两侧缺口
- upsert 后履约区间取并集 [min(start, 旧start), max(end, 旧end)]

**简化声明**：区间并集假设两次请求区间相邻或重叠（与现有 csv `_fetch_meta.json`
同口径）。日常用法（固定研究窗口 + 向今天滚动的增量刷新）满足该假设；跳跃式
请求会产生虚假覆盖声明，文档明示不支持。

特征表的"刷新"= 重算：某 symbol 的 bars 覆盖区间变化后，**整只重算**该 symbol
的特征序列（向量化下单只毫秒级，不做尾部增量的复杂逻辑）。

QMT 基本面接口为整批拉取（无 per-symbol 粒度），meta 以 `symbol='*'` 记一行。

## 6. 向量化特征引擎

新建 `src/domain/market/services/feature_engine.py`（domain 层，红线变更后合法）：

- 输入：单 symbol 按日排序的 OHLCV 序列（pandas DataFrame）
- 输出：该 symbol 全时段特征 DataFrame，行 = 快照日 T（自第 2 根 bar 起），
  特征列全部由 **T-1 及更早** 的数据 rolling 计算（shift(1) 后算窗口）
- 替代"每日 × 每股 × 120 根重算"，预期全市场特征构建从 ~2 小时 → 分钟级

### 语义钉死（相对手写版 `CrossSectionBuilder`）

| 特征 | 语义 | 与手写版关系 |
|---|---|---|
| return_5d / 60d | pct_change(5/60) @ T-1 | 严格等价（1e-9） |
| **return_20d** | pct_change(20) @ T-1 | **修复**：手写版为 closes[0] bug |
| volatility_20d/60d | 日收益样本标准差（ddof=1） | 严格等价 |
| skewness_20d | 总体偏度（÷n，样本 std） | 严格等价 |
| rsi_14 | Cutler 式（近 14 日涨/跌简单平均） | 严格等价 |
| atr_14 / ma / high_20d / low_20d | 固定窗口 | 严格等价 |
| turnover_rate / avg_turnover_20d | vol[-1]/20日均量、20日均量 | 严格等价 |
| illiquidity_20d | Amihud 近 20 日均值 | 严格等价 |
| obv_slope_20d | OBV 近 20 点线性回归斜率 | 严格等价（OBV 平移不变） |
| macd / macd_signal | **标准全历史递推 EMA** | 有差异（手写版为 120 窗重启近似，量级 ~1e-6），文档明示；P0 因子不使用 |

手写版 `CrossSectionBuilder` **保留**（strategy_runner / ml_pipeline / data_loader
等调用方不动），并作为 golden test 的参考实现与向量化版互证。

## 7. 管道接入（runner 零改动）

新建 `src/application/market_data_app.py` — `MarketDataAppService`：

```
ensure_instruments()                     # 在线则刷新股票池，离线用库内存量
ensure_bars(symbols, start, end)         # 对照 fetch_meta 拉缺口 → upsert
ensure_fundamentals(start, end)          # 同上（整批，symbol='*'）
ensure_features(symbols, start, end)     # bars 覆盖变化的 symbol 整只重算
load_cross_sections(symbols, start, end) # SELECT features JOIN fundamentals
                                         # → (snapshots_by_date, returns_by_date, prices_by_date)
```

- `FactorTestAppService` 增加可选 `market_data` 服务注入：有 → 走库（CLI 真实路径）；
  无 → 原内存路径（已有 stub 测试与小股票池场景不变）
- `load_cross_sections` 输出与现有 `prepare_snapshots` 完全同构，
  `FactorTestRunner` / 判决逻辑零改动
- returns 仍由 exec_close 推（`_compute_forward_returns`，按实现日键入），不落库
- CLI：`quant data refresh --start --end [--config]`（手动刷新）、
  `quant data status`（覆盖率概览）；`factor-test` 默认自动 ensure：
  库覆盖 → 离线直接跑；有缺口且 QMT 在线 → 自动补；离线 → 明确报错
- 现有 csv 缓存过渡期保留不删，DB 为唯一可信源；待稳定后另行退役

## 8. 测试策略

1. **golden 等价测试**：随机游走 OHLCV（~150 根 × 多只），手写版逐日跑（复刻
   prepare_snapshots 的 120 窗循环）vs 向量化版，固定窗口特征 |diff|<1e-9；
   macd 系相对容差 1e-3；return_20d 按修复口径单独断言
2. **store 单测**：upsert 幂等、缺口计算（无记录/左缺/右缺/全覆盖）、特征版本隔离、
   日期字符串边界（`:memory:` 库，WSL/Windows 都能跑）
3. **管道特征化测试**：无前视 / T-1 / warmup 三个约定在 **DB 路径**上重验
   （temp duckdb + stub fetcher，复用现有测试的数据构造）
4. 全量 suite + ruff 通过

## 9. 性能预期与未来工作

| 环节 | 现状 | 落地后 |
|---|---|---|
| 行情/基本面获取（已缓存窗口） | csv 逐文件读 + 整批基本面在线重拉 | DuckDB 扫描，秒级 |
| 特征构建（全市场 5 年） | ~2 小时（每次） | 首次分钟级，命中后 0 |
| factor-test 端到端（数据就绪后） | ~2.5 小时 | 分钟级 |

未来（明确不在本次范围）：FactorTestRunner 直接消费 DataFrame（免 565 万
StockSnapshot 对象构造）；跨源数据对账；分钟线表；csv 缓存退役。

## 10. 落地顺序

见同目录 `2026-06-11-market-data-store-plan.md`（实施计划）。
