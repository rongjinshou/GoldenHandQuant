# 多因子选股策略 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现多因子选股策略，支持因子注册、百分位打分、加权合成选股。

**Architecture:** Domain 层新增 Factor Protocol + FactorScorer + 4 个因子实现 + MultiFactorStrategy。扩展 FundamentalSnapshot 和 StockSnapshot 数据模型。复用现有 CrossSectionalStrategy 框架和 StrategyRegistry。

**Tech Stack:** Python 3.13+, pytest, ruff, dataclasses

**Spec:** `docs/feat/0510-multi-factor-strategy/2026-05-10-multi-factor-strategy-design.md`

---

## 文件结构总览

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/domain/strategy/factors/__init__.py` | 包初始化 |
| `src/domain/strategy/factors/base.py` | Factor Protocol + FactorScorer |
| `src/domain/strategy/factors/value_factor.py` | 价值因子（PB, PE） |
| `src/domain/strategy/factors/quality_factor.py` | 质量因子（ROE） |
| `src/domain/strategy/factors/reversal_factor.py` | 反转因子（20d return） |
| `src/domain/strategy/factors/low_volatility_factor.py` | 低波动因子（波动率） |
| `src/domain/strategy/services/strategies/multi_factor_strategy.py` | 多因子策略 |
| `tests/domain/strategy/factors/__init__.py` | 测试包初始化 |
| `tests/domain/strategy/factors/test_base.py` | FactorScorer 测试 |
| `tests/domain/strategy/factors/test_value_factor.py` | 价值因子测试 |
| `tests/domain/strategy/factors/test_quality_factor.py` | 质量因子测试 |
| `tests/domain/strategy/factors/test_reversal_factor.py` | 反转因子测试 |
| `tests/domain/strategy/factors/test_low_volatility_factor.py` | 低波动因子测试 |
| `tests/domain/strategy/test_multi_factor_strategy.py` | 多因子策略集成测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/domain/market/value_objects/fundamental_snapshot.py` | 新增 pe_ratio, pb_ratio |
| `src/domain/market/value_objects/stock_snapshot.py` | 新增 pe_ratio, pb_ratio, return_20d, volatility_20d, turnover_rate |
| `src/domain/strategy/registry.py` | 注册 multi_factor 策略 |
| `src/infrastructure/gateway/tushare_fundamental_fetcher.py` | 读取 pe_ttm, pb 字段 |

---

## Task 1: 扩展数据模型

**Files:**
- Modify: `src/domain/market/value_objects/fundamental_snapshot.py`
- Modify: `src/domain/market/value_objects/stock_snapshot.py`

- [ ] **Step 1: 扩展 FundamentalSnapshot**

新增两个可选字段：

```python
@dataclass(slots=True, kw_only=True)
class FundamentalSnapshot:
    # ... 现有字段 ...
    pe_ratio: float | None = None  # 市盈率 (TTM)
    pb_ratio: float | None = None  # 市净率
```

- [ ] **Step 2: 扩展 StockSnapshot**

新增 5 个可选字段：

```python
@dataclass(slots=True, kw_only=True)
class StockSnapshot:
    # ... 现有字段 ...
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    return_20d: float | None = None       # 20 日收益率
    volatility_20d: float | None = None   # 20 日波动率
    turnover_rate: float | None = None    # 换手率
```

- [ ] **Step 3: 运行现有测试确认不破坏**

```bash
python -m pytest tests/domain/market/ -v
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q
```

- [ ] **Step 4: 提交**

```bash
git add src/domain/market/value_objects/fundamental_snapshot.py src/domain/market/value_objects/stock_snapshot.py
git commit -m "feat: 扩展 FundamentalSnapshot 和 StockSnapshot 数据模型"
```

---

## Task 2: FactorScorer 基础框架

**Files:**
- Create: `src/domain/strategy/factors/__init__.py`
- Create: `src/domain/strategy/factors/base.py`
- Create: `tests/domain/strategy/factors/__init__.py`
- Create: `tests/domain/strategy/factors/test_base.py`

- [ ] **Step 1: 编写 FactorScorer 测试**

```python
# tests/domain/strategy/factors/test_base.py
from src.domain.strategy.factors.base import FactorScorer


class TestFactorScorer:
    def test_percentile_rank_basic(self):
        raw = {"A": 10.0, "B": 20.0, "C": 30.0, "D": 40.0}
        scores = FactorScorer.percentile_rank(raw)
        assert scores["A"] == 0.0    # 最小值 → 0
        assert scores["D"] == 1.0    # 最大值 → 1
        assert 0.0 < scores["B"] < 1.0

    def test_percentile_rank_same_values(self):
        raw = {"A": 10.0, "B": 10.0, "C": 10.0}
        scores = FactorScorer.percentile_rank(raw)
        # 所有相同值 → 都应该是 0.5
        for v in scores.values():
            assert v == 0.5

    def test_percentile_rank_single(self):
        raw = {"A": 42.0}
        scores = FactorScorer.percentile_rank(raw)
        assert scores["A"] == 0.5

    def test_percentile_rank_empty(self):
        scores = FactorScorer.percentile_rank({})
        assert scores == {}

    def test_percentile_rank_inverted(self):
        """低值高分（用于价值因子，低 PE 更好）。"""
        raw = {"A": 10.0, "B": 20.0, "C": 30.0}
        scores = FactorScorer.percentile_rank(raw, invert=True)
        assert scores["A"] == 1.0   # 最小值 → 最高分
        assert scores["C"] == 0.0   # 最大值 → 最低分

    def test_weighted_combine(self):
        scores_a = {"A": 0.8, "B": 0.4, "C": 0.6}
        scores_b = {"A": 0.2, "B": 0.6, "C": 0.4}
        combined = FactorScorer.weighted_combine(
            [scores_a, scores_b], [0.6, 0.4]
        )
        assert abs(combined["A"] - 0.56) < 1e-6   # 0.8*0.6 + 0.2*0.4
        assert abs(combined["B"] - 0.48) < 1e-6   # 0.4*0.6 + 0.6*0.4
        assert abs(combined["C"] - 0.52) < 1e-6   # 0.6*0.6 + 0.4*0.4

    def test_weighted_combine_empty(self):
        combined = FactorScorer.weighted_combine([], [])
        assert combined == {}

    def test_weighted_combine_missing_symbol(self):
        """某因子缺少某只股票时，该股票不参与合成。"""
        scores_a = {"A": 0.8, "B": 0.4}
        scores_b = {"A": 0.6}  # B 缺失
        combined = FactorScorer.weighted_combine(
            [scores_a, scores_b], [0.5, 0.5]
        )
        assert "A" in combined
        assert "B" not in combined

    def test_rank_top_n(self):
        scores = {"A": 0.9, "B": 0.3, "C": 0.7, "D": 0.5, "E": 0.1}
        top = FactorScorer.rank_top_n(scores, 3)
        assert top == ["A", "C", "D"]

    def test_rank_top_n_more_than_available(self):
        scores = {"A": 0.5, "B": 0.3}
        top = FactorScorer.rank_top_n(scores, 10)
        assert top == ["A", "B"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/domain/strategy/factors/test_base.py -v
```

- [ ] **Step 3: 实现 FactorScorer**

```python
# src/domain/strategy/factors/base.py
from typing import Protocol

from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class Factor(Protocol):
    """因子接口。"""
    name: str

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        """计算每只股票的因子原始值。"""
        ...


class FactorScorer:
    """因子打分器：百分位排名 + 加权合成。"""

    @staticmethod
    def percentile_rank(
        raw_values: dict[str, float],
        invert: bool = False,
    ) -> dict[str, float]:
        """将原始值转换为百分位分数 [0, 1]。

        Args:
            raw_values: {symbol: raw_value}
            invert: True 时低值得高分（用于价值因子）
        """
        if not raw_values:
            return {}

        items = sorted(raw_values.items(), key=lambda x: x[1])
        n = len(items)

        if n == 1:
            return {items[0][0]: 0.5}

        scores: dict[str, float] = {}
        for rank, (symbol, _) in enumerate(items):
            score = rank / (n - 1)
            scores[symbol] = (1.0 - score) if invert else score

        return scores

    @staticmethod
    def weighted_combine(
        factor_scores: list[dict[str, float]],
        weights: list[float],
    ) -> dict[str, float]:
        """加权合成多个因子的分数。

        只有所有因子都有分数的股票才参与合成。
        """
        if not factor_scores:
            return {}

        # 取所有因子都有的 symbol 交集
        common = set(factor_scores[0].keys())
        for scores in factor_scores[1:]:
            common &= set(scores.keys())

        combined: dict[str, float] = {}
        for symbol in common:
            total = sum(
                scores[symbol] * w
                for scores, w in zip(factor_scores, weights)
            )
            combined[symbol] = total

        return combined

    @staticmethod
    def rank_top_n(
        scores: dict[str, float],
        n: int,
    ) -> list[str]:
        """按分数降序排列，返回前 N 个 symbol。"""
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [symbol for symbol, _ in sorted_items[:n]]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/domain/strategy/factors/test_base.py -v
```

- [ ] **Step 5: 运行 lint**

```bash
ruff check src/domain/strategy/factors/base.py tests/domain/strategy/factors/test_base.py
```

- [ ] **Step 6: 提交**

```bash
git add src/domain/strategy/factors/ tests/domain/strategy/factors/
git commit -m "feat: 新增 Factor Protocol 和 FactorScorer 基础框架"
```

---

## Task 3: 价值因子 + 质量因子

**Files:**
- Create: `src/domain/strategy/factors/value_factor.py`
- Create: `src/domain/strategy/factors/quality_factor.py`
- Create: `tests/domain/strategy/factors/test_value_factor.py`
- Create: `tests/domain/strategy/factors/test_quality_factor.py`

- [ ] **Step 1: 编写价值因子测试**

```python
# tests/domain/strategy/factors/test_value_factor.py
from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.value_factor import PBValueFactor, PEValueFactor


def _make_snapshot(symbol: str, pb: float | None = None, pe: float | None = None) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name="test", list_date=datetime(2020, 1, 1),
        market_cap=1e10, pb_ratio=pb, pe_ratio=pe,
    )


class TestPBValueFactor:
    def test_compute_returns_raw_pb_values(self):
        factor = PBValueFactor()
        snapshots = [
            _make_snapshot("A", pb=1.0),
            _make_snapshot("B", pb=3.0),
            _make_snapshot("C", pb=2.0),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 1.0
        assert raw["B"] == 3.0
        assert raw["C"] == 2.0

    def test_compute_skips_none_pb(self):
        factor = PBValueFactor()
        snapshots = [
            _make_snapshot("A", pb=1.0),
            _make_snapshot("B", pb=None),
        ]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw

    def test_compute_empty(self):
        factor = PBValueFactor()
        assert factor.compute([]) == {}


class TestPEValueFactor:
    def test_compute_returns_raw_pe_values(self):
        factor = PEValueFactor()
        snapshots = [
            _make_snapshot("A", pe=10.0),
            _make_snapshot("B", pe=30.0),
            _make_snapshot("C", pe=20.0),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 10.0
        assert raw["B"] == 30.0

    def test_compute_skips_negative_pe(self):
        """负 PE（亏损股）应被排除。"""
        factor = PEValueFactor()
        snapshots = [
            _make_snapshot("A", pe=10.0),
            _make_snapshot("B", pe=-5.0),
        ]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现价值因子**

```python
# src/domain/strategy/factors/value_factor.py
from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class PBValueFactor:
    """市净率价值因子 — 低 PB 得高分。"""
    name = "pb_value"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.pb_ratio
            for s in snapshots
            if s.pb_ratio is not None and s.pb_ratio > 0
        }


class PEValueFactor:
    """市盈率价值因子 — 低 PE 得高分。"""
    name = "pe_value"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.pe_ratio
            for s in snapshots
            if s.pe_ratio is not None and s.pe_ratio > 0
        }
```

- [ ] **Step 4: 运行测试确认通过**

- [ ] **Step 5: 编写质量因子测试**

```python
# tests/domain/strategy/factors/test_quality_factor.py
from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.quality_factor import ROEQualityFactor


def _make_snapshot(symbol: str, roe: float | None = None) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name="test", list_date=datetime(2020, 1, 1),
        market_cap=1e10, roe_ttm=roe,
    )


class TestROEQualityFactor:
    def test_compute_returns_raw_roe(self):
        factor = ROEQualityFactor()
        snapshots = [
            _make_snapshot("A", roe=0.15),
            _make_snapshot("B", roe=0.08),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.15
        assert raw["B"] == 0.08

    def test_compute_skips_none_roe(self):
        factor = ROEQualityFactor()
        snapshots = [
            _make_snapshot("A", roe=0.15),
            _make_snapshot("B", roe=None),
        ]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw

    def test_compute_skips_negative_roe(self):
        factor = ROEQualityFactor()
        snapshots = [_make_snapshot("A", roe=-0.05)]
        raw = factor.compute(snapshots)
        assert "A" not in raw
```

- [ ] **Step 6: 实现质量因子**

```python
# src/domain/strategy/factors/quality_factor.py
from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class ROEQualityFactor:
    """ROE 质量因子 — 高 ROE 得高分。"""
    name = "roe_quality"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.roe_ttm
            for s in snapshots
            if s.roe_ttm is not None and s.roe_ttm > 0
        }
```

- [ ] **Step 7: 运行全部因子测试 + lint + 提交**

```bash
python -m pytest tests/domain/strategy/factors/ -v
ruff check src/domain/strategy/factors/ tests/domain/strategy/factors/
git add src/domain/strategy/factors/ tests/domain/strategy/factors/
git commit -m "feat: 新增价值因子和质量因子"
```

---

## Task 4: 反转因子 + 低波动因子

**Files:**
- Create: `src/domain/strategy/factors/reversal_factor.py`
- Create: `src/domain/strategy/factors/low_volatility_factor.py`
- Create: `tests/domain/strategy/factors/test_reversal_factor.py`
- Create: `tests/domain/strategy/factors/test_low_volatility_factor.py`

- [ ] **Step 1: 编写反转因子测试**

```python
# tests/domain/strategy/factors/test_reversal_factor.py
from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.reversal_factor import ReversalFactor


def _make_snapshot(symbol: str, return_20d: float | None = None) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name="test", list_date=datetime(2020, 1, 1),
        market_cap=1e10, return_20d=return_20d,
    )


class TestReversalFactor:
    def test_compute_returns_raw_return(self):
        factor = ReversalFactor()
        snapshots = [
            _make_snapshot("A", return_20d=0.10),
            _make_snapshot("B", return_20d=-0.05),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.10
        assert raw["B"] == -0.05

    def test_compute_skips_none(self):
        factor = ReversalFactor()
        snapshots = [_make_snapshot("A", return_20d=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw
```

- [ ] **Step 2: 实现反转因子**

```python
# src/domain/strategy/factors/reversal_factor.py
from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class ReversalFactor:
    """20 日反转因子 — 涨幅越小/负，分数越高（A 股反转效应）。"""
    name = "reversal_20d"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.return_20d
            for s in snapshots
            if s.return_20d is not None
        }
```

- [ ] **Step 3: 编写低波动因子测试**

```python
# tests/domain/strategy/factors/test_low_volatility_factor.py
from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.low_volatility_factor import LowVolatilityFactor


def _make_snapshot(symbol: str, vol: float | None = None) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name="test", list_date=datetime(2020, 1, 1),
        market_cap=1e10, volatility_20d=vol,
    )


class TestLowVolatilityFactor:
    def test_compute_returns_raw_volatility(self):
        factor = LowVolatilityFactor()
        snapshots = [
            _make_snapshot("A", vol=0.02),
            _make_snapshot("B", vol=0.05),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.02
        assert raw["B"] == 0.05

    def test_compute_skips_none(self):
        factor = LowVolatilityFactor()
        snapshots = [_make_snapshot("A", vol=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw
```

- [ ] **Step 4: 实现低波动因子**

```python
# src/domain/strategy/factors/low_volatility_factor.py
from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class LowVolatilityFactor:
    """20 日低波动因子 — 波动率越低，分数越高。"""
    name = "low_volatility_20d"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.volatility_20d
            for s in snapshots
            if s.volatility_20d is not None
        }
```

- [ ] **Step 5: 运行全部因子测试 + lint + 提交**

```bash
python -m pytest tests/domain/strategy/factors/ -v
ruff check src/domain/strategy/factors/ tests/domain/strategy/factors/
git add src/domain/strategy/factors/
git commit -m "feat: 新增反转因子和低波动因子"
```

---

## Task 5: MultiFactorStrategy 策略实现

**Files:**
- Create: `src/domain/strategy/services/strategies/multi_factor_strategy.py`
- Create: `tests/domain/strategy/test_multi_factor_strategy.py`

- [ ] **Step 1: 编写策略测试**

```python
# tests/domain/strategy/test_multi_factor_strategy.py
from datetime import datetime

from src.domain.account.entities.position import Position
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.value_factor import PBValueFactor
from src.domain.strategy.factors.quality_factor import ROEQualityFactor
from src.domain.strategy.services.strategies.multi_factor_strategy import MultiFactorStrategy
from src.domain.strategy.value_objects.signal_direction import SignalDirection


def _make_snapshot(symbol: str, pb: float, roe: float) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 6, 15),
        open=10, high=10, low=10, close=10, volume=1000,
        name=f"stock_{symbol}", list_date=datetime(2020, 1, 1),
        market_cap=1e10, pb_ratio=pb, roe_ttm=roe,
    )


class TestMultiFactorStrategy:
    def test_generate_signals_selects_top_n(self):
        strategy = MultiFactorStrategy(
            factors=[PBValueFactor(), ROEQualityFactor()],
            weights=[0.5, 0.5],
            top_n=2,
        )
        universe = [
            _make_snapshot("A", pb=1.0, roe=0.20),  # 低PB + 高ROE → 最好
            _make_snapshot("B", pb=2.0, roe=0.15),
            _make_snapshot("C", pb=5.0, roe=0.05),  # 高PB + 低ROE → 最差
        ]

        signals = strategy.generate_cross_sectional_signals(
            universe=universe,
            current_positions=[],
            current_date=datetime(2024, 6, 15),
        )

        # 应该选出 top_n=2 只（A 和 B）
        assert len(signals) == 2
        symbols = {s.symbol for s in signals}
        assert "A" in symbols
        assert "B" in symbols
        for s in signals:
            assert s.direction == SignalDirection.BUY
            assert s.strategy_name == "MultiFactorStrategy"

    def test_generate_signals_sells_dropped_positions(self):
        strategy = MultiFactorStrategy(
            factors=[PBValueFactor()],
            weights=[1.0],
            top_n=2,
        )
        universe = [
            _make_snapshot("A", pb=1.0, roe=0.15),
            _make_snapshot("B", pb=2.0, roe=0.15),
            _make_snapshot("C", pb=3.0, roe=0.15),
        ]
        # 当前持有 A 和 C，但只有 A 在 top_n 中
        positions = [
            Position(account_id="acc", ticker="A", total_volume=100, available_volume=100),
            Position(account_id="acc", ticker="C", total_volume=100, available_volume=100),
        ]

        signals = strategy.generate_cross_sectional_signals(
            universe=universe,
            current_positions=positions,
            current_date=datetime(2024, 6, 15),
        )

        buy_symbols = {s.symbol for s in signals if s.direction == SignalDirection.BUY}
        sell_symbols = {s.symbol for s in signals if s.direction == SignalDirection.SELL}
        assert "A" in buy_symbols or "B" in buy_symbols
        assert "C" in sell_symbols  # C 不在 top_n，应卖出

    def test_generate_signals_empty_universe(self):
        strategy = MultiFactorStrategy(factors=[PBValueFactor()], weights=[1.0], top_n=5)
        signals = strategy.generate_cross_sectional_signals(
            universe=[], current_positions=[], current_date=datetime(2024, 6, 15),
        )
        assert signals == []

    def test_name_property(self):
        strategy = MultiFactorStrategy(factors=[], weights=[], top_n=5)
        assert strategy.name == "MultiFactorStrategy"
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 MultiFactorStrategy**

```python
# src/domain/strategy/services/strategies/multi_factor_strategy.py
import logging
from datetime import datetime

from src.domain.account.entities.position import Position
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.base import Factor, FactorScorer
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection

logger = logging.getLogger(__name__)


class MultiFactorStrategy(CrossSectionalStrategy):
    """多因子选股策略。

    对全市场股票按多个因子打分，加权合成后选 top_n 买入。
    已持有但不在 top_n 中的标的生成卖出信号。
    """

    def __init__(
        self,
        factors: list[Factor],
        weights: list[float],
        top_n: int = 10,
    ) -> None:
        self._factors = factors
        self._weights = weights
        self._top_n = top_n

    @property
    def name(self) -> str:
        return "MultiFactorStrategy"

    def generate_cross_sectional_signals(
        self,
        universe: list[StockSnapshot],
        current_positions: list[Position],
        current_date: datetime,
    ) -> list[Signal]:
        if not universe or not self._factors:
            return []

        # 1. 对每个因子计算原始值 → 百分位分数
        all_scores: list[dict[str, float]] = []
        for factor in self._factors:
            raw = factor.compute(universe)
            if not raw:
                logger.warning("因子 %s 无有效数据", factor.name)
                continue
            scores = FactorScorer.percentile_rank(
                raw,
                invert=(factor.name in ("pb_value", "pe_value", "reversal_20d", "low_volatility_20d")),
            )
            all_scores.append(scores)

        if not all_scores:
            return []

        # 2. 加权合成
        combined = FactorScorer.weighted_combine(all_scores, self._weights)
        if not combined:
            return []

        # 3. 排名选股
        top_symbols = FactorScorer.rank_top_n(combined, self._top_n)
        top_set = set(top_symbols)

        # 4. 生成信号
        signals: list[Signal] = []

        # BUY: 在 top_n 中的
        price_map = {s.symbol: s.close for s in universe}
        for symbol in top_symbols:
            signals.append(Signal(
                symbol=symbol,
                direction=SignalDirection.BUY,
                confidence_score=combined.get(symbol, 0.0),
                strategy_name=self.name,
                reason=f"MultiFactor rank #{top_symbols.index(symbol)+1}, score={combined.get(symbol, 0):.3f}",
            ))

        # SELL: 已持有但不在 top_n 中的
        for pos in current_positions:
            if pos.ticker not in top_set:
                signals.append(Signal(
                    symbol=pos.ticker,
                    direction=SignalDirection.SELL,
                    confidence_score=0.0,
                    strategy_name=self.name,
                    reason="Dropped from multi-factor top_n",
                ))

        return signals
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/domain/strategy/test_multi_factor_strategy.py -v
```

- [ ] **Step 5: 运行 lint**

```bash
ruff check src/domain/strategy/services/strategies/multi_factor_strategy.py
```

- [ ] **Step 6: 提交**

```bash
git add src/domain/strategy/services/strategies/multi_factor_strategy.py tests/domain/strategy/test_multi_factor_strategy.py
git commit -m "feat: 新增多因子选股策略 (MultiFactorStrategy)"
```

---

## Task 6: 注册表 + 配置集成

**Files:**
- Modify: `src/domain/strategy/registry.py`
- Modify: `src/infrastructure/gateway/tushare_fundamental_fetcher.py`

- [ ] **Step 1: 注册 multi_factor 策略**

在 `registry.py` 中添加：

```python
def _build_multi_factor(params: dict[str, Any]) -> BaseStrategy:
    from src.domain.strategy.factors.value_factor import PBValueFactor, PEValueFactor
    from src.domain.strategy.factors.quality_factor import ROEQualityFactor
    from src.domain.strategy.factors.reversal_factor import ReversalFactor
    from src.domain.strategy.factors.low_volatility_factor import LowVolatilityFactor
    from src.domain.strategy.services.strategies.multi_factor_strategy import MultiFactorStrategy

    weights_dict = params.get("weights", {})
    factors = []
    weights = []

    factor_map = {
        "pb_value": PBValueFactor(),
        "pe_value": PEValueFactor(),
        "quality": ROEQualityFactor(),
        "reversal": ReversalFactor(),
        "low_volatility": LowVolatilityFactor(),
    }

    for name, weight in weights_dict.items():
        if name in factor_map:
            factors.append(factor_map[name])
            weights.append(weight)

    if not factors:
        factors = [PBValueFactor(), ROEQualityFactor()]
        weights = [0.5, 0.5]

    return MultiFactorStrategy(
        factors=factors,
        weights=weights,
        top_n=params.get("top_n", 10),
    )


_register(StrategyConfig(
    name="multi_factor",
    factory=_build_multi_factor,
    strategy_type="cross_section",
    description="多因子选股策略 (价值+质量+反转+低波动)",
    default_params={
        "top_n": 10,
        "weights": {
            "pb_value": 0.25,
            "quality": 0.25,
            "reversal": 0.25,
            "low_volatility": 0.25,
        },
    },
))
```

- [ ] **Step 2: 扩展 TushareFundamentalFetcher 读取 PE/PB**

在 `tushare_fundamental_fetcher.py` 的快照构建中添加 `pe_ttm` 和 `pb` 字段的读取。

- [ ] **Step 3: 运行注册表测试**

```bash
python -m pytest tests/domain/strategy/test_registry.py -v
```

- [ ] **Step 4: 运行全量测试**

```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q
```

- [ ] **Step 5: 提交**

```bash
git add src/domain/strategy/registry.py src/infrastructure/gateway/tushare_fundamental_fetcher.py
git commit -m "feat: 注册多因子策略并扩展基本面数据获取"
```

---

## Task 7: 集成验证

- [ ] **Step 1: 运行全部测试**

```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -v
```

- [ ] **Step 2: 运行 ruff lint**

```bash
ruff check src/
```

- [ ] **Step 3: 验证策略注册**

```bash
python -c "from src.domain.strategy.registry import list_strategies; [print(f'{s.name}: {s.description}') for s in list_strategies()]"
```

Expected: 包含 multi_factor 策略

- [ ] **Step 4: 提交最终变更**

```bash
git add -A && git commit -m "feat: 多因子选股策略完整实现"
```
