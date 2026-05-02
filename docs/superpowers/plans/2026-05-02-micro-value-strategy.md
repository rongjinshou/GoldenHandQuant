# 微盘价值质量增强策略 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 QuantFlow DDD 架构，实现"基本面过滤 + 极小市值轮动增强"回测策略的完整数据→策略→风控→执行链路。

**Architecture:** 在现有 DDD 四层架构上做增量扩展：新增 CrossSectionalStrategy 截面策略基类、FundamentalSnapshot/Registry 数据模型、三层风控（Gate + Chain + SignalGenerator）、批量 Sizer 接口、双模式回测循环。Domain 层保持纯 Python 标准库依赖。

**Tech Stack:** Python 3.13+, pytest, ruff, dataclasses, Tushare (infrastructure only)

**Spec:** `docs/feat/0502-micro-value-strategy/design.md`

---

## Sprint 1: 数据层 — 值对象、注册表与特征管道

### Task 1: FundamentalSnapshot 值对象

**Files:**
- Create: `src/domain/market/value_objects/fundamental_snapshot.py`
- Create: `tests/domain/market/test_fundamental_snapshot.py`
- Create: `src/domain/market/services/__init__.py`

- [ ] **Step 1: 编写测试**

```python
# tests/domain/market/test_fundamental_snapshot.py
from datetime import datetime
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot

def test_fundamental_snapshot_creation():
    snap = FundamentalSnapshot(
        symbol="000001.SZ",
        date=datetime(2024, 6, 15),
        name="平安银行",
        list_date=datetime(1991, 4, 3),
        market_cap=2.5e11,
        roe_ttm=0.12,
        ocf_ttm=1.5e10,
    )
    assert snap.symbol == "000001.SZ"
    assert snap.name == "平安银行"
    assert snap.market_cap == 2.5e11
    assert snap.roe_ttm == 0.12
    assert snap.ocf_ttm == 1.5e10

def test_fundamental_snapshot_nullable_fields():
    snap = FundamentalSnapshot(
        symbol="000002.SZ",
        date=datetime(2024, 6, 15),
        name="万科A",
        list_date=datetime(1991, 1, 29),
        market_cap=1.0e11,
        roe_ttm=None,
        ocf_ttm=None,
    )
    assert snap.roe_ttm is None
    assert snap.ocf_ttm is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run python -m pytest tests/domain/market/test_fundamental_snapshot.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: 实现 FundamentalSnapshot**

```python
# src/domain/market/value_objects/fundamental_snapshot.py
from dataclasses import dataclass
from datetime import datetime

@dataclass(slots=True, kw_only=True)
class FundamentalSnapshot:
    """单只股票在某交易日的基本面快照。

    Attributes:
        symbol: 标的代码 (如 "000001.SZ")。
        date: 交易日（ann_date，公告日期，非报告期）。
        name: 股票名称。
        list_date: 上市日期。
        market_cap: 总市值。
        roe_ttm: ROE (TTM)，可能缺失。
        ocf_ttm: 经营现金流净额 (TTM)，可能缺失。
    """
    symbol: str
    date: datetime
    name: str
    list_date: datetime
    market_cap: float
    roe_ttm: float | None = None
    ocf_ttm: float | None = None
```

```python
# src/domain/market/services/__init__.py
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run python -m pytest tests/domain/market/test_fundamental_snapshot.py -v
```
Expected: 2 PASS

- [ ] **Step 5: 提交**

```bash
git add src/domain/market/value_objects/fundamental_snapshot.py tests/domain/market/test_fundamental_snapshot.py src/domain/market/services/__init__.py
git commit -m "feat: add FundamentalSnapshot value object"
```

---

### Task 2: StockSnapshot 值对象

**Files:**
- Create: `src/domain/market/value_objects/stock_snapshot.py`
- Create: `tests/domain/market/test_stock_snapshot.py`

- [ ] **Step 1: 编写测试**

```python
# tests/domain/market/test_stock_snapshot.py
from datetime import datetime
from src.domain.market.value_objects.stock_snapshot import StockSnapshot

def test_stock_snapshot_creation():
    snap = StockSnapshot(
        symbol="000001.SZ",
        date=datetime(2024, 6, 15),
        open=10.0, high=10.5, low=9.8, close=10.2, volume=1e6,
        name="平安银行",
        list_date=datetime(1991, 4, 3),
        market_cap=2.5e11,
        roe_ttm=0.12,
        ocf_ttm=1.5e10,
    )
    assert snap.open == 10.0
    assert snap.close == 10.2
    assert snap.volume == 1e6
    assert snap.name == "平安银行"
    assert snap.roe_ttm == 0.12

def test_stock_snapshot_nullable_financials():
    snap = StockSnapshot(
        symbol="000002.SZ",
        date=datetime(2024, 6, 15),
        open=8.0, high=8.3, low=7.9, close=8.1, volume=5e5,
        name="万科A",
        list_date=datetime(1991, 1, 29),
        market_cap=1.0e11,
    )
    assert snap.roe_ttm is None
    assert snap.ocf_ttm is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run python -m pytest tests/domain/market/test_stock_snapshot.py -v
```

- [ ] **Step 3: 实现 StockSnapshot**

```python
# src/domain/market/value_objects/stock_snapshot.py
from dataclasses import dataclass
from datetime import datetime

@dataclass(slots=True, kw_only=True)
class StockSnapshot:
    """Bar + FundamentalSnapshot 合并视图，过滤器的标准输入。"""
    symbol: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    name: str
    list_date: datetime
    market_cap: float
    roe_ttm: float | None = None
    ocf_ttm: float | None = None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run python -m pytest tests/domain/market/test_stock_snapshot.py -v
```
Expected: 2 PASS

- [ ] **Step 5: 提交**

```bash
git add src/domain/market/value_objects/stock_snapshot.py tests/domain/market/test_stock_snapshot.py
git commit -m "feat: add StockSnapshot value object"
```

---

### Task 3: IFundamentalFetcher Protocol 接口

**Files:**
- Create: `src/domain/market/interfaces/gateways/fundamental_fetcher.py`

- [ ] **Step 1: 实现接口（纯 Protocol，无需独立测试）**

```python
# src/domain/market/interfaces/gateways/fundamental_fetcher.py
from typing import Protocol
from datetime import datetime
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot

class IFundamentalFetcher(Protocol):
    """基本面数据获取接口（Domain 层定义，Infrastructure 层实现）。"""

    def fetch_by_range(
        self, start_date: str, end_date: str
    ) -> list[FundamentalSnapshot]:
        """批量预加载指定区间的基本面数据。

        以 ann_date（公告日期）为时间轴，杜绝未来函数。
        """
        ...

    def fetch_index_daily(
        self, index_symbol: str, start_date: str, end_date: str
    ) -> list[dict]:
        """获取指数日线数据（用于风控门禁和基准比较）。

        Returns:
            list[dict]: 每项含 trade_date, open, high, low, close, volume 等字段。
        """
        ...
```

- [ ] **Step 2: 提交**

```bash
git add src/domain/market/interfaces/gateways/fundamental_fetcher.py
git commit -m "feat: add IFundamentalFetcher Protocol interface"
```

---

### Task 4: FundamentalRegistry 服务

**Files:**
- Create: `src/domain/market/services/fundamental_registry.py`
- Create: `tests/domain/market/test_fundamental_registry.py`

- [ ] **Step 1: 编写测试**

```python
# tests/domain/market/test_fundamental_registry.py
from datetime import datetime
from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot

def _snap(symbol, date_str, name="Test", mcap=1e10):
    return FundamentalSnapshot(
        symbol=symbol,
        date=datetime.strptime(date_str, "%Y-%m-%d"),
        name=name,
        list_date=datetime(2000, 1, 1),
        market_cap=mcap,
    )

class TestFundamentalRegistry:
    def test_add_and_get_by_symbol(self):
        registry = FundamentalRegistry()
        s1 = _snap("000001.SZ", "2024-06-15", "Stock A")
        s2 = _snap("000001.SZ", "2024-06-16", "Stock A")
        registry.add(s1)
        registry.add(s2)

        assert registry.get("000001.SZ", datetime(2024, 6, 15)) is s1
        assert registry.get("000001.SZ", datetime(2024, 6, 16)) is s2
        assert registry.get("000001.SZ", datetime(2024, 6, 17)) is None

    def test_get_all_at_date_returns_all_symbols(self):
        registry = FundamentalRegistry()
        registry.add(_snap("000001.SZ", "2024-06-15", "A"))
        registry.add(_snap("000002.SZ", "2024-06-15", "B"))
        registry.add(_snap("000003.SZ", "2024-06-16", "C"))

        results = registry.get_all_at_date(datetime(2024, 6, 15))
        assert len(results) == 2
        symbols = {s.symbol for s in results}
        assert symbols == {"000001.SZ", "000002.SZ"}

    def test_get_all_at_date_empty_returns_empty_list(self):
        registry = FundamentalRegistry()
        results = registry.get_all_at_date(datetime(2024, 6, 15))
        assert results == []
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run python -m pytest tests/domain/market/test_fundamental_registry.py -v
```

- [ ] **Step 3: 实现 FundamentalRegistry**

```python
# src/domain/market/services/fundamental_registry.py
from datetime import datetime
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot

class FundamentalRegistry:
    """基本面数据内存注册表。

    双索引结构:
    - _by_symbol: dict[symbol, dict[date, FundamentalSnapshot]] — 按标的查询 O(1)
    - _by_date: dict[date, list[FundamentalSnapshot]] — 按日期批量获取 O(1)

    索引键使用 ann_date（公告日期），不使用 end_date（报告期），杜绝未来函数。
    """

    def __init__(self) -> None:
        self._by_symbol: dict[str, dict[datetime, FundamentalSnapshot]] = {}
        self._by_date: dict[datetime, list[FundamentalSnapshot]] = {}

    def add(self, snapshot: FundamentalSnapshot) -> None:
        date_key = snapshot.date.replace(hour=0, minute=0, second=0, microsecond=0)

        self._by_symbol.setdefault(snapshot.symbol, {})[date_key] = snapshot
        self._by_date.setdefault(date_key, []).append(snapshot)

    def get(self, symbol: str, date: datetime) -> FundamentalSnapshot | None:
        date_key = date.replace(hour=0, minute=0, second=0, microsecond=0)
        return self._by_symbol.get(symbol, {}).get(date_key)

    def get_all_at_date(self, date: datetime) -> list[FundamentalSnapshot]:
        date_key = date.replace(hour=0, minute=0, second=0, microsecond=0)
        return self._by_date.get(date_key, [])
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run python -m pytest tests/domain/market/test_fundamental_registry.py -v
```
Expected: 3 PASS

- [ ] **Step 5: 提交**

```bash
git add src/domain/market/services/fundamental_registry.py tests/domain/market/test_fundamental_registry.py
git commit -m "feat: add FundamentalRegistry with dual-index structure"
```

---

### Task 5: Bar 增加 prev_close 字段

**Files:**
- Modify: `src/domain/market/value_objects/bar.py`

- [ ] **Step 1: 修改 Bar**

```python
# src/domain/market/value_objects/bar.py (在现有字段后追加 prev_close)
@dataclass(slots=True, kw_only=True)
class Bar:
    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    unadjusted_close: float = 0.0
    prev_close: float = 0.0  # 前一日收盘价（用于涨停价计算）
```

- [ ] **Step 2: 运行现有测试确认兼容**

```bash
uv run python -m pytest tests/domain/strategy/test_dual_ma_strategy.py tests/domain/market/test_entities.py -v
```
Expected: all PASS (prev_close 有默认值，不影响现有 Bar 构造)

- [ ] **Step 3: 提交**

```bash
git add src/domain/market/value_objects/bar.py
git commit -m "feat: add prev_close field to Bar for price limit calculation"
```

---

### Task 6: FeaturePipeline.build_cross_section()

**Files:**
- Modify: `src/infrastructure/ml_engine/feature_pipeline.py`
- Create: `tests/infrastructure/ml_engine/test_feature_pipeline_cross_section.py`

- [ ] **Step 1: 编写测试**

```python
# tests/infrastructure/ml_engine/test_feature_pipeline_cross_section.py
from datetime import datetime, timedelta
from src.infrastructure.ml_engine.feature_pipeline import FeaturePipeline
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
from src.domain.market.services.fundamental_registry import FundamentalRegistry

def _bar(symbol, dt, close, volume=1000):
    return Bar(
        symbol=symbol, timeframe=Timeframe.DAY_1, timestamp=dt,
        open=close, high=close, low=close, close=close, volume=volume,
    )

class TestBuildCrossSection:
    def test_merges_bars_with_fundamentals(self):
        date = datetime(2024, 6, 15)
        registry = FundamentalRegistry()
        registry.add(FundamentalSnapshot(
            symbol="000001.SZ", date=date, name="Stock A",
            list_date=datetime(2000, 1, 1), market_cap=1e10,
            roe_ttm=0.15, ocf_ttm=5e8,
        ))
        registry.add(FundamentalSnapshot(
            symbol="000002.SZ", date=date, name="Stock B",
            list_date=datetime(2001, 1, 1), market_cap=5e9,
            roe_ttm=None, ocf_ttm=None,
        ))

        bars = {
            "000001.SZ": _bar("000001.SZ", date, 10.0),
            "000002.SZ": _bar("000002.SZ", date, 8.0),
        }

        result = FeaturePipeline.build_cross_section(date, bars, registry)
        assert len(result) == 2
        snap_a = next(s for s in result if s.symbol == "000001.SZ")
        snap_b = next(s for s in result if s.symbol == "000002.SZ")
        assert snap_a.name == "Stock A"
        assert snap_a.roe_ttm == 0.15
        assert snap_a.close == 10.0
        assert snap_b.name == "Stock B"
        assert snap_b.roe_ttm is None

    def test_skips_symbols_without_fundamental_data(self):
        date = datetime(2024, 6, 15)
        registry = FundamentalRegistry()
        bars = {"000001.SZ": _bar("000001.SZ", date, 10.0)}
        result = FeaturePipeline.build_cross_section(date, bars, registry)
        assert result == []

    def test_skips_symbols_without_bar_data(self):
        date = datetime(2024, 6, 15)
        registry = FundamentalRegistry()
        registry.add(FundamentalSnapshot(
            symbol="000001.SZ", date=date, name="A",
            list_date=datetime(2000, 1, 1), market_cap=1e10,
        ))
        bars: dict[str, Bar] = {}
        result = FeaturePipeline.build_cross_section(date, bars, registry)
        assert result == []
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run python -m pytest tests/infrastructure/ml_engine/test_feature_pipeline_cross_section.py -v
```

- [ ] **Step 3: 实现 build_cross_section**

```python
# 在 FeaturePipeline 类中追加静态方法
@staticmethod
def build_cross_section(
    date: datetime,
    bars: dict[str, Bar],
    registry: FundamentalRegistry,
) -> list:
    from src.domain.market.value_objects.stock_snapshot import StockSnapshot

    fundamentals = {s.symbol: s for s in registry.get_all_at_date(date)}
    snapshots: list[StockSnapshot] = []

    for symbol, bar in bars.items():
        fund = fundamentals.get(symbol)
        if fund is None:
            continue
        snapshots.append(StockSnapshot(
            symbol=symbol,
            date=date,
            open=bar.open, high=bar.high, low=bar.low,
            close=bar.close, volume=bar.volume,
            name=fund.name, list_date=fund.list_date,
            market_cap=fund.market_cap,
            roe_ttm=fund.roe_ttm, ocf_ttm=fund.ocf_ttm,
        ))

    return snapshots
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run python -m pytest tests/infrastructure/ml_engine/test_feature_pipeline_cross_section.py -v
```
Expected: 3 PASS

- [ ] **Step 5: 提交**

```bash
git add src/infrastructure/ml_engine/feature_pipeline.py tests/infrastructure/ml_engine/test_feature_pipeline_cross_section.py
git commit -m "feat: add FeaturePipeline.build_cross_section() for Bar+FundamentalSnapshot merging"
```

---

### Task 7: TushareHistoryDataFetcher 映射 pre_close

**Files:**
- Modify: `src/infrastructure/gateway/tushare_history_data.py`

- [ ] **Step 1: 修改数据获取器**

在 `TushareHistoryDataFetcher.fetch_history_bars` 中：

1. 扩展 CSV 保存/读取字段列表，增加 `pre_close`
2. 在 Bar 构造时传递 `prev_close`

```python
# 在 fetch_history_bars() 方法中修改两处:

# 处1: CSV 缓存保存字段 (约第128行)
save_df = df[["datetime", "symbol", "open", "high", "low", "close", "volume", "pre_close"]]
save_df.to_csv(csv_path, index=False)

# 处2: Bar 构造循环 (约第133行)
for _, row in df.iterrows():
    bars.append(Bar(
        symbol=str(row["symbol"]),
        timeframe=timeframe,
        timestamp=row["datetime"].to_pydatetime() if isinstance(row["datetime"], pd.Timestamp) else row["datetime"],
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
        prev_close=float(row.get("pre_close", 0.0)) if "pre_close" in row.index else 0.0,
    ))
```

- [ ] **Step 2: 运行现有 Tushare 测试确认兼容**

```bash
uv run python -m pytest tests/infrastructure/gateway/test_tushare_history_data.py -v --ignore=tests/infrastructure/gateway/
```
Expected: should still pass (test may be skipped if no token, which is fine)

- [ ] **Step 3: 提交**

```bash
git add src/infrastructure/gateway/tushare_history_data.py
git commit -m "feat: map Tushare pre_close to Bar.prev_close"
```

---

## Sprint 2: 策略层 — 过滤器与截面策略

### Task 8: filter_st — ST 股票过滤器

**Files:**
- Create: `src/domain/strategy/services/filters/__init__.py`
- Create: `src/domain/strategy/services/filters/filter_st.py`
- Create: `tests/domain/strategy/test_filters.py`

- [ ] **Step 1: 编写测试**

```python
# tests/domain/strategy/test_filters.py
from datetime import datetime
from src.domain.strategy.services.filters.filter_st import filter_st
from src.domain.strategy.services.filters.filter_new_listing import filter_new_listing
from src.domain.strategy.services.filters.filter_penny_stock import filter_penny_stock
from src.domain.strategy.services.filters.filter_trading_status import filter_trading_status
from src.domain.strategy.services.filters.filter_quality import filter_quality
from src.domain.market.value_objects.stock_snapshot import StockSnapshot

def _snap(symbol, **kwargs):
    defaults = dict(
        symbol=symbol, date=datetime(2024, 6, 15),
        open=10.0, high=10.5, low=9.8, close=10.2, volume=1e6,
        name="Normal Stock",
        list_date=datetime(2000, 1, 1),
        market_cap=1e10, roe_ttm=0.15, ocf_ttm=5e8,
    )
    defaults.update(kwargs)
    return StockSnapshot(**defaults)

class TestFilterST:
    def test_removes_st_stocks(self):
        snaps = [
            _snap("000001.SZ", name="ST 股票"),
            _snap("000002.SZ", name="*ST 退市"),
            _snap("000003.SZ", name="平安银行"),
        ]
        result = filter_st(snaps)
        assert len(result) == 1
        assert result[0].symbol == "000003.SZ"

    def test_keeps_st_in_middle_of_name(self):
        snaps = [_snap("000001.SZ", name="BEST Inc")]
        result = filter_st(snaps)
        assert len(result) == 1

    def test_empty_list(self):
        assert filter_st([]) == []
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run python -m pytest tests/domain/strategy/test_filters.py::TestFilterST -v
```

- [ ] **Step 3: 实现 filter_st**

```python
# src/domain/strategy/services/filters/filter_st.py
from src.domain.market.value_objects.stock_snapshot import StockSnapshot

def filter_st(snapshots: list[StockSnapshot]) -> list[StockSnapshot]:
    """剔除股票名称包含 'ST' 或 '*ST' 的标的。"""
    return [s for s in snapshots if "ST" not in s.name]
```

```python
# src/domain/strategy/services/filters/__init__.py
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run python -m pytest tests/domain/strategy/test_filters.py::TestFilterST -v
```
Expected: 3 PASS

- [ ] **Step 5: 提交**

```bash
git add src/domain/strategy/services/filters/
git commit -m "feat: add filter_st to exclude ST/*ST stocks"
```

---

### Task 9: filter_new_listing — 次新股过滤器

- [ ] **Step 1: 编写测试**

```python
# 追加到 tests/domain/strategy/test_filters.py

class TestFilterNewListing:
    def test_removes_stocks_listed_less_than_365_days(self):
        date = datetime(2024, 6, 15)
        snaps = [
            _snap("000001.SZ", list_date=datetime(2024, 1, 1)),   # < 365 days
            _snap("000002.SZ", list_date=datetime(2000, 1, 1)),   # old stock
        ]
        result = filter_new_listing(snaps, date)
        assert len(result) == 1
        assert result[0].symbol == "000002.SZ"

    def test_keeps_stock_exactly_365_days(self):
        date = datetime(2024, 6, 15)
        snaps = [_snap("000001.SZ", list_date=datetime(2023, 6, 16))]
        result = filter_new_listing(snaps, date)
        assert len(result) == 0  # exactly 365 days is still < 365 (strict)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run python -m pytest tests/domain/strategy/test_filters.py::TestFilterNewListing -v
```

- [ ] **Step 3: 实现**

```python
# src/domain/strategy/services/filters/filter_new_listing.py
from datetime import datetime
from src.domain.market.value_objects.stock_snapshot import StockSnapshot

def filter_new_listing(
    snapshots: list[StockSnapshot],
    current_date: datetime,
    min_days: int = 365,
) -> list[StockSnapshot]:
    """剔除上市天数不足 min_days 的次新股。"""
    return [s for s in snapshots if (current_date - s.list_date).days >= min_days]
```

- [ ] **Step 4: 运行测试确认通过**

- [ ] **Step 5: 提交**

```bash
git add src/domain/strategy/services/filters/filter_new_listing.py tests/domain/strategy/test_filters.py
git commit -m "feat: add filter_new_listing to exclude IPOs < 365 days"
```

---

### Task 10: filter_penny_stock — 仙股过滤器

- [ ] **Step 1: 编写测试**

```python
# 追加到 tests/domain/strategy/test_filters.py

class TestFilterPennyStock:
    def test_removes_stocks_below_min_price(self):
        snaps = [
            _snap("000001.SZ", close=1.2),
            _snap("000002.SZ", close=1.5),
            _snap("000003.SZ", close=5.0),
        ]
        result = filter_penny_stock(snaps, min_price=1.5)
        assert len(result) == 2
        symbols = {s.symbol for s in result}
        assert symbols == {"000002.SZ", "000003.SZ"}

    def test_default_min_price(self):
        snaps = [_snap("000001.SZ", close=1.49)]
        assert len(filter_penny_stock(snaps)) == 0
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现**

```python
# src/domain/strategy/services/filters/filter_penny_stock.py
from src.domain.market.value_objects.stock_snapshot import StockSnapshot

def filter_penny_stock(
    snapshots: list[StockSnapshot],
    min_price: float = 1.5,
) -> list[StockSnapshot]:
    """剔除收盘价低于 min_price 的仙股，规避面值退市风险。"""
    return [s for s in snapshots if s.close >= min_price]
```

- [ ] **Step 4: 运行测试确认通过**

- [ ] **Step 5: 提交**

```bash
git add src/domain/strategy/services/filters/filter_penny_stock.py tests/domain/strategy/test_filters.py
git commit -m "feat: add filter_penny_stock to exclude stocks with close < 1.5"
```

---

### Task 11: filter_trading_status — 停牌/涨跌停过滤器

- [ ] **Step 1: 编写测试**

```python
# 追加到 tests/domain/strategy/test_filters.py

class TestFilterTradingStatus:
    def test_removes_suspended_stocks(self):
        snaps = [_snap("000001.SZ", volume=0), _snap("000002.SZ", volume=1e6)]
        result = filter_trading_status(snaps)
        assert len(result) == 1
        assert result[0].symbol == "000002.SZ"

    def test_removes_limit_up_or_down_lock(self):
        snaps = [
            _snap("000001.SZ", open=10.0, high=10.0, low=10.0, close=10.0),
            _snap("000002.SZ", open=10.0, high=11.0, low=9.5, close=10.5),
        ]
        result = filter_trading_status(snaps)
        assert len(result) == 1
        assert result[0].symbol == "000002.SZ"
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现**

```python
# src/domain/strategy/services/filters/filter_trading_status.py
from src.domain.market.value_objects.stock_snapshot import StockSnapshot

def filter_trading_status(snapshots: list[StockSnapshot]) -> list[StockSnapshot]:
    """剔除停牌（volume==0）或一字涨跌停（open==high==low==close，含非零）的标的。"""
    return [
        s for s in snapshots
        if s.volume > 0 and not (s.open == s.high == s.low == s.close)
    ]
```

- [ ] **Step 4: 运行测试确认通过**

- [ ] **Step 5: 提交**

```bash
git add src/domain/strategy/services/filters/filter_trading_status.py tests/domain/strategy/test_filters.py
git commit -m "feat: add filter_trading_status to exclude suspended/limit-locked stocks"
```

---

### Task 12: filter_quality — ROE/OCF 质量过滤器

- [ ] **Step 1: 编写测试**

```python
# 追加到 tests/domain/strategy/test_filters.py

class TestFilterQuality:
    def test_keeps_stocks_above_median_roe_and_positive_ocf(self):
        snaps = [
            _snap("A", roe_ttm=0.20, ocf_ttm=1e8),   # ROE high, OCF > 0 → keep
            _snap("B", roe_ttm=0.10, ocf_ttm=1e8),   # ROE mid, OCF > 0 → ?
            _snap("C", roe_ttm=0.05, ocf_ttm=1e8),   # ROE low, OCF > 0 → drop
            _snap("D", roe_ttm=0.25, ocf_ttm=-1e8),  # ROE high, OCF < 0 → drop
        ]
        # median ROE = (0.10 + 0.20) / 2... sorted: [0.05, 0.10, 0.20, 0.25], median = 0.10 (index 1)
        result = filter_quality(snaps)
        symbols = {s.symbol for s in result}
        assert symbols == {"A"}

    def test_excludes_missing_financials(self):
        snaps = [
            _snap("A", roe_ttm=None, ocf_ttm=1e8),
            _snap("B", roe_ttm=0.15, ocf_ttm=None),
            _snap("C", roe_ttm=0.15, ocf_ttm=1e8),
        ]
        result = filter_quality(snaps)
        assert len(result) == 1
        assert result[0].symbol == "C"

    def test_small_universe_returns_all_valid(self):
        snaps = [
            _snap("A", roe_ttm=0.15, ocf_ttm=1e8),
            _snap("B", roe_ttm=0.10, ocf_ttm=1e8),
        ]
        result = filter_quality(snaps, min_universe_size=30)
        assert len(result) == 2  # below min_universe_size, no filtering
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现**

```python
# src/domain/strategy/services/filters/filter_quality.py
from src.domain.market.value_objects.stock_snapshot import StockSnapshot

def filter_quality(
    snapshots: list[StockSnapshot],
    min_universe_size: int = 30,
) -> list[StockSnapshot]:
    """保留 ROE > 全市场中位数且 OCF > 0 的标的。"""
    valid = [s for s in snapshots if s.roe_ttm is not None and s.ocf_ttm is not None]
    if len(valid) < min_universe_size:
        return valid
    sorted_roe = sorted(s.roe_ttm for s in valid)  # type: ignore[arg-type]
    median_roe = sorted_roe[len(sorted_roe) // 2]
    return [s for s in valid if s.roe_ttm > median_roe and s.ocf_ttm > 0]
```

- [ ] **Step 4: 运行测试确认通过**

- [ ] **Step 5: 提交**

```bash
git add src/domain/strategy/services/filters/filter_quality.py tests/domain/strategy/test_filters.py
git commit -m "feat: add filter_quality for ROE > median + OCF > 0 screening"
```

---

### Task 13: CrossSectionalStrategy 基类

**Files:**
- Create: `src/domain/strategy/services/cross_sectional_strategy.py`
- Create: `tests/domain/strategy/test_cross_sectional_strategy.py`

- [ ] **Step 1: 编写测试**

```python
# tests/domain/strategy/test_cross_sectional_strategy.py
import pytest
from datetime import datetime
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.account.entities.position import Position
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection

class _ConcreteCS(CrossSectionalStrategy):
    @property
    def name(self) -> str:
        return "TestCS"

    def generate_cross_sectional_signals(self, universe, current_positions, current_date):
        return [
            Signal(symbol=s.symbol, direction=SignalDirection.BUY,
                   confidence_score=1.0, strategy_name=self.name)
            for s in universe
        ]

class TestCrossSectionalStrategy:
    def test_generate_signals_raises_not_implemented(self):
        strategy = _ConcreteCS()
        with pytest.raises(NotImplementedError, match="generate_cross_sectional_signals"):
            strategy.generate_signals({}, [])

    def test_isinstance_of_base_strategy(self):
        from src.domain.strategy.services.base_strategy import BaseStrategy
        strategy = _ConcreteCS()
        assert isinstance(strategy, BaseStrategy)

    def test_concrete_implementation_works(self):
        strategy = _ConcreteCS()
        snap = StockSnapshot(
            symbol="000001.SZ", date=datetime(2024, 6, 15),
            open=10.0, high=10.5, low=9.8, close=10.2, volume=1e6,
            name="Test", list_date=datetime(2000, 1, 1), market_cap=1e10,
        )
        signals = strategy.generate_cross_sectional_signals(
            [snap], [], datetime(2024, 6, 15)
        )
        assert len(signals) == 1
        assert signals[0].symbol == "000001.SZ"
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现**

```python
# src/domain/strategy/services/cross_sectional_strategy.py
from abc import ABC, abstractmethod
from datetime import datetime
from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.services.base_strategy import BaseStrategy
from src.domain.strategy.value_objects.signal import Signal

class CrossSectionalStrategy(BaseStrategy, ABC):
    """截面策略基类 — 操作全市场日频快照，产出批量信号。"""

    @abstractmethod
    def generate_cross_sectional_signals(
        self,
        universe: list[StockSnapshot],
        current_positions: list[Position],
        current_date: datetime,
    ) -> list[Signal]:
        ...

    def generate_signals(
        self,
        market_data: dict[str, list[Bar]],
        current_positions: list[Position],
    ) -> list[Signal]:
        raise NotImplementedError(
            "Use generate_cross_sectional_signals() for cross-sectional strategies"
        )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run python -m pytest tests/domain/strategy/test_cross_sectional_strategy.py -v
```
Expected: 3 PASS

- [ ] **Step 5: 提交**

```bash
git add src/domain/strategy/services/cross_sectional_strategy.py tests/domain/strategy/test_cross_sectional_strategy.py
git commit -m "feat: add CrossSectionalStrategy base class"
```

---

### Task 14: MicroValueStrategy

**Files:**
- Create: `src/domain/strategy/services/strategies/micro_value_strategy.py`
- Create: `tests/domain/strategy/test_micro_value_strategy.py`

- [ ] **Step 1: 编写测试**

```python
# tests/domain/strategy/test_micro_value_strategy.py
from datetime import datetime
from src.domain.strategy.services.strategies.micro_value_strategy import MicroValueStrategy
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.market.value_objects.stock_snapshot import StockSnapshot

def _snap(symbol, mcap, **kwargs):
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 6, 11),  # Tuesday
        open=10.0, high=10.5, low=9.8, close=10.2, volume=1e6,
        name="Normal Stock", list_date=datetime(2000, 1, 1),
        market_cap=mcap, roe_ttm=0.20, ocf_ttm=1e8, **kwargs
    )

class TestMicroValueStrategy:
    def test_calendar_circuit_breaker_january_returns_empty(self):
        strategy = MicroValueStrategy(top_n=5)
        universe = [_snap("A", 1e9), _snap("B", 2e9), _snap("C", 3e9), _snap("D", 4e9), _snap("E", 5e9)]
        jan_date = datetime(2024, 1, 9)  # Tuesday in January
        signals = strategy.generate_cross_sectional_signals(universe, [], jan_date)
        assert signals == []

    def test_calendar_circuit_breaker_april_returns_empty(self):
        strategy = MicroValueStrategy(top_n=5)
        universe = [_snap("A", 1e9) for _ in range(5)]
        apr_date = datetime(2024, 4, 9)  # Tuesday in April
        signals = strategy.generate_cross_sectional_signals(universe, [], apr_date)
        assert signals == []

    def test_non_tuesday_returns_empty(self):
        strategy = MicroValueStrategy(top_n=5)
        universe = [_snap("A", 1e9) for _ in range(10)]
        monday = datetime(2024, 6, 10)  # Monday
        signals = strategy.generate_cross_sectional_signals(universe, [], monday)
        assert signals == []

    def test_tuesday_produces_top_n_buy_signals(self):
        strategy = MicroValueStrategy(top_n=3)
        universe = [
            _snap("B", 2e9), _snap("A", 1e9), _snap("D", 4e9),
            _snap("C", 3e9), _snap("E", 5e9),
        ]
        tuesday = datetime(2024, 6, 11)  # Tuesday
        signals = strategy.generate_cross_sectional_signals(universe, [], tuesday)
        assert len(signals) == 3
        # Should be A, B, C (mcap: 1e9, 2e9, 3e9)
        assert signals[0].symbol == "A"
        assert signals[1].symbol == "B"
        assert signals[2].symbol == "C"
        for s in signals:
            assert s.direction == SignalDirection.BUY
            assert s.strategy_name == "MicroValueStrategy"

    def test_filters_penny_stocks_before_ranking(self):
        strategy = MicroValueStrategy(top_n=3)
        universe = [
            _snap("Penny", 1e8, close=1.0),  # filtered out
            _snap("A", 1e9, close=10.0),
            _snap("B", 2e9, close=10.0),
            _snap("C", 3e9, close=10.0),
            _snap("D", 4e9, close=10.0),
        ]
        tuesday = datetime(2024, 6, 11)
        signals = strategy.generate_cross_sectional_signals(universe, [], tuesday)
        assert len(signals) == 3
        assert "Penny" not in {s.symbol for s in signals}

    def test_name_property(self):
        assert MicroValueStrategy().name == "MicroValueStrategy"
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现**

```python
# src/domain/strategy/services/strategies/micro_value_strategy.py
from datetime import datetime
from src.domain.account.entities.position import Position
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.domain.strategy.services.filters.filter_st import filter_st
from src.domain.strategy.services.filters.filter_new_listing import filter_new_listing
from src.domain.strategy.services.filters.filter_penny_stock import filter_penny_stock
from src.domain.strategy.services.filters.filter_trading_status import filter_trading_status
from src.domain.strategy.services.filters.filter_quality import filter_quality
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection


class MicroValueStrategy(CrossSectionalStrategy):
    """微盘价值质量增强策略。

    逻辑:
    1. 日历熔断: 1月/4月空仓
    2. 错峰调仓: 仅周二
    3. 过滤链: ST → 次新 → 仙股 → 停牌 → 质量
    4. 按市值升序 → 截取 top_n
    """

    def __init__(self, top_n: int = 9) -> None:
        self._top_n = top_n

    @property
    def name(self) -> str:
        return "MicroValueStrategy"

    def generate_cross_sectional_signals(
        self,
        universe: list[StockSnapshot],
        current_positions: list[Position],
        current_date: datetime,
    ) -> list[Signal]:
        if current_date.month in (1, 4):
            return []
        if current_date.weekday() != 1:
            return []

        pool = universe
        pool = filter_st(pool)
        pool = filter_new_listing(pool, current_date)
        pool = filter_penny_stock(pool)
        pool = filter_trading_status(pool)
        pool = filter_quality(pool)

        ranked = sorted(pool, key=lambda s: s.market_cap)
        targets = ranked[:self._top_n]

        return [
            Signal(
                symbol=t.symbol, direction=SignalDirection.BUY,
                confidence_score=1.0, strategy_name=self.name,
                reason=f"MicroValue rank #{i+1}, mcap={t.market_cap:.0f}",
            )
            for i, t in enumerate(targets)
        ]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run python -m pytest tests/domain/strategy/test_micro_value_strategy.py -v
```
Expected: 6 PASS

- [ ] **Step 5: 提交**

```bash
git add src/domain/strategy/services/strategies/micro_value_strategy.py tests/domain/strategy/test_micro_value_strategy.py
git commit -m "feat: add MicroValueStrategy with filter chain and Tuesday-only rebalancing"
```

---

## Sprint 3: 组合层 — 批量 Sizer

### Task 15: IPositionSizer 增加 calculate_targets 抽象方法

**Files:**
- Modify: `src/domain/portfolio/interfaces/position_sizer.py`

- [ ] **Step 1: 扩展接口**

```python
# 在现有 calculate_target 方法后追加
@abstractmethod
def calculate_targets(
    self,
    signals: list[Signal],
    prices: dict[str, float],
    asset: Asset,
    positions: list[Position],
) -> list:
    """批量计算目标仓位。

    Args:
        signals: 策略 + 风控产出的全部信号列表。
        prices: symbol → 当前价格映射。
        asset: 账户资产。
        positions: 当前全部持仓。

    Returns:
        list[OrderTarget]: 包含调仓所需的全部 BUY 和 SELL 目标。
    """
    ...
```

- [ ] **Step 2: 提交**

```bash
git add src/domain/portfolio/interfaces/position_sizer.py
git commit -m "feat: add calculate_targets() batch method to IPositionSizer"
```

---

### Task 16: EqualWeightSizer 实现 calculate_targets

**Files:**
- Modify: `src/domain/portfolio/services/equal_weight_sizer.py`
- Modify: `tests/domain/portfolio/test_equal_weight_sizer.py`

- [ ] **Step 1: 编写测试**

```python
# 追加到 tests/domain/portfolio/test_equal_weight_sizer.py
from src.domain.portfolio.entities.order_target import OrderTarget

def _signal(symbol, direction=OrderDirection.BUY):
    return Signal(symbol=symbol, direction=direction, confidence_score=1.0, generated_at=datetime.now())

def _asset(total=100000.0):
    return Asset(account_id="TEST", total_asset=total, available_cash=total, frozen_cash=0)

def _pos(symbol, total_vol, avail_vol, avg_cost=10.0):
    return Position(account_id="TEST", ticker=symbol, total_volume=total_vol, available_volume=avail_vol, average_cost=avg_cost)

class TestEqualWeightSizerBatch:
    def test_calculate_targets_clears_all_when_no_signals(self):
        sizer = EqualWeightSizer(n_symbols=5)
        targets = sizer.calculate_targets(
            signals=[], prices={"A": 10.0, "B": 10.0},
            asset=_asset(), positions=[_pos("A", 1000, 1000)],
        )
        assert len(targets) == 1
        assert targets[0].symbol == "A"
        assert targets[0].direction == OrderDirection.SELL

    def test_calculate_targets_sells_positions_not_in_target_pool(self):
        sizer = EqualWeightSizer(n_symbols=2)
        signals = [_signal("A", OrderDirection.BUY), _signal("B", OrderDirection.BUY)]
        targets = sizer.calculate_targets(
            signals=signals, prices={"A": 10.0, "B": 10.0, "C": 10.0},
            asset=_asset(), positions=[_pos("C", 500, 500)],
        )
        sell_targets = [t for t in targets if t.direction == OrderDirection.SELL]
        assert len(sell_targets) == 1
        assert sell_targets[0].symbol == "C"

    def test_calculate_targets_buys_underweight_targets(self):
        sizer = EqualWeightSizer(n_symbols=2)
        signals = [_signal("A", OrderDirection.BUY), _signal("B", OrderDirection.BUY)]
        targets = sizer.calculate_targets(
            signals=signals, prices={"A": 10.0, "B": 10.0},
            asset=_asset(100000), positions=[],
        )
        buy_targets = [t for t in targets if t.direction == OrderDirection.BUY]
        assert len(buy_targets) == 2
        # Each should be ~5000 value / 10.0 = 500, but rounded to 100s = 500
        for t in buy_targets:
            assert t.volume >= 100
            assert t.volume % 100 == 0
```

- [ ] **Step 2: 运行测试确认失败（calculate_targets 未实现）**

- [ ] **Step 3: 实现 calculate_targets**

```python
# 在 EqualWeightSizer 类中追加方法
def calculate_targets(
    self, signals: list[Signal], prices: dict[str, float],
    asset: Asset, positions: list[Position],
) -> list[OrderTarget]:
    from src.domain.portfolio.entities.order_target import OrderTarget

    targets: list[OrderTarget] = []
    pos_map = {p.ticker: p for p in positions}
    buy_signals = [s for s in signals if s.direction == OrderDirection.BUY]

    if not buy_signals:
        # 目标池为空 → 清仓所有持仓
        for pos in positions:
            p = prices.get(pos.ticker, pos.average_cost)
            targets.append(OrderTarget(
                symbol=pos.ticker, direction=OrderDirection.SELL,
                volume=pos.available_volume, price=p,
                strategy_name="EqualWeightSizer"
            ))
        return targets

    n = len(buy_signals)
    target_value_per = asset.total_asset / n
    target_symbols = {s.symbol for s in buy_signals}

    for sig in buy_signals:
        price = prices.get(sig.symbol, 0.0)
        if price <= 0:
            continue
        pos = pos_map.get(sig.symbol)
        current_value = pos.total_volume * price if pos else 0.0
        diff_value = target_value_per - current_value
        diff_volume = int(diff_value / price)
        diff_volume = (diff_volume // 100) * 100

        if diff_volume > 0:
            targets.append(OrderTarget(
                symbol=sig.symbol, direction=OrderDirection.BUY,
                volume=diff_volume, price=price,
                strategy_name=sig.strategy_name,
            ))
        elif diff_volume < 0 and pos:
            sell_vol = min(abs(diff_volume), pos.available_volume)
            if sell_vol > 0:
                targets.append(OrderTarget(
                    symbol=sig.symbol, direction=OrderDirection.SELL,
                    volume=sell_vol, price=price,
                    strategy_name=sig.strategy_name,
                ))

    # 不在目标池中的持仓 → 清仓
    for pos in positions:
        if pos.ticker not in target_symbols and pos.available_volume > 0:
            price = prices.get(pos.ticker, pos.average_cost)
            targets.append(OrderTarget(
                symbol=pos.ticker, direction=OrderDirection.SELL,
                volume=pos.available_volume, price=price,
                strategy_name="EqualWeightSizer",
            ))

    return targets
```

- [ ] **Step 4: 运行全部 EqualWeightSizer 测试**

```bash
uv run python -m pytest tests/domain/portfolio/test_equal_weight_sizer.py -v
```
Expected: all PASS (old + new)

- [ ] **Step 5: 提交**

```bash
git add src/domain/portfolio/services/equal_weight_sizer.py tests/domain/portfolio/test_equal_weight_sizer.py
git commit -m "feat: implement EqualWeightSizer.calculate_targets() batch rebalancing"
```

---

### Task 17: FixedRatioSizer 实现 calculate_targets（接口完备）

**Files:**
- Modify: `src/domain/portfolio/services/sizers/fixed_ratio_sizer.py`

- [ ] **Step 1: 委托实现**

```python
# 在 FixedRatioSizer 类中追加
def calculate_targets(
    self, signals: list[Signal], prices: dict[str, float],
    asset: Asset, positions: list[Position],
) -> list[OrderTarget]:
    from src.domain.portfolio.entities.order_target import OrderTarget
    pos_map = {p.ticker: p for p in positions}
    targets: list[OrderTarget] = []
    for sig in signals:
        price = prices.get(sig.symbol, 0.0)
        if price <= 0:
            continue
        volume = self.calculate_target(sig, price, asset, pos_map.get(sig.symbol))
        if volume <= 0:
            continue
        targets.append(OrderTarget(
            symbol=sig.symbol, direction=sig.direction,
            volume=volume, price=price, strategy_name=sig.strategy_name,
        ))
    return targets
```

- [ ] **Step 2: 运行现有 FixedRatioSizer 测试确认兼容**

```bash
uv run python -m pytest tests/domain/portfolio/test_fixed_ratio_sizer.py -v
```

- [ ] **Step 3: 提交**

```bash
git add src/domain/portfolio/services/sizers/fixed_ratio_sizer.py
git commit -m "feat: add FixedRatioSizer.calculate_targets() delegation"
```

---

## Sprint 4: 风控层 — 三分层架构

### Task 18: BaseRiskSignalPolicy 接口

**Files:**
- Create: `src/domain/risk/services/base_risk_signal_policy.py`
- Create: `tests/domain/risk/test_risk_signal_policies.py`

- [ ] **Step 1: 编写测试 + 实现（接口极简，同一步）**

```python
# src/domain/risk/services/base_risk_signal_policy.py
from abc import ABC, abstractmethod
from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.strategy.value_objects.signal import Signal


class BaseRiskSignalPolicy(ABC):
    """盘后风控信号策略 — 主动产出 SELL 信号，而非拦截订单。"""

    @abstractmethod
    def evaluate_positions(
        self, positions: list[Position], bars: dict[str, Bar]
    ) -> list[Signal]:
        ...
```

- [ ] **Step 2: 提交**

```bash
git add src/domain/risk/services/base_risk_signal_policy.py
git commit -m "feat: add BaseRiskSignalPolicy interface for post-trade risk signals"
```

---

### Task 19: SystemRiskGate + GateResult

**Files:**
- Create: `src/domain/risk/services/system_risk_gate.py`
- Create: 测试追加到 `tests/domain/risk/test_risk_signal_policies.py`

- [ ] **Step 1: 编写测试**

```python
# 追加到 tests/domain/risk/test_risk_signal_policies.py
from datetime import datetime, timedelta
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.risk.services.system_risk_gate import SystemRiskGate, GateResult

def _index_bar(dt, close):
    return Bar(symbol="000852.SH", timeframe=Timeframe.DAY_1, timestamp=dt,
               open=close, high=close, low=close, close=close, volume=1e6)

class TestSystemRiskGate:
    def test_passes_when_above_ma20(self):
        bars = [_index_bar(datetime(2024, 6, 1) + timedelta(days=i), 6000) for i in range(25)]
        gate = SystemRiskGate(bars)
        result = gate.check_gate(datetime(2024, 6, 25))
        assert result.pass_buy is True

    def test_blocks_when_below_ma20(self):
        dt = datetime(2024, 6, 1)
        # 19 bars at 6000, then 5 bars dropping to 5000
        bars = [_index_bar(dt + timedelta(days=i), 6000) for i in range(20)]
        bars += [_index_bar(dt + timedelta(days=20 + i), 5000) for i in range(5)]
        gate = SystemRiskGate(bars)
        result = gate.check_gate(datetime(2024, 6, 25))
        assert result.pass_buy is False
        assert "MA20" in result.reason

    def test_passes_with_insufficient_data(self):
        bars = [_index_bar(datetime(2024, 6, 1) + timedelta(days=i), 6000) for i in range(10)]
        gate = SystemRiskGate(bars)
        result = gate.check_gate(datetime(2024, 6, 10))
        assert result.pass_buy is True

    def test_set_index_data_updates_bars(self):
        gate = SystemRiskGate()
        gate.set_index_data([_index_bar(datetime(2024, 6, 1) + timedelta(days=i), 6000) for i in range(20)])
        assert len(gate._index_bars) == 20
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现**

```python
# src/domain/risk/services/system_risk_gate.py
from dataclasses import dataclass
from datetime import datetime
from src.domain.market.value_objects.bar import Bar


@dataclass(slots=True, kw_only=True)
class GateResult:
    pass_buy: bool
    reason: str = ""


class SystemRiskGate:
    """盘前系统级风控门禁。

    判定当日是否允许买入。不审核单个订单。SELL 信号不受此门禁影响。
    """

    def __init__(self, index_bars: list[Bar] | None = None) -> None:
        self._index_bars = index_bars or []

    def set_index_data(self, bars: list[Bar]) -> None:
        self._index_bars = bars

    def check_gate(self, current_date: datetime) -> GateResult:
        if len(self._index_bars) < 20:
            return GateResult(pass_buy=True)
        recent = self._index_bars[-20:]
        ma20 = sum(b.close for b in recent) / 20
        if recent[-1].close < ma20:
            return GateResult(
                pass_buy=False,
                reason=f"Market circuit breaker: {recent[-1].close:.0f} < MA20 {ma20:.0f}",
            )
        return GateResult(pass_buy=True)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run python -m pytest tests/domain/risk/test_risk_signal_policies.py::TestSystemRiskGate -v
```
Expected: 4 PASS

- [ ] **Step 5: 提交**

```bash
git add src/domain/risk/services/system_risk_gate.py tests/domain/risk/test_risk_signal_policies.py
git commit -m "feat: add SystemRiskGate for market circuit breaker (CSI1000 < MA20)"
```

---

### Task 20: LimitUpBreakPolicy

- [ ] **Step 1: 编写测试**

```python
# 追加到 tests/domain/risk/test_risk_signal_policies.py
from src.domain.risk.services.risk_policies.limit_up_break_policy import LimitUpBreakPolicy
from src.domain.account.entities.position import Position
from src.domain.strategy.value_objects.signal_direction import SignalDirection

class TestLimitUpBreakPolicy:
    def test_triggers_sell_when_limit_up_broken(self):
        policy = LimitUpBreakPolicy()
        pos = Position(account_id="A", ticker="000001.SZ", total_volume=1000, available_volume=1000, average_cost=10.0)
        # prev_close=10.0, limit_up=11.00, high hits 11.00 but close 10.80 < 11.00
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime.now(),
                  open=10.5, high=11.00, low=10.5, close=10.80, volume=1e6, prev_close=10.0)
        signals = policy.evaluate_positions([pos], {"000001.SZ": bar})
        assert len(signals) == 1
        assert signals[0].direction == SignalDirection.SELL
        assert "涨停破板" in signals[0].reason

    def test_no_trigger_when_close_at_limit_up(self):
        policy = LimitUpBreakPolicy()
        pos = Position(account_id="A", ticker="000001.SZ", total_volume=1000, available_volume=1000, average_cost=10.0)
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime.now(),
                  open=10.5, high=11.00, low=10.5, close=11.00, volume=1e6, prev_close=10.0)
        signals = policy.evaluate_positions([pos], {"000001.SZ": bar})
        assert len(signals) == 0

    def test_no_trigger_when_not_touching_limit_up(self):
        policy = LimitUpBreakPolicy()
        pos = Position(account_id="A", ticker="000001.SZ", total_volume=1000, available_volume=1000, average_cost=10.0)
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime.now(),
                  open=10.5, high=10.90, low=10.5, close=10.80, volume=1e6, prev_close=10.0)
        signals = policy.evaluate_positions([pos], {"000001.SZ": bar})
        assert len(signals) == 0
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现**

```python
# src/domain/risk/services/risk_policies/limit_up_break_policy.py
from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.price_limit import calculate_price_limits
from src.domain.risk.services.base_risk_signal_policy import BaseRiskSignalPolicy
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection


class LimitUpBreakPolicy(BaseRiskSignalPolicy):
    """涨停破板卖出策略。

    若当日最高价触及涨停价，但收盘价未封住涨停，则判定为多头动能衰竭，
    无条件触发清仓卖出信号。
    """

    def evaluate_positions(
        self, positions: list[Position], bars: dict[str, Bar]
    ) -> list[Signal]:
        signals: list[Signal] = []
        for pos in positions:
            bar = bars.get(pos.ticker)
            if bar is None or bar.volume <= 0 or bar.prev_close <= 0:
                continue
            price_limit = calculate_price_limits(bar.prev_close)
            if bar.high >= price_limit.limit_up and bar.close < price_limit.limit_up:
                signals.append(Signal(
                    symbol=pos.ticker, direction=SignalDirection.SELL,
                    confidence_score=1.0, strategy_name="LimitUpBreak",
                    reason=f"涨停破板: high={bar.high} limit_up={price_limit.limit_up} close={bar.close}",
                ))
        return signals
```

- [ ] **Step 4: 运行测试确认通过**

- [ ] **Step 5: 提交**

```bash
git add src/domain/risk/services/risk_policies/limit_up_break_policy.py tests/domain/risk/test_risk_signal_policies.py
git commit -m "feat: add LimitUpBreakPolicy for limit-up break sell signals"
```

---

### Task 21: HardStopLossPolicy

- [ ] **Step 1: 编写测试**

```python
# 追加到 tests/domain/risk/test_risk_signal_policies.py
from src.domain.risk.services.risk_policies.hard_stop_loss_policy import HardStopLossPolicy

class TestHardStopLossPolicy:
    def test_triggers_sell_when_loss_exceeds_threshold(self):
        policy = HardStopLossPolicy(max_loss_ratio=0.03)
        pos = Position(account_id="A", ticker="000001.SZ", total_volume=1000, available_volume=1000, average_cost=10.0)
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime.now(),
                  open=9.0, high=9.0, low=9.0, close=9.50, volume=1e6)
        # loss = (9.50 - 10.0) / 10.0 = -5% > -3%
        signals = policy.evaluate_positions([pos], {"000001.SZ": bar})
        assert len(signals) == 1
        assert signals[0].direction == SignalDirection.SELL

    def test_no_trigger_when_loss_within_threshold(self):
        policy = HardStopLossPolicy(max_loss_ratio=0.03)
        pos = Position(account_id="A", ticker="000001.SZ", total_volume=1000, available_volume=1000, average_cost=10.0)
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime.now(),
                  open=9.8, high=9.8, low=9.8, close=9.80, volume=1e6)
        # loss = (9.80 - 10.0) / 10.0 = -2% > -3%, no trigger
        signals = policy.evaluate_positions([pos], {"000001.SZ": bar})
        assert len(signals) == 0

    def test_no_trigger_when_profitable(self):
        policy = HardStopLossPolicy(max_loss_ratio=0.03)
        pos = Position(account_id="A", ticker="000001.SZ", total_volume=1000, available_volume=1000, average_cost=10.0)
        bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime.now(),
                  open=11.0, high=11.0, low=11.0, close=11.0, volume=1e6)
        signals = policy.evaluate_positions([pos], {"000001.SZ": bar})
        assert len(signals) == 0
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现**

```python
# src/domain/risk/services/risk_policies/hard_stop_loss_policy.py
from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.risk.services.base_risk_signal_policy import BaseRiskSignalPolicy
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection


class HardStopLossPolicy(BaseRiskSignalPolicy):
    """绝对止损策略。

    若持仓账面亏损超过 max_loss_ratio，立刻生成市价清仓信号。
    """

    def __init__(self, max_loss_ratio: float = 0.03) -> None:
        self._max_loss = max_loss_ratio

    def evaluate_positions(
        self, positions: list[Position], bars: dict[str, Bar]
    ) -> list[Signal]:
        signals: list[Signal] = []
        for pos in positions:
            bar = bars.get(pos.ticker)
            if bar is None or pos.total_volume <= 0 or pos.average_cost <= 0:
                continue
            loss_ratio = (bar.close - pos.average_cost) / pos.average_cost
            if loss_ratio < -self._max_loss:
                signals.append(Signal(
                    symbol=pos.ticker, direction=SignalDirection.SELL,
                    confidence_score=1.0, strategy_name="HardStopLoss",
                    reason=f"Stop loss: {loss_ratio:.2%} < -{self._max_loss:.0%}",
                ))
        return signals
```

- [ ] **Step 4: 运行测试确认通过**

- [ ] **Step 5: 提交**

```bash
git add src/domain/risk/services/risk_policies/hard_stop_loss_policy.py tests/domain/risk/test_risk_signal_policies.py
git commit -m "feat: add HardStopLossPolicy for position-level 3% stop loss"
```

---

### Task 22: RiskSignalGenerator

**Files:**
- Create: `src/domain/risk/services/risk_signal_generator.py`

- [ ] **Step 1: 编写测试**

```python
# 追加到 tests/domain/risk/test_risk_signal_policies.py
from src.domain.risk.services.risk_signal_generator import RiskSignalGenerator

class _FakePolicy(BaseRiskSignalPolicy):
    def __init__(self, signals):
        self.signals = signals
    def evaluate_positions(self, positions, bars):
        return self.signals

class TestRiskSignalGenerator:
    def test_aggregates_all_policy_signals(self):
        p1 = _FakePolicy([Signal(symbol="A", direction=SignalDirection.SELL, confidence_score=1.0)])
        p2 = _FakePolicy([Signal(symbol="B", direction=SignalDirection.SELL, confidence_score=1.0)])
        gen = RiskSignalGenerator([p1, p2])
        signals = gen.evaluate([], {})
        assert len(signals) == 2

    def test_empty_policies_returns_empty(self):
        gen = RiskSignalGenerator()
        assert gen.evaluate([], {}) == []
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现**

```python
# src/domain/risk/services/risk_signal_generator.py
from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.risk.services.base_risk_signal_policy import BaseRiskSignalPolicy
from src.domain.strategy.value_objects.signal import Signal


class RiskSignalGenerator:
    """盘后风控信号生成器。

    聚合多个 BaseRiskSignalPolicy，评估持仓状态，主动产出 SELL 信号。
    """

    def __init__(self, policies: list[BaseRiskSignalPolicy] | None = None) -> None:
        self._policies = policies or []

    def evaluate(
        self, positions: list[Position], bars: dict[str, Bar]
    ) -> list[Signal]:
        signals: list[Signal] = []
        for policy in self._policies:
            signals.extend(policy.evaluate_positions(positions, bars))
        return signals
```

- [ ] **Step 4: 运行测试确认通过**

- [ ] **Step 5: 提交**

```bash
git add src/domain/risk/services/risk_signal_generator.py tests/domain/risk/test_risk_signal_policies.py
git commit -m "feat: add RiskSignalGenerator to aggregate post-trade risk sell signals"
```

---

## Sprint 5: 应用层 — 回测循环改造与可视化

### Task 23: BacktestReport 增加 turnover_rate

**Files:**
- Modify: `src/domain/backtest/entities/backtest_report.py`
- Create: `tests/domain/backtest/services/test_turnover_rate.py`

- [ ] **Step 1: 编写测试**

```python
# tests/domain/backtest/services/test_turnover_rate.py
from datetime import datetime
from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.domain.backtest.value_objects.trade_record import TradeRecord
from src.domain.trade.value_objects.order_direction import OrderDirection

def test_turnover_rate_basic():
    snapshots = [
        DailySnapshot(date=datetime(2024, 6, 10), total_asset=100000, available_cash=50000, market_value=50000, pnl=0, return_rate=0),
        DailySnapshot(date=datetime(2024, 6, 11), total_asset=101000, available_cash=40000, market_value=61000, pnl=1000, return_rate=0.01),
    ]
    trades = [
        TradeRecord(symbol="A", direction=OrderDirection.BUY, execute_at=datetime(2024, 6, 11), price=10.0, volume=1000),
    ]
    report = BacktestReport(
        start_date=datetime(2024, 6, 10), end_date=datetime(2024, 6, 11),
        initial_capital=100000, final_capital=101000,
        total_return=0.01, annualized_return=0.1, max_drawdown=0.0,
        win_rate=1.0, profit_loss_ratio=1.0, trade_count=1,
        snapshots=snapshots, trades=trades,
        dates=[s.date for s in snapshots],
        equity_curve=[s.total_asset for s in snapshots],
        daily_returns=[s.return_rate for s in snapshots],
    )
    # turnover = sum(trade_value) / avg_equity
    # trade_value = 1000 * 10 = 10000
    # avg_equity = (100000 + 101000) / 2 = 100500
    # daily_turnover = 10000 / 100500 ≈ 0.0995
    assert report.turnover_rate > 0
    assert report.turnover_rate < 1.0
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现**

```python
# 在 BacktestReport 类中追加 @property
@property
def turnover_rate(self) -> float:
    """日均换手率 = 日均交易额 / 日均总资产。"""
    if not self.trades or not self.snapshots:
        return 0.0
    total_trade_value = sum(t.price * t.volume for t in self.trades)
    avg_equity = sum(s.total_asset for s in self.snapshots) / len(self.snapshots)
    if avg_equity <= 0:
        return 0.0
    return total_trade_value / avg_equity
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run python -m pytest tests/domain/backtest/services/test_turnover_rate.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/domain/backtest/entities/backtest_report.py tests/domain/backtest/services/test_turnover_rate.py
git commit -m "feat: add BacktestReport.turnover_rate property"
```

---

### Task 24: BacktestAppService 双模式回测循环

**Files:**
- Modify: `src/application/backtest_app.py`

- [ ] **Step 1: 增加截面循环方法**

在 `run_backtest()` 的时序策略循环之前，插入路由逻辑和截面方法。

```python
# 在 run_backtest() 中，时序策略循环之前插入:
for i, strategy in enumerate(strategies):
    sub_account_id = f"BT_{strategy.name}_{start_date.strftime('%Y%m%d')}"
    self.trade_gateway.create_sub_account(sub_account_id, initial_capital)
    is_last = (i == len(strategies) - 1)

    if isinstance(strategy, CrossSectionalStrategy):
        report = self._run_cross_sectional_strategy(
            symbols, start_date, end_date, base_timeframe,
            strategy, sub_account_id, initial_capital,
            plot=(plot and is_last),
        )
    else:
        report = self._run_single_strategy(
            symbols, start_date, end_date, base_timeframe,
            strategy, sub_account_id, initial_capital,
            plot=(plot and is_last),
        )
    reports.append(report)
```

- [ ] **Step 2: 实现 `_run_cross_sectional_strategy()`**

```python
def _run_cross_sectional_strategy(
    self, symbols, start_date, end_date, base_timeframe,
    strategy, account_id, initial_capital, plot=False,
) -> BacktestReport:
    """执行截面策略回测循环。"""
    from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
    from src.domain.risk.services.system_risk_gate import SystemRiskGate
    from src.domain.risk.services.risk_signal_generator import RiskSignalGenerator
    from src.domain.risk.services.risk_policies.limit_up_break_policy import LimitUpBreakPolicy
    from src.domain.risk.services.risk_policies.hard_stop_loss_policy import HardStopLossPolicy
    from src.infrastructure.ml_engine.feature_pipeline import FeaturePipeline
    from src.infrastructure.logging.backtest_logger import BacktestProgress

    self.trade_gateway.activate_account(account_id)
    self.snapshots: list[DailySnapshot] = []

    all_timestamps = self.market_gateway.get_all_timestamps(base_timeframe)
    valid_timestamps = [ts for ts in all_timestamps if start_date <= ts <= end_date]

    if not valid_timestamps:
        return self.evaluator.evaluate(
            start_date=start_date, end_date=end_date,
            initial_capital=initial_capital, snapshots=[], trades=[],
        )

    # 风控组件初始化（index_data 由外部传入）
    system_gate = SystemRiskGate()
    risk_signal_gen = RiskSignalGenerator([
        LimitUpBreakPolicy(),
        HardStopLossPolicy(max_loss_ratio=0.03),
    ])

    progress = BacktestProgress(len(valid_timestamps))
    fundamental_registry = getattr(self, 'fundamental_registry', None)

    for current_time in valid_timestamps:
        progress.update(current_time)
        self.market_gateway.set_current_time(current_time)

        # [01] 截面构建
        bars: dict[str, Bar] = {}
        for sym in symbols:
            recent = self.market_gateway.get_recent_bars(sym, base_timeframe, 1)
            if recent:
                bars[sym] = recent[-1]

        universe = []
        if fundamental_registry:
            universe = FeaturePipeline.build_cross_section(
                current_time, bars, fundamental_registry
            )

        # [02] 门禁
        gate = system_gate.check_gate(current_time)

        # [03-04] 策略 + 风控信号
        strategy_signals = strategy.generate_cross_sectional_signals(
            universe, self.trade_gateway.get_positions(), current_time
        )
        risk_signals = risk_signal_gen.evaluate(
            self.trade_gateway.get_positions(), bars
        )
        all_signals = strategy_signals + risk_signals

        # [06] 熔断：只禁 BUY
        if not gate.pass_buy:
            all_signals = [s for s in all_signals if s.direction != SignalDirection.BUY]

        # [07] 批量 Sizer
        prices = {sym: bar.open for sym, bar in bars.items()}
        targets = self.sizer.calculate_targets(
            all_signals, prices, self.trade_gateway.get_asset(),
            self.trade_gateway.get_positions(),
        )

        # [08] SELL 优先
        targets.sort(key=lambda t: 0 if t.direction == OrderDirection.SELL else 1)

        # [09] 逐单执行
        for target in targets:
            order = Order(
                order_id=f"ORD_{current_time.strftime('%Y%m%d')}_{target.symbol}",
                account_id=account_id,
                ticker=target.symbol,
                direction=target.direction,
                price=target.price,
                volume=target.volume,
                type=OrderType.LIMIT,
                status=OrderStatus.CREATED,
                created_at=current_time,
            )
            try:
                self.trade_gateway.place_order(order)
            except Exception as e:
                print(f"[{current_time}] Order error for {target.symbol}: {e}")

        # [10-11] 结算 + 快照
        all_orders = self.trade_gateway.list_orders()
        all_positions = self.trade_gateway.get_positions()
        asset = self.trade_gateway.get_asset()
        if asset is None:
            raise ValueError("Asset not available from trade gateway.")
        self.settlement_service.process_daily_settlement(all_orders, all_positions, asset)

        current_prices = {sym: bar.close for sym, bar in bars.items()}
        self._record_snapshot(current_time, current_prices)

    report = self.evaluator.evaluate(
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital,
        snapshots=self.snapshots,
        trades=self.trade_gateway.list_trade_records(),
    )

    if plot:
        try:
            from src.infrastructure.visualization.plotter import BacktestPlotter
            BacktestPlotter().plot(report)
        except Exception as e:
            print(f"Error plotting: {e}")

    return report
```

- [ ] **Step 3: 添加导入**

在 `backtest_app.py` 顶部添加：
```python
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
```

- [ ] **Step 4: 修改 `_record_snapshot` 支持无 prices 场景**

现有 `_record_snapshot` 需要 `current_prices` 参数 — 截面循环中已构造，兼容。

- [ ] **Step 5: 运行现有回测测试确认不破坏时序路径**

```bash
uv run python -m pytest tests/application/test_backtest_app.py -v
```
Expected: all existing tests PASS

- [ ] **Step 6: 提交**

```bash
git add src/application/backtest_app.py
git commit -m "feat: add dual-mode backtest loop with cross-sectional path"
```

---

### Task 25: 可视化增强

**Files:**
- Modify: `src/infrastructure/visualization/plotter.py`

- [ ] **Step 1: 增强 Plotter**

```python
def plot(self, report: BacktestReport, benchmark_data: list[float] | None = None,
         benchmark_dates: list[datetime] | None = None, show: bool = True) -> None:
    if not HAS_MATPLOTLIB:
        print("Warning: matplotlib is not installed.")
        return

    if not report.dates or not report.equity_curve:
        print("Warning: No data to plot.")
        return

    try:
        plt.style.use('bmh')
    except OSError:
        pass

    has_benchmark = benchmark_data is not None and benchmark_dates is not None
    n_panels = 3

    fig, axes = plt.subplots(n_panels, 1, figsize=(14, 12), sharex=True)
    ax1, ax2, ax3 = axes[0], axes[1], axes[2]

    # Panel 1: 净值曲线
    normalized_equity = [v / report.initial_capital for v in report.equity_curve]
    ax1.plot(report.dates, normalized_equity, label='Strategy NAV', color='blue', linewidth=0.8)
    if has_benchmark:
        normalized_benchmark = [v / benchmark_data[0] for v in benchmark_data]
        ax1.plot(benchmark_dates, normalized_benchmark, label='CSI1000', color='gray', linewidth=0.8, alpha=0.7)
    ax1.axhline(y=1.0, color='black', linestyle='--', linewidth=0.5)
    ax1.set_title(f'Strategy: {report.annualized_return:.2%} annual, {report.max_drawdown:.2%} maxDD, Sharpe {report.sharpe_ratio:.2f}')
    ax1.set_ylabel('NAV')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # Panel 2: 每日收益率
    ax2.bar(report.dates, report.daily_returns, label='Daily Return', color='gray', alpha=0.5, width=0.8)
    ax2.axhline(0, color='black', linewidth=0.5)
    ax2.set_ylabel('Return')
    ax2.grid(True, alpha=0.3)

    # Panel 3: 回撤曲线
    drawdowns = []
    peak = report.initial_capital
    for v in report.equity_curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0
        drawdowns.append(-dd)
    ax3.fill_between(report.dates, drawdowns, 0, color='red', alpha=0.3, label='Drawdown')
    ax3.set_ylabel('Drawdown')
    ax3.set_xlabel('Date')
    ax3.grid(True, alpha=0.3)

    fig.autofmt_xdate()
    plt.tight_layout()

    # 打印核心指标
    print(f"Annual Return: {report.annualized_return:.2%}")
    print(f"Max Drawdown: {report.max_drawdown:.2%}")
    print(f"Sharpe Ratio: {report.sharpe_ratio:.2f}")
    print(f"Win Rate: {report.win_rate:.2%}")
    print(f"Turnover Rate: {report.turnover_rate:.2%}")
    print(f"Sortino Ratio: {report.sortino_ratio:.2f}")
    print(f"Calmar Ratio: {report.calmar_ratio:.2f}")

    if show:
        plt.show()
    else:
        plt.close(fig)
```

- [ ] **Step 2: 提交**

```bash
git add src/infrastructure/visualization/plotter.py
git commit -m "feat: enhance plotter with benchmark overlay, drawdown panel, and metrics printout"
```

---

### Task 26: backtest.yaml 配置更新

**Files:**
- Modify: `resources/backtest.yaml`

- [ ] **Step 1: 更新配置**

```yaml
backtest:
  symbols:
    - "000852.SH"
  start_date: "2016-01-01"
  end_date: "2026-04-29"
  base_timeframe: "1d"
  initial_capital: 1000000.0
  plot: true
  benchmark: "000852.SH"

strategy:
  name: "MicroValueStrategy"
  top_n: 9

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

costs:
  commission_rate: 0.0002
  tax_rate: 0.001
  min_commission: 5.0
  slippage: 0.003

data:
  cache_dir: "data/"
  history_fetcher: "TushareHistoryDataFetcher"
  tushare:
    token: "bd02c391c531732dc221165af820ea5fec582e4251cdf70115ed264d"
```

- [ ] **Step 2: 提交**

```bash
git add resources/backtest.yaml
git commit -m "feat: update backtest.yaml for MicroValueStrategy with risk and cost config"
```

---

### Task 27: 全链路集成测试

**Files:**
- Create: `tests/infrastructure/mock/test_micro_value_integration.py`

- [ ] **Step 1: 编写集成测试（使用 Mock 数据，不依赖 Tushare）**

```python
# tests/infrastructure/mock/test_micro_value_integration.py
from datetime import datetime, timedelta
from src.application.backtest_app import BacktestAppService
from src.domain.strategy.services.strategies.micro_value_strategy import MicroValueStrategy
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
from src.domain.market.services.fundamental_registry import FundamentalRegistry

def _make_bar(symbol, dt, close, volume=1e6, prev_close=None):
    return Bar(
        symbol=symbol, timeframe=Timeframe.DAY_1, timestamp=dt,
        open=close * 0.99, high=close * 1.02, low=close * 0.98, close=close,
        volume=volume, prev_close=prev_close or close * 0.99,
    )

class TestMicroValueIntegration:
    def test_basic_backtest_run_with_mock_data(self):
        # Arrange: 10 stocks, 30 trading days
        symbols = [f"00000{i}.SZ" for i in range(1, 10)]
        start = datetime(2024, 6, 1)
        dates = [start + timedelta(days=i) for i in range(30)]

        market = MockMarketGateway()
        trade = MockTradeGateway(initial_capital=1_000_000)
        strategy = MicroValueStrategy(top_n=3)
        evaluator = PerformanceEvaluator()
        sizer = EqualWeightSizer(n_symbols=3)

        # Load mock bars
        for sym in symbols:
            bars = [_make_bar(sym, d, 10.0 + 0.1 * i + hash(sym) % 3) for i, d in enumerate(dates)]
            market.load_bars(bars)

        # Build FundamentalRegistry with mock data
        registry = FundamentalRegistry()
        for sym in symbols:
            for d in dates:
                registry.add(FundamentalSnapshot(
                    symbol=sym, date=d, name=f"Stock {sym}",
                    list_date=datetime(2000, 1, 1), market_cap=1e9 + hash(sym) % 10 * 1e8,
                    roe_ttm=0.10 + hash(sym) % 10 * 0.02,
                    ocf_ttm=1e8 + hash(sym) % 10 * 1e7,
                ))

        app = BacktestAppService(
            market_gateway=market, trade_gateway=trade,
            strategy=strategy, evaluator=evaluator, sizer=sizer,
        )
        app.fundamental_registry = registry

        # Act
        reports = app.run_backtest(
            symbols=symbols, start_date=dates[0], end_date=dates[-1],
            base_timeframe=Timeframe.DAY_1, plot=False,
        )

        # Assert
        assert len(reports) == 1
        report = reports[0]
        assert report.initial_capital == 1_000_000
        assert report.trade_count >= 0
        assert report.max_drawdown >= 0.0
        assert len(report.snapshots) > 0
        print(f"Total Return: {report.total_return:.2%}")
        print(f"Sharpe: {report.sharpe_ratio:.2f}")
        print(f"Trades: {report.trade_count}")
```

- [ ] **Step 2: 运行集成测试**

```bash
uv run python -m pytest tests/infrastructure/mock/test_micro_value_integration.py -v --ignore=tests/infrastructure/gateway/
```
Expected: PASS (verifies the full pipeline works end-to-end)

- [ ] **Step 3: 运行全部测试确认无回归**

```bash
uv run python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -v
```
Expected: all tests PASS

- [ ] **Step 4: 运行 lint**

```bash
uv run ruff check src/
```

- [ ] **Step 5: 提交**

```bash
git add tests/infrastructure/mock/test_micro_value_integration.py
git commit -m "test: add end-to-end integration test for MicroValueStrategy"
```

---

## 实现顺序总览

```
Sprint 1 (数据层):
  Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7

Sprint 2 (策略层):
  Task 8 → Task 9 → Task 10 → Task 11 → Task 12 → Task 13 → Task 14

Sprint 3 (组合层):
  Task 15 → Task 16 → Task 17

Sprint 4 (风控层):
  Task 18 → Task 19 → Task 20 → Task 21 → Task 22

Sprint 5 (应用层):
  Task 23 → Task 24 → Task 25 → Task 26 → Task 27
```

每 Sprint 内部有线性依赖（后续 Task 依赖前置的 Domain 类型），Sprint 之间也存在依赖（Sprint 2 依赖 Sprint 1 的类型，Sprint 5 依赖全部前序 Sprint）。

## 运行验证

```bash
# 全部测试
uv run python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -v

# Lint
uv run ruff check src/

# 回测执行
uv run python -m src.interfaces.cli.run_backtest
```
