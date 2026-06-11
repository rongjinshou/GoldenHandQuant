# 数据获取与持久化规范 (Data Layer)

## 1. QMT (xtquant) 调用规范

绕过 QMT 底层 C++ 接口常见陷阱的强制规则：

### 1.1 历史行情 API

1. **禁用** `xtdata.get_market_data()`（返回 `{字段: DataFrame}` 反人类结构）。
2. **强制** `xtdata.get_market_data_ex()`（返回 `{stock_code: DataFrame}`，
   含 open/high/low/close/volume 完整字段）。
3. 用于回测与指标计算的 K 线必须 `dividend_type='front'`（前复权）。

### 1.2 时间格式

1. 请求参数：`YYYY-MM-DD` 必须去横杠转为 `YYYYMMDD`（或 `YYYYMMDDHHMMSS`）再传给
   `download_history_data` / `get_market_data_ex`。
2. 返回解析：时间在 DataFrame 的 `index` 里，必须 `pandas.to_datetime(df.index)`
   转标准 datetime 再向领域模型传递。

### 1.3 连接模型

1. **行情 (xtdata)**: 无状态调用，`import xtdata` 直接用；前提是本地 QMT 终端已启动。
2. **交易 (xttrader)**: 必须显式实例化 `XtQuantTrader`（`qmt_path` + `session_id`），
   严格执行 `connect()` + `subscribe()` 握手。撤单走
   `cancel_order_stock(account, int(order_id))`，result==0 表示受理。

### 1.4 透明缓存

1. 历史数据落盘以 `symbol + timeframe` 为联合主键：`data/{symbol}_{timeframe}.csv`
   （如 `000021.SZ_1d.csv`）。
2. 所有 `IHistoryDataFetcher` 实现必须防备性：先查本地缓存，命中则走本地 IO，
   避免重复打 QMT。

## 2. 数据源矩阵

| Fetcher | 路径 | 用途 |
|---|---|---|
| `QmtHistoryDataFetcher` | `gateway/qmt_history_data.py` | QMT K 线（需 Windows + 客户端） |
| `DuckDBHistoryDataFetcher` | `gateway/duckdb_history_data.py` | 回测直读研究库，QMT 离线可跑；仅日线，缺失标的回退 QMT；**用完必须 `close()`** |
| `TushareHistoryDataFetcher` / `TushareFundamentalFetcher` / `TushareIndexFetcher` | `gateway/tushare_*.py` | Tushare 备用源（需 token） |
| `QmtFundamentalFetcher` | `gateway/qmt_fundamental_fetcher.py` | QMT 财务数据 |
| `QmtRealtimeQuoteFetcher` | `gateway/qmt_realtime_quote.py` | 实时五档报价（实盘下单用） |

回测入口统一经 `build_history_fetcher()`（`src/interfaces/cli/run_backtest.py`）
按配置 `data.history_fetcher` 构建，三个回测 CLI 共用。

## 3. 双库格局（职责分离，严禁混用）

| | `data/market.duckdb`（研究库） | `data/trading.db`（交易留痕） |
|---|---|---|
| 引擎 | DuckDB | SQLite (WAL) |
| 表 | bars / fundamentals / features / factor_verdicts / backtest_runs | trading_cycles / execution_records / account_snapshots / position_snapshots / audit_logs |
| 写入方 | data refresh / factor-test / 回测入库钩子 | 自动交易循环 / 受控下单 |
| 访问类 | `MarketDataStore`（persistence/market_data_store.py） | `TradingStore` + `Database`（persistence/trading_store.py, database.py） |

**DuckDB 约束（实测教训）**：
- 单写者：refresh 写锁期间其他写连接/不同配置连接会失败。
- 同进程互斥：`read_only` 连接与写连接**配置不同不能共存**——fetcher 用完即
  `close()` 再开写连接（回测入库前必须释放数据源连接）。
- 只读消费端（驾驶舱 API）对缺表场景必须容错（`except duckdb.CatalogException`
  返回空，老库无新表不可 500）。

**SQLite 约束**：
- 守护线程写库必须 `check_same_thread=False`；`PRAGMA journal_mode=WAL` +
  `synchronous=NORMAL`。
- 驾驶舱消费用 sqlite URI `mode=ro` 只读打开。

## 4. 数据维护 CLI

```bash
# 行情库刷新（只刷缺口）与状态
$WIN_PYTHON -m src.interfaces.cli.quant data refresh --start-date ... --end-date ...
$WIN_PYTHON -m src.interfaces.cli.quant data status
# 因子判决（结果入 factor_verdicts, feature_version 版本化）
$WIN_PYTHON -m src.interfaces.cli.quant factor-test --factors P0 --split-date 2024-06-30
```

特征列由 `feature_engine`（domain）计算、refresh 写入 `features` 表；新增因子
表达式前先确认字段在管道中真实存在（F10 毛利率字段缺失判决无效的教训，
factor-test 引擎字段存在性校验为登记债）。
