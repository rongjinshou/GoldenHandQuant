# Market Data Store 实施计划

> **For agentic workers:** 按任务顺序执行，每任务自带测试与验证命令。
> 设计依据：同目录 `2026-06-11-market-data-store-design.md`。
> 测试统一用 Windows conda Python 跑（WSL 无环境）：
> `WIN_PY=/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe`

**Goal:** 市场数据（股票池/日线/基本面/截面特征）入 DuckDB，只刷缺口；
向量化特征引擎替代逐日逐股纯 Python 重算并修复 `return_20d` bug。

**Architecture:** domain 放纯计算（FeatureEngine, pandas），infrastructure 放
存储（MarketDataStore, duckdb），application 放编排（MarketDataAppService），
CLI 只接线。`FactorTestRunner` 接口零改动。

**Tech Stack:** duckdb（新增依赖）、pandas、pytest。

---

### Task 1: Domain 红线规则更新

**Files:**
- Modify: `CLAUDE.md`（"Domain 红线"条目）
- Modify: `docs/rules/architecture.md:21`（核心红线第 1 条）

- [x] 两处规则改为：domain 允许纯计算库（numpy/pandas/scipy，无 I/O、无网络、
  无全局状态）；仍禁止数据源 SDK、存储引擎、框架、可视化、ML 训练库
- [x] `architecture.md:246` 等提及"纯 domain 无第三方依赖"的描述同步修正

### Task 2: duckdb 依赖

**Files:**
- Modify: `pyproject.toml`（dependencies 加 `"duckdb>=1.0"`）

- [x] pyproject 增加依赖；Windows conda env 已 `pip install duckdb`（1.x）
- [x] 验证：`$WIN_PY -c "import duckdb; print(duckdb.__version__)"`

### Task 3: MarketDataStore（DuckDB 仓储）

**Files:**
- Create: `src/infrastructure/persistence/market_data_store.py`
- Test: `tests/infrastructure/persistence/test_market_data_store.py`

接口（全部日期参数为 `"YYYY-MM-DD"` 字符串）：

```python
class MarketDataStore:
    def __init__(self, db_path: str = "data/market.duckdb") -> None: ...  # ":memory:" 可测
    # instruments
    def upsert_instruments(self, instruments: list[dict], source: str) -> None
    def load_symbols(self, source: str) -> list[str]
    # bars
    def upsert_bars(self, bars: list[Bar], source: str) -> None
    def load_bars_df(self, symbols, start_date, end_date, source) -> pd.DataFrame
    # fundamentals
    def upsert_fundamentals(self, snaps: list[FundamentalSnapshot], source: str) -> None
    # features
    def upsert_features_df(self, df: pd.DataFrame, feature_version: int) -> None
    def load_feature_join_df(self, symbols, start_date, end_date,
                             feature_version, source) -> pd.DataFrame  # features ⋈ fundamentals
    def feature_symbols_at(self, feature_version: int) -> set[str]
    # fetch_meta
    def get_fulfilled(self, source, table_name, symbol) -> tuple[str, str] | None
    def missing_ranges(self, source, table_name, symbol, start, end) -> list[tuple[str, str]]
    def mark_fulfilled(self, source, table_name, symbol, start, end) -> None
```

缺口算法（设计 §5）：无记录 → `[(start, end)]`；有 `(fs, fe)` →
左缺 `(start, day_before(fs))` 当 `start < fs`，右缺 `(day_after(fe), end)` 当
`end > fe`；`mark_fulfilled` 取区间并集。upsert 全部用
`INSERT ... ON CONFLICT DO UPDATE`（幂等）。

- [x] 测试先行：建表幂等 / bars upsert 幂等（重复插入行数不变、字段更新）/
  缺口四象限（无记录、左缺、右缺、全覆盖）/ mark_fulfilled 并集 /
  特征版本隔离（v1 与 v2 互不可见）
- [x] 实现并通过：`$WIN_PY -m pytest tests/infrastructure/persistence/test_market_data_store.py -v`

### Task 4: FeatureEngine（向量化 + 修 return_20d）

**Files:**
- Create: `src/domain/market/services/feature_engine.py`
- Test: `tests/domain/market/services/test_feature_engine.py`（golden 对照）

```python
FEATURE_VERSION = 1  # 口径: return_20d 修复后首版

def compute_symbol_features(bars_df: pd.DataFrame) -> pd.DataFrame:
    """单 symbol 全时段特征。bars_df: date 升序, 列 open/high/low/close/volume/prev_close。
    返回行 = 快照日 T（自第 2 根起）; 特征列全部 shift(1) 后 rolling（T-1 信息）;
    exec_close = T 日 close。窗口不足 → NaN（与手写版'缺特征'同语义）。"""
```

核心写法：`info = df.shift(1)` 之后全部窗口在 `info` 上算——
`return_5d = info.close.pct_change(5)`；`return_20d = info.close.pct_change(20)`
（**修复点**）；`volatility_20d = info.close.pct_change().rolling(20).std(ddof=1)`；
skew 手算（总体偏度 ÷n、样本 std，不用 pandas .skew()）；RSI 用近 14 日收益
正/负部 rolling 和 ÷14；MACD 用标准 `ewm(span=12/26, adjust=False)` 全历史递推
（与手写版差异已在设计 §6 声明）；OBV 累计后 rolling 20 点线性回归斜率
（`cov(x,y)/var(x)` 闭式）。

- [x] golden 测试先行：随机游走 OHLCV 150 根 × 3 symbol；参考实现 = 复刻
  `prepare_snapshots` 循环（`get_recent_bars(120)` 截断 + `info_bars=recent[:-1]`
  + 手写 `CrossSectionBuilder._compute_bar_metrics`）；逐日逐特征对比：
  固定窗口特征 `abs diff < 1e-9`；macd/macd_signal 相对容差 1e-3；
  return_20d 单独断言 = `closes[-21]` 口径且 ≠ 手写 bug 口径
- [x] 实现并通过：`$WIN_PY -m pytest tests/domain/market/services/test_feature_engine.py -v`

### Task 5: MarketDataAppService（编排 + 管道接入）

**Files:**
- Create: `src/application/market_data_app.py`
- Modify: `src/application/factor_test_app.py`（可选注入，走库路径）
- Test: `tests/application/test_market_data_app.py`

```python
class MarketDataAppService:
    def __init__(self, store, history_fetcher, fundamental_fetcher,
                 instrument_fetcher=None, source: str = "qmt") -> None: ...
    def ensure_bars(self, symbols, start, end) -> None        # 缺口驱动, 逐 symbol
    def ensure_fundamentals(self, start, end) -> None         # 整批, symbol='*'
    def ensure_features(self, symbols, start, end) -> None    # bars 覆盖变化 → 整只重算
    def load_cross_sections(self, symbols, start, end)        # 设计 §7, 返回三个 dict
        -> tuple[dict, dict, dict]
```

`load_cross_sections` 内部：`store.load_feature_join_df`（warmup 由 ensure 阶段
完成，查询窗口即 [start, end]）→ groupby date → 构造 `StockSnapshot`（特征列直接
喂构造器 kwargs）→ `prices_by_date` 取 `exec_close` → `_compute_forward_returns`。
`ensure_bars` 对照 meta 拉缺口时仍带 warmup 提前量（`_WARMUP_DAYS=200` 移到
共享常量）。`FactorTestAppService.__init__` 增加 `market_data: MarketDataAppService
| None = None`；`prepare_snapshots` 开头 `if self._market_data: return
self._market_data.prepare(symbols, start, end)`（ensure 三连 + load）。

- [x] 测试先行（temp duckdb + 现有 stub fetcher）：
  - 三个约定在 DB 路径重验：T-1 信息（snapshot.close == T-1 close、执行价 == T close）、
    无前视（篡改未来不影响过去）、warmup（窗口首日 return_5d/volatility_20d 可算）、
    输出键严格落 [start, end]
  - 只刷缺口：第二次 ensure_bars 同窗口 → fetcher 零调用；右移 end → 只拉尾部
  - 特征复用：bars 未变 → ensure_features 不重算（meta 命中）
- [x] 实现并通过：`$WIN_PY -m pytest tests/application/test_market_data_app.py -v`

### Task 6: CLI 接线

**Files:**
- Create: `src/interfaces/cli/commands/data_cmd.py`（`quant data refresh|status`）
- Modify: `src/interfaces/cli/quant.py`（注册子命令）
- Modify: `src/interfaces/cli/commands/factor_test.py`（组装 store + MarketDataAppService，
  替换直连 fetcher 路径；离线且库覆盖 → 可跑；离线有缺口 → 明确报错退出）

- [x] `quant data status`：按表输出 symbol 数 / 日期范围 / 行数 / 特征版本
- [x] `quant data refresh --start --end`：ensure 三连，打印各表新增行数
- [x] factor-test 走库路径；`--no-store` 回退旧内存路径（兼容逃生门）

### Task 7: 全量验证

- [x] `$WIN_PY -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q` 全绿
- [x] `$WIN_PY -m ruff check src/ tests/` 干净（存量 fetch_account.py E501 除外，不在本次范围）
- [x] 现有特征化测试（内存路径）不回归

### Task 8: 重跑 P0 判决（修复口径）

- [x] `quant data refresh` 全市场入库（QMT 在线，首次全量）
- [x] `factor-test --factors P0 ...` 走库路径重跑，产出
  `docs/feat/0610-factor-library/2026-06-11-p0-verdict-v2.json` + 报告对比第一轮

## Self-Review 结论

- 设计 §2-§8 每节均有对应任务（§2→T1、§3/§4/§5→T3、§6→T4、§7→T5/T6、§8→T5/T7）
- 接口签名在 T3/T5 间一致（store 方法名、日期字符串约定）
- 无 TBD/占位符；T8 为设计 §9 性能验证的实跑闭环
