# F01 可投性回测 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans（本会话内联执行，全权委托模式）。步骤用 `- [ ]` 复选框跟踪。

**Goal:** 让 `MicroValueStrategy`（=F01 可投策略）能在 `market.duckdb` 上**全离线、全市场、无截断**地跑回测，产出 ¥146k 真实可执行收益，回答"size edge 过不过毕业闸"。

**Architecture:** 新增 `DuckDBFundamentalFetcher`（QMT 基本面的离线对偶，SQL 层 `market_cap>0`）；抽 `build_backtest_cross_section` helper 统一三回测入口并去掉随机 500 截断；刷新 `backtest.yaml` 到重判窗口；run-driver 显式注入 `EqualWeightSizer` 跑 top_n 敏感性并入库；report-harness 算等权覆盖池基准并对照重判 +16.5% 上界。

**Tech Stack:** Python 3.13, duckdb, pytest(AAA)。测试与实跑均走 `$WIN_PYTHON`（`/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe`）；WSL `/usr/bin/python3` 无项目依赖，勿用。

**关键事实（来自理解阶段）：**
- DuckDB 列与 `FundamentalSnapshot` VO **字段名 1:1**；`fundamental_snapshots` 每交易日每股一行（market_cap 按 close 日更，财务 as-of），span 2020-06-15→2026-06-11，5207 股。
- `MarketDataStore(db_path, read_only=True).load_symbols("qmt")` → 全 5207 宇宙（instruments.source 全为 'qmt'）。
- `MockTradeGateway` **内置**真实成本（`COMMISSION_RATE=0.00025`/`STAMP_DUTY_RATE=0.0005`/`TRANSFER_FEE_RATE=0.00001`/`SLIPPAGE_BUY=SLIPPAGE_SELL=0.001`/`MIN_COMMISSION=5`），不读 yaml。
- `BacktestAppService(sizer=None)` 默认 `FixedRatioSizer(0.2)` → 等权 basket **必须显式传 `EqualWeightSizer`**。
- 离线 DuckDB **无指数 bars** → 中证1000 趋势闸 inert（设计 DD-4，须留痕）。
- registry：`create_strategy("micro_value", {"top_n": N})`，`strategy_type="cross_section"`。

---

## 文件结构（改动面）

| 文件 | 责任 | 类型 |
|---|---|---|
| `src/infrastructure/gateway/duckdb_fundamental_fetcher.py` | DuckDB `fundamental_snapshots` → `FundamentalSnapshot`（`market_cap>0`） | 新建 |
| `tests/infrastructure/persistence/test_duckdb_fundamental_fetcher.py` | 上者测试（刻意不放被 ignore 的 gateway/） | 新建 |
| `src/interfaces/cli/_backtest_wiring.py` | `build_backtest_cross_section` 三入口共用装配 | 新建 |
| `tests/interfaces/cli/test_backtest_wiring.py` | 上者测试 | 新建 |
| `src/interfaces/cli/run_backtest.py` | 截面装配块 → 调 helper | 改 |
| `src/interfaces/cli/commands/backtest.py` | 同上（含删随机500） | 改 |
| `src/interfaces/cli/compare_strategies.py` | 同上（含删随机500） | 改 |
| `resources/backtest.yaml` | 重判窗口 + MicroValue + ¥146k + DuckDB 源 | 改 |
| `scripts/run_f01_investability.py` | 离线全市场 run-driver（top_n 敏感性 + 入库） | 新建 |
| `scripts/f01_investability_report.py` | 等权覆盖池基准 + 指标对照计算 | 新建 |
| `docs/feat/0613-f01-investability/2026-06-13-f01-investability-report.md` | 可投性报告（人工分析） | 新建 |

---

## Task 1: DuckDBFundamentalFetcher（离线基本面）

**Files:**
- Create: `src/infrastructure/gateway/duckdb_fundamental_fetcher.py`
- Test: `tests/infrastructure/persistence/test_duckdb_fundamental_fetcher.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/infrastructure/persistence/test_duckdb_fundamental_fetcher.py
"""DuckDBFundamentalFetcher 测试 — 放 persistence/ 而非镜像目录 gateway/:
gateway/ 因 QMT 文件导入失败被默认门 --ignore; 本 fetcher 纯 DuckDB 无 QMT, 须在门跑得到处。"""
import duckdb
import pytest

from src.infrastructure.gateway.duckdb_fundamental_fetcher import DuckDBFundamentalFetcher


def _make_db(path):
    con = duckdb.connect(str(path))
    con.execute("""CREATE TABLE fundamental_snapshots(
        symbol VARCHAR, date DATE, source VARCHAR, name VARCHAR, list_date DATE,
        market_cap DOUBLE, roe_ttm DOUBLE, ocf_ttm DOUBLE, pe_ratio DOUBLE,
        pb_ratio DOUBLE, earnings_growth DOUBLE, revenue_growth DOUBLE)""")
    con.executemany(
        "INSERT INTO fundamental_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("000001.SZ", "2024-01-02", "qmt", "平安", "1991-04-03", 3.0e11, 0.1, 1.0, 5.0, 0.8, 0.05, 0.04),
            ("000002.SZ", "2024-01-02", "qmt", "万科", "1991-01-29", 2.0e10, 0.08, 1.0, 6.0, 0.7, 0.02, 0.01),
            ("000003.SZ", "2024-01-02", "qmt", "空洞", "1991-01-29", 0.0, None, None, None, None, None, None),  # market_cap=0 须剔除
            ("000001.SZ", "2024-02-01", "qmt", "平安", "1991-04-03", 3.1e11, 0.1, 1.0, 5.0, 0.8, 0.05, 0.04),  # 区间外(若 end<此)
        ])
    con.close()


def test_fetch_filters_market_cap_zero_and_maps_columns(tmp_path):
    db = tmp_path / "m.duckdb"; _make_db(db)
    f = DuckDBFundamentalFetcher(str(db))
    try:
        snaps = f.fetch_by_range("2024-01-01", "2024-01-31")
    finally:
        f.close()
    syms = {s.symbol for s in snaps}
    assert syms == {"000001.SZ", "000002.SZ"}          # market_cap=0 的 000003 被剔除
    px = next(s for s in snaps if s.symbol == "000001.SZ")
    assert px.market_cap == 3.0e11 and px.name == "平安"
    assert px.pe_ratio == 5.0 and px.roe_ttm == 0.1
    assert px.date.year == 2024 and px.list_date.year == 1991  # date→datetime 转换


def test_fetch_respects_date_range_and_symbols(tmp_path):
    db = tmp_path / "m.duckdb"; _make_db(db)
    f = DuckDBFundamentalFetcher(str(db))
    try:
        only_feb = f.fetch_by_range("2024-01-15", "2024-12-31")     # 含 000001 的 2-01 行
        only_wanke = f.fetch_by_range("2024-01-01", "2024-01-31", symbols=["000002.SZ"])
    finally:
        f.close()
    assert {s.date.month for s in only_feb} == {2}
    assert {s.symbol for s in only_wanke} == {"000002.SZ"}


def test_missing_table_returns_empty(tmp_path):
    db = tmp_path / "empty.duckdb"; duckdb.connect(str(db)).close()
    f = DuckDBFundamentalFetcher(str(db))
    try:
        assert f.fetch_by_range("2024-01-01", "2024-12-31") == []
    finally:
        f.close()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$WIN_PY" -m pytest tests/infrastructure/persistence/test_duckdb_fundamental_fetcher.py -v`
Expected: FAIL（ModuleNotFoundError: duckdb_fundamental_fetcher）

- [ ] **Step 3: 实现 fetcher**

```python
# src/infrastructure/gateway/duckdb_fundamental_fetcher.py
"""DuckDB 基本面数据源 — 回测离线消费 market.duckdb 的 fundamental_snapshots。

QmtFundamentalFetcher 的离线对偶: 列与 FundamentalSnapshot VO 1:1 映射, 无需 QMT 在线。
market_cap<=0 的行(QMT TotalVolume 缺失造成的数据空洞, ~14%)在 SQL 层剔除——
无有效市值的快照无法参与 size 截面排序(设计 DD-7)。
设计: docs/feat/0613-f01-investability/2026-06-13-f01-investability-design.md
"""
from __future__ import annotations

import logging
from datetime import datetime

import duckdb

from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot

logger = logging.getLogger(__name__)

_COLUMNS = (
    "symbol", "date", "name", "list_date", "market_cap",
    "roe_ttm", "ocf_ttm", "pe_ratio", "pb_ratio",
    "earnings_growth", "revenue_growth",
)


class DuckDBFundamentalFetcher:
    """从 market.duckdb 的 fundamental_snapshots 读基本面快照(read_only)。

    实现 IFundamentalFetcher.fetch_by_range（鸭子类型, 含 QMT 风格 symbols 可选参）。
    与写进程(refresh/factor-test)互斥——回测期间勿跑刷数任务。
    """

    def __init__(self, db_path: str = "data/market.duckdb") -> None:
        self._conn = duckdb.connect(db_path, read_only=True)

    def close(self) -> None:
        self._conn.close()

    def fetch_by_range(
        self, start_date: str, end_date: str, symbols: list[str] | None = None
    ) -> list[FundamentalSnapshot]:
        cols = ", ".join(_COLUMNS)
        sql = (f"SELECT {cols} FROM fundamental_snapshots "
               "WHERE date BETWEEN ? AND ? AND market_cap > 0")
        params: list = [start_date, end_date]
        if symbols:
            sql += f" AND symbol IN ({', '.join('?' * len(symbols))})"
            params.extend(symbols)
        sql += " ORDER BY date, symbol"
        try:
            rows = self._conn.execute(sql, params).fetchall()
        except duckdb.Error as e:
            logger.warning("DuckDB 基本面读取失败(%s); 返回空。", e)
            return []
        return [self._to_snapshot(r) for r in rows]

    @staticmethod
    def _to_snapshot(row: tuple) -> FundamentalSnapshot:
        (symbol, date, name, list_date, market_cap, roe_ttm, ocf_ttm,
         pe_ratio, pb_ratio, earnings_growth, revenue_growth) = row
        return FundamentalSnapshot(
            symbol=symbol,
            date=datetime.combine(date, datetime.min.time()),
            name=name or symbol,
            list_date=(datetime.combine(list_date, datetime.min.time())
                       if list_date is not None else datetime(1990, 1, 1)),
            market_cap=market_cap,
            roe_ttm=roe_ttm, ocf_ttm=ocf_ttm, pe_ratio=pe_ratio, pb_ratio=pb_ratio,
            earnings_growth=earnings_growth, revenue_growth=revenue_growth,
        )
```

- [ ] **Step 4: 跑测试通过** — `"$WIN_PY" -m pytest tests/infrastructure/persistence/test_duckdb_fundamental_fetcher.py -v` → PASS

- [ ] **Step 5: Commit**
```bash
git add src/infrastructure/gateway/duckdb_fundamental_fetcher.py tests/infrastructure/persistence/test_duckdb_fundamental_fetcher.py
git commit -m "feat(gateway): DuckDBFundamentalFetcher — 离线基本面(market_cap>0 兜数据空洞)"
```

---

## Task 2: build_backtest_cross_section helper（统一装配，去截断）

**Files:**
- Create: `src/interfaces/cli/_backtest_wiring.py`
- Test: `tests/interfaces/cli/test_backtest_wiring.py`

- [ ] **Step 1: 写失败测试**（DuckDB 源 → 全市场宇宙无截断 + 用 DuckDB 基本面）

```python
# tests/interfaces/cli/test_backtest_wiring.py
import duckdb

from src.interfaces.cli._backtest_wiring import build_backtest_cross_section


def _seed(path, n_symbols=600):
    """造 >500 只 instruments + 当日基本面, 验证不被随机 500 截断。"""
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE instruments(symbol VARCHAR, source VARCHAR, name VARCHAR, "
                "list_date DATE, delist_date DATE, updated_at TIMESTAMP)")
    con.execute("""CREATE TABLE fundamental_snapshots(
        symbol VARCHAR, date DATE, source VARCHAR, name VARCHAR, list_date DATE,
        market_cap DOUBLE, roe_ttm DOUBLE, ocf_ttm DOUBLE, pe_ratio DOUBLE,
        pb_ratio DOUBLE, earnings_growth DOUBLE, revenue_growth DOUBLE)""")
    syms = [f"{i:06d}.SZ" for i in range(n_symbols)]
    con.executemany("INSERT INTO instruments VALUES (?,?,?,?,?,?)",
                    [(s, "qmt", s, None, None, None) for s in syms])
    con.executemany("INSERT INTO fundamental_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(s, "2024-01-02", "qmt", s, None, 1e9 + i, None, None, None, None, None, None)
                     for i, s in enumerate(syms)])
    con.close()


def test_duckdb_source_full_universe_no_500_cap(tmp_path):
    db = tmp_path / "m.duckdb"; _seed(db, n_symbols=600)
    registry, universe = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", "2024-01-01", "2024-01-31",
        config_symbols=["000852.SH"], db_path=str(db))
    assert len(universe) == 600                       # 未被随机 500 截断
    assert len(registry.get_all_at_date(__import__("datetime").datetime(2024, 1, 2))) == 600


def test_max_universe_explicit_cap(tmp_path):
    db = tmp_path / "m.duckdb"; _seed(db, n_symbols=600)
    _, universe = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", "2024-01-01", "2024-01-31",
        config_symbols=[], db_path=str(db), max_universe=100)
    assert len(universe) <= 100
```

- [ ] **Step 2: 跑测试确认失败** — `"$WIN_PY" -m pytest tests/interfaces/cli/test_backtest_wiring.py -v` → FAIL（无 `_backtest_wiring`）

- [ ] **Step 3: 实现 helper**

```python
# src/interfaces/cli/_backtest_wiring.py
"""回测截面策略的数据装配 — 三个回测入口(run_backtest/quant backtest/compare)共用。

统一前: 三入口各写一份, 其中两个把宇宙随机截到 500(对 micro-cap=静默错误结论)。
统一后: 一处修复, 三入口同口径, 去截断; DuckDB 源全离线全市场。
设计: docs/feat/0613-f01-investability/2026-06-13-f01-investability-design.md DD-2
"""
from __future__ import annotations

from src.domain.market.services.fundamental_registry import FundamentalRegistry

DEFAULT_DB_PATH = "data/market.duckdb"


def build_backtest_cross_section(
    history_fetcher_type: str,
    start_date: str,
    end_date: str,
    *,
    tushare_token: str | None = None,
    config_symbols: list[str] | None = None,
    db_path: str = DEFAULT_DB_PATH,
    max_universe: int | None = None,
) -> tuple[FundamentalRegistry, list[str]]:
    """返回 (fundamental_registry, stock_universe)。

    - DuckDBHistoryDataFetcher: 基本面 + 宇宙全部来自 market.duckdb(离线全市场, 无截断)。
    - TushareHistoryDataFetcher: Tushare 基本面, 其覆盖标的为宇宙。
    - 其它(QMT): QMT 基本面 + 沪深A股 sector 为宇宙(去随机500截断; max_universe 显式限速)。
    """
    registry = FundamentalRegistry()

    if history_fetcher_type == "DuckDBHistoryDataFetcher":
        from src.infrastructure.gateway.duckdb_fundamental_fetcher import DuckDBFundamentalFetcher
        from src.infrastructure.persistence.market_data_store import MarketDataStore

        store = MarketDataStore(db_path, read_only=True)
        try:
            universe = store.load_symbols("qmt")
        finally:
            store.close()
        if max_universe is not None and len(universe) > max_universe:
            universe = sorted(universe)[:max_universe]

        fetcher = DuckDBFundamentalFetcher(db_path)
        try:
            snapshots = fetcher.fetch_by_range(start_date, end_date, symbols=universe)
        finally:
            fetcher.close()
        registry.load_snapshots(snapshots)
        universe = sorted({s.symbol for s in snapshots})
        print(f"Universe(DuckDB 离线): {len(universe)} 只, 基本面 {len(snapshots)} 条")
        return registry, universe

    if history_fetcher_type == "TushareHistoryDataFetcher":
        from src.infrastructure.gateway.tushare_fundamental_fetcher import TushareFundamentalFetcher
        snapshots = TushareFundamentalFetcher(token=tushare_token).fetch_by_range(start_date, end_date)
        registry.load_snapshots(snapshots)
        return registry, sorted({s.symbol for s in snapshots})

    # QMT 在线
    from src.infrastructure.gateway.qmt_fundamental_fetcher import QmtFundamentalFetcher
    universe: list[str] = []
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata as _xt
        for sector in ["沪深A股"]:
            universe.extend(_xt.get_stock_list_in_sector(sector))
    except Exception as e:
        print(f"Warning: 无法加载全市场列表 ({e})")
    universe = sorted(set(universe))
    if max_universe is not None and len(universe) > max_universe:
        universe = universe[:max_universe]
    snapshots = QmtFundamentalFetcher().fetch_by_range(start_date, end_date, symbols=universe or None)
    registry.load_snapshots(snapshots)
    return registry, sorted({s.symbol for s in snapshots})
```

- [ ] **Step 4: 跑测试通过** — `"$WIN_PY" -m pytest tests/interfaces/cli/test_backtest_wiring.py -v` → PASS

- [ ] **Step 5: Commit**
```bash
git add src/interfaces/cli/_backtest_wiring.py tests/interfaces/cli/test_backtest_wiring.py
git commit -m "feat(cli): build_backtest_cross_section — 三回测入口共用装配, DuckDB 离线全市场, 去随机500截断"
```

---

## Task 3: 三入口接线 helper（重构，行为保持 + 修截断陷阱）

**Files:** Modify `src/interfaces/cli/run_backtest.py`、`src/interfaces/cli/commands/backtest.py`、`src/interfaces/cli/compare_strategies.py`

- [ ] **Step 1: run_backtest.py main()** — 用下块**替换** `fundamental_registry = None` 起、到 `print(f"Stocks with fundamental data: {len(stock_universe)}")` 止的整段：

```python
    fundamental_registry = None
    stock_universe: list[str] = []
    if config.strategy_type == "cross_section":
        from src.interfaces.cli._backtest_wiring import build_backtest_cross_section
        fundamental_registry, stock_universe = build_backtest_cross_section(
            history_fetcher_type, start_date, end_date,
            tushare_token=tushare_token, config_symbols=symbols,
        )
```

- [ ] **Step 2: commands/backtest.py run_backtest()** — 同样**替换** `fundamental_registry = None` 起、到 `print(f"Stocks with fundamental data: {len(stock_universe)}")` 止的整段（即删除含 `max_stocks = 500` / `random.sample` 的 QMT 块）为：

```python
    fundamental_registry = None
    stock_universe: list[str] = []
    if config.strategy_type == "cross_section":
        from src.interfaces.cli._backtest_wiring import build_backtest_cross_section
        fundamental_registry, stock_universe = build_backtest_cross_section(
            history_fetcher_type, start_date, end_date,
            tushare_token=tushare_token, config_symbols=symbols,
        )
```

- [ ] **Step 3: compare_strategies.py main()** — **替换** `fundamental_registry = None` 起、到 `stock_universe = sorted({s.symbol for s in snapshots})`（紧接 `if need_fundamental:` 块）止的整段（删含 `max_stocks = 500` / `random.sample` 的块）为：

```python
    fundamental_registry = None
    stock_universe: list[str] = []
    if need_fundamental:
        from src.interfaces.cli._backtest_wiring import build_backtest_cross_section
        fundamental_registry, stock_universe = build_backtest_cross_section(
            history_fetcher_type, start_date, end_date,
            tushare_token=tushare_token, config_symbols=symbols,
        )
```

- [ ] **Step 4: 删除三文件因替换而不再使用的 import**（如 `import random` 若仅服务于截断块）。用 `ruff check src/interfaces/cli/` 找未用 import。

- [ ] **Step 5: 冒烟 + 回归** — 模块可导入、现有回测测试绿：

Run: `"$WIN_PY" -c "import src.interfaces.cli.run_backtest, src.interfaces.cli.commands.backtest, src.interfaces.cli.compare_strategies; print('import ok')"`
Run: `"$WIN_PY" -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q`
Expected: import ok；测试全绿（无回归）

- [ ] **Step 6: Commit**
```bash
git add src/interfaces/cli/run_backtest.py src/interfaces/cli/commands/backtest.py src/interfaces/cli/compare_strategies.py
git commit -m "refactor(cli): 三回测入口统一走 build_backtest_cross_section; 删随机500截断陷阱(micro-cap静默错误)"
```

---

## Task 4: 刷新 resources/backtest.yaml 到重判口径

**Files:** Modify `resources/backtest.yaml`

- [ ] **Step 1: 整文件替换为**：

```yaml
backtest:
  # 全市场截面回测的宇宙来自 market.duckdb(DuckDB 源, 见 build_backtest_cross_section)。
  # 下列 symbols 仅供风控/对照指数; 个股宇宙不在此列。
  symbols:
    - "000852.SH"   # 中证1000: 系统风控闸 index + 次级对照(离线无指数bars时 inert, 设计 DD-3/DD-4)
  start_date: "2021-01-01"
  end_date: "2026-06-11"
  base_timeframe: "1d"
  initial_capital: 146000.0     # 对齐真实账户, 检验 ¥146k 可投性
  plot: false
  benchmark: "000852.SH"

strategy:
  name: "MicroValueStrategy"
  top_n: 20                     # 可投档(¥146k/20≈¥7.3k/仓); 敏感性 {10,30} 见 run-driver

position_sizing:
  type: "EqualWeightSizer"

risk:
  system_gate:
    index_symbol: "000852.SH"
    ma_period: 20
  stop_loss:
    max_loss_ratio: 0.03
  policies:
    - "limit_up_break"
    - "hard_stop_loss"

# 成本由 MockTradeGateway 内置(佣金万2.5/印花0.5‰/过户/滑点±0.1%/流动性10%), 此处仅留档。
costs:
  commission_rate: 0.00025
  tax_rate: 0.0005
  min_commission: 5.0
  slippage: 0.001

data:
  history_fetcher: "DuckDBHistoryDataFetcher"
  cache_dir: "data/"
  tushare:
    token: "${TUSHARE_TOKEN}"
```

- [ ] **Step 2: 校验配置可加载**

Run: `"$WIN_PY" -c "from src.infrastructure.config.settings import load_backtest_config as L; s=L('resources/backtest.yaml'); print(s.strategy.name, s.strategy.top_n, s.backtest.initial_capital, s.data.history_fetcher)"`
Expected: `MicroValueStrategy 20 146000.0 DuckDBHistoryDataFetcher`

- [ ] **Step 3: Commit**
```bash
git add resources/backtest.yaml
git commit -m "config(backtest): backtest.yaml 切重判口径 — 2021-01..2026-06 / MicroValue top_n=20 / ¥146k / DuckDB 离线"
```

---

## Task 5: 全量回归 + ruff 门

- [ ] **Step 1: ruff**

Run: `ruff check src/`（若 WSL 无 ruff，走 `"$WIN_PY" -m ruff check src/`）
Expected: 干净（或仅预先存在、与本次无关项——逐条确认无新增）

- [ ] **Step 2: 全量测试**

Run: `"$WIN_PY" -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q`
Expected: 全绿（含 Task1/2 新测试 + 现有回归）

- [ ] **Step 3: 若有红 → 修到绿再继续**（不得带红进实跑）。

---

## Task 6: F01 可投性回测 run-driver（离线全市场 + top_n 敏感性 + 入库）

**Files:** Create `scripts/run_f01_investability.py`

- [ ] **Step 1: 写 run-driver**

```python
# scripts/run_f01_investability.py
"""F01 可投性回测驱动 — 全市场离线 MicroValueStrategy, top_n 敏感性, 入库 backtest_runs。

用法(Windows python, 离线): "$WIN_PY" -m scripts.run_f01_investability [--quick]
  --quick: 仅 OOS 窗口(2024-06-30..end) + top_n=20, 用于先测单跑耗时再决定全量。
读 market.duckdb(只读 bars/基本面); 每个 top_n 结果入 backtest_runs(驾驶舱可查)。
设计/计划: docs/feat/0613-f01-investability/
"""
from __future__ import annotations

import sys
from datetime import datetime

from src.application.backtest_app import BacktestAppService
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.strategy.registry import create_strategy
from src.infrastructure.config.settings import load_backtest_config
from src.infrastructure.gateway.duckdb_history_data import DuckDBHistoryDataFetcher
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway
from src.interfaces.cli._backtest_wiring import build_backtest_cross_section
from src.interfaces.cli.run_backtest import store_backtest_reports

CONFIG = "resources/backtest.yaml"


def main() -> None:
    quick = "--quick" in sys.argv
    s = load_backtest_config(CONFIG)
    start = "2024-06-30" if quick else s.backtest.start_date
    end = s.backtest.end_date
    cap = s.backtest.initial_capital
    idx = s.risk.system_gate.index_symbol if s.risk else None
    top_ns = [20] if quick else [20, 10, 30]   # headline=20 先跑先存
    tf = Timeframe.DAY_1

    registry, universe = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", start, end, config_symbols=s.backtest.symbols)
    print(f"宇宙 {len(universe)} 只 | 区间 {start}..{end} | 资金 ¥{cap:,.0f} | top_n {top_ns}")

    # 一次性把 bars 装入共享行情网关(避免 3 次重载 6M 行)
    data_symbols = sorted(set(universe + ([idx] if idx else [])))
    mkt = MockMarketGateway()
    fetcher = DuckDBHistoryDataFetcher(fallback=None)   # 离线; 指数缺 bars → 趋势闸 inert
    try:
        for i, sym in enumerate(data_symbols):
            mkt.load_bars(fetcher.fetch_history_bars(sym, tf, start, end))
            if (i + 1) % 1000 == 0:
                print(f"  bars 装载 {i + 1}/{len(data_symbols)}")
    finally:
        fetcher.close()
    if idx and not mkt.get_recent_bars(idx, tf, 5):
        print(f"⚠ 指数 {idx} 无 bars(离线) → 中证1000 趋势闸 inert(设计 DD-4)。")

    for top_n in top_ns:
        print(f"\n=== MicroValue top_n={top_n} ===")
        trade = MockTradeGateway(market_gateway=mkt, initial_capital=cap)
        app = BacktestAppService(
            market_gateway=mkt, trade_gateway=trade,
            strategy=create_strategy("micro_value", {"top_n": top_n}),
            evaluator=PerformanceEvaluator(),
            sizer=EqualWeightSizer(n_symbols=top_n),       # 显式等权, 否则默认 FixedRatio
            fundamental_registry=registry, risk_settings=s.risk)
        reports = app.run_backtest(
            universe, start_date=datetime.strptime(start, "%Y-%m-%d"),
            end_date=datetime.strptime(end, "%Y-%m-%d"), base_timeframe=tf)
        r = reports[0]
        print(f"  总收益 {r.total_return:.2%} | 年化 {r.annualized_return:.2%} | "
              f"回撤 {r.max_drawdown:.2%} | 胜率 {r.win_rate:.2%} | 成交 {r.trade_count}")
        store_backtest_reports(reports, params={
            "source": "f01_investability", "strategy": "micro_value", "top_n": top_n,
            "universe": len(universe), "window": f"{start}..{end}", "quick": quick})


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 计时冒烟（先测单跑耗时）**

Run: `time "$WIN_PY" -m scripts.run_f01_investability --quick`
Expected: 完成一个 OOS 窗口 top_n=20 跑；记录耗时。
- 若 `--quick`（约 1 年 OOS）耗时 > ~30 分钟 → 全量(5.5 年×3)不可行：**改为只跑全窗口 top_n=20 一档**（编辑 `top_ns=[20]`），敏感性留作后续；在报告显式记录"因算力裁剪敏感性"。
- 成交数应 > 0 且宇宙 > 4000；若成交 0 → 排查（基本面装载/过滤链/资金一手）。

- [ ] **Step 3: 全量跑**（依 Step 2 决定 top_ns 广度）

Run: `"$WIN_PY" -m scripts.run_f01_investability`
Expected: 各 top_n 打印指标 + `结果已入库: backtest_runs ...`。

- [ ] **Step 4: 核对入库**

Run: `"$WIN_PY" -c "from src.infrastructure.persistence.market_data_store import MarketDataStore as M; s=M('data/market.duckdb', read_only=True); rs=s.load_backtest_runs(); print([ (r.get('run_id'), len(r['strategies'])) for r in rs[:3]]); s.close()"`
Expected: 见到 f01_investability 的 run(s)。

- [ ] **Step 5: Commit**
```bash
git add scripts/run_f01_investability.py
git commit -m "feat(scripts): F01 可投性回测驱动 — 离线全市场 MicroValue + top_n 敏感性 + 入库"
```

---

## Task 7: 报告 harness + 写报告

**Files:** Create `scripts/f01_investability_report.py`、`docs/feat/0613-f01-investability/2026-06-13-f01-investability-report.md`

- [ ] **Step 1: 写基准/指标 harness**

```python
# scripts/f01_investability_report.py
"""算等权覆盖池基准 + 取 backtest_runs 指标, 供人工写可投性报告。

等权覆盖池基准 = 每交易日全市场(prev_close>0)个股日收益均值复利(对齐重判'等权覆盖池'口径)。
用法: "$WIN_PY" -m scripts.f01_investability_report
"""
from __future__ import annotations

import duckdb

DB = "data/market.duckdb"
SPLIT = "2024-06-30"
START, END = "2021-01-01", "2026-06-11"


def _ew_benchmark(con, start, end):
    rows = con.execute(
        """WITH r AS (SELECT date, close/prev_close - 1 AS ret
                      FROM bars WHERE date BETWEEN ? AND ? AND prev_close > 0)
           SELECT date, avg(ret) FROM r GROUP BY date ORDER BY date""",
        [start, end]).fetchall()
    cum = 1.0
    cum_at = {}
    for d, ret in rows:
        cum *= 1 + (ret or 0)
        cum_at[d] = cum
    return rows, cum_at


def main() -> None:
    con = duckdb.connect(DB, read_only=True)
    rows, cum_at = _ew_benchmark(con, START, END)
    full = cum_at[max(cum_at)] - 1 if cum_at else 0.0
    # OOS 切片
    oos_rows = [(d, r) for d, r in rows if str(d) > SPLIT]
    cum = 1.0
    for _, r in oos_rows:
        cum *= 1 + (r or 0)
    oos = cum - 1
    print(f"等权覆盖池基准: 全程({START}..{END}) {full:.2%} | OOS({SPLIT}..{END}) {oos:.2%}")
    print(f"交易日: 全 {len(rows)} / OOS {len(oos_rows)}")
    # backtest_runs 指标
    from src.infrastructure.persistence.market_data_store import MarketDataStore
    st = MarketDataStore(DB, read_only=True)
    try:
        for run in st.load_backtest_runs():
            for s in run["strategies"]:
                import json
                p = json.loads(s["params"]) if s.get("params") else {}
                if p.get("source") != "f01_investability":
                    continue
                print(f"top_n={p.get('top_n')}: 总收益={s.get('total_return')}, "
                      f"年化={s.get('annualized_return')}, 回撤={s.get('max_drawdown')}, "
                      f"胜率={s.get('win_rate')}, 成交={s.get('trade_count')}")
    finally:
        st.close()
    con.close()


if __name__ == "__main__":
    main()
```

> 注：`load_backtest_runs` 返回的 strategy dict 字段名（`total_return`/`annualized_return`/…）以实跑打印为准，若不符按实际键调整（Step 2 会暴露）。

- [ ] **Step 2: 跑 harness 取数** — `"$WIN_PY" -m scripts.f01_investability_report`，记录基准 + 各 top_n 指标。

- [ ] **Step 3: 写报告** `2026-06-13-f01-investability-report.md`，含：
  - 运行口径（窗口/宇宙数/资金/成本/top_n/趋势闸是否 inert）。
  - 指标表：各 top_n 的 总收益/年化/回撤/Sharpe(若有)/胜率/换手/成交。
  - **三条对照**：① vs 等权覆盖池基准（全程 & OOS 超额）；② vs 重判 OOS Top 超额 +16.52%（写清 DD-5 非 like-for-like：本回测含叠层+真实对称成本+流动性，重判是裸因子无成本上界）；③ 集中度（top_n 10/20/30）对收益/回撤的影响（呼应重判 q5/q10 集中增强）。
  - **毕业闸结论**：size edge 在 ¥146k 真实约束下还剩多少 → 过 / 不过 / 有条件过（含已知偏置：生存者偏差/趋势闸 inert/小微盘真实冲击）。
  - 主线下一岔口：过→实盘硬化(D1/D4/D8)+小资金；不过→§六.2 稳健化或记分牌精化 L3/L4。

- [ ] **Step 4: Commit**
```bash
git add scripts/f01_investability_report.py docs/feat/0613-f01-investability/2026-06-13-f01-investability-report.md
git commit -m "feat(scripts)+docs(f01-investability): 基准/指标 harness + 可投性报告(对照重判+16.5%上界)"
```

---

## Task 8: 更新记忆/CLAUDE.md + 晨间补审清单

- [ ] **Step 1: 更新 `factor-funnel-status` 记忆**——把"下一步①F01 可投性回测"改为已完成 + 结论（过/不过）+ 新的下一岔口；记新事实（DuckDBFundamentalFetcher 离线回测命令、market_cap=0 数据债 B4）。
- [ ] **Step 2: 更新 CLAUDE.md 常用命令**——加 `"$WIN_PY" -m scripts.run_f01_investability`（离线全市场可投性回测）。若发现 EqualWeightSizer 未在 CLI 入口接线（默认 FixedRatio）属另一隐患，登记为观察项（不在本 Spec 修）。
- [ ] **Step 3: 晨间补审清单**（写入报告尾或单独 note）：本次决策留痕（DD-3/4/7）、待人工核对项（趋势闸 inert 影响、生存者偏差量级、是否需补指数 bars/退市股）、`git push`（WSL 不能 push → Windows 侧推）。
- [ ] **Step 4: Commit**
```bash
git add CLAUDE.md
git commit -m "docs(claude-md): 加 F01 可投性回测离线命令; 登记 market_cap=0 数据债"
```

---

## Self-Review（计划 vs 设计）

- **Spec 覆盖**：R1 离线全市场→Task1/2；R2 统一入口去截断→Task2/3；R3 重判口径→Task4；R4 实跑入库+报告→Task6/7；R5 留痕→各 Task commit + Task8。DD-1→Task1；DD-2→Task2/3；DD-3 基准→Task7；DD-4 趋势闸 inert→Task6 Step2 检测+报告；DD-5 非like-for-like→Task7 Step3；DD-6 `$WIN_PYTHON`→全程；DD-7 market_cap>0→Task1。全覆盖。
- **占位符**：两个新单元（fetcher/helper）给完整实现 + 测试；rewiring 给精确替换块；yaml 给整文件；run/report 给完整脚本。无 TODO/TBD。
- **类型一致**：`build_backtest_cross_section(...) -> (FundamentalRegistry, list[str])` 在 helper 定义、三入口与 run-driver 调用一致；`DuckDBFundamentalFetcher.fetch_by_range(start,end,symbols=None)` 全程一致；`create_strategy("micro_value", {"top_n": n})` 与 registry 一致；`EqualWeightSizer(n_symbols=...)` 与构造签名一致。
- **风险**：Task6 全量耗时未知 → 已内建 `--quick` 计时冒烟 + 裁剪回退（headline top_n=20 优先），不静默裁剪（报告记录）。
