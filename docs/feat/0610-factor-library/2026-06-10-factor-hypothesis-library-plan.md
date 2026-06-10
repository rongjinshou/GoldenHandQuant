# Factor Hypothesis Library — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `quant factor-test` CLI to `FactorTestRunner` engine, enabling end-to-end factor hypothesis validation with batch testing, sample split, and hard threshold judgment.

**Architecture:** A new `FactorTestAppService` (application layer) orchestrates data loading → snapshot construction → batch factor testing → verdict judgment. The CLI command delegates to this service. Data loading reuses the existing `IHistoryDataFetcher` + `FundamentalRegistry` + `CrossSectionBuilder` pipeline already proven in backtesting.

**Tech Stack:** Python 3.13, existing `FactorTestRunner`, `CrossSectionBuilder`, `MockMarketGateway`, `FundamentalRegistry`, argparse CLI.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/application/factor_test_app.py` | **Create** | FactorTestAppService: data prep + batch run + verdict |
| `src/interfaces/cli/commands/factor_test.py` | **Modify** | Wire CLI args to FactorTestAppService |
| `src/interfaces/cli/quant.py` | **Modify** | Add `--split-date`, `--num-layers`, `--output` args |
| `tests/application/test_factor_test_app.py` | **Create** | Unit tests for FactorTestAppService |
| `tests/interfaces/cli/test_factor_test_cli.py` | **Create** | Integration test for CLI wiring |

---

### Task 1: Define Factor Catalog and Verdict Logic (Domain Layer)

**Files:**
- Create: `src/domain/strategy/factor_test/factor_catalog.py`
- Create: `src/domain/strategy/factor_test/verdict.py`
- Create: `tests/domain/strategy/factor_test/test_verdict.py`

- [ ] **Step 1: Write the FactorCatalog dataclass**

```python
# src/domain/strategy/factor_test/factor_catalog.py
"""因子假设库 — P0/P1/P2 因子定义。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorHypothesis:
    """单条因子假设。"""
    factor_id: str          # e.g. "F01"
    name: str               # e.g. "小市值"
    category: str           # e.g. "规模"
    expression: str         # DSL expression, e.g. "0 - log(market_cap)"
    direction_note: str     # e.g. "高=小盘=预期跑赢"
    evidence_strength: str  # "强" | "中强" | "中" | "弱"
    field_ready: bool       # True if StockSnapshot field is populated
    priority: str           # "P0" | "P1" | "P2"


# P0 因子: 字段已就绪 · 证据强 · 个人优势区
P0_FACTORS: list[FactorHypothesis] = [
    FactorHypothesis(
        factor_id="F01", name="小市值", category="规模",
        expression="0 - log(market_cap)",
        direction_note="高=小盘=预期跑赢；raw log(market_cap) IC为负",
        evidence_strength="强", field_ready=True, priority="P0",
    ),
    FactorHypothesis(
        factor_id="F02", name="短期反转", category="量价",
        expression="0 - return_20d",
        direction_note="高=过去跌得多=预期反弹；raw return_20d IC为负",
        evidence_strength="强", field_ready=True, priority="P0",
    ),
    FactorHypothesis(
        factor_id="F03", name="换手率", category="流动性/情绪",
        expression="0 - avg_turnover_20d",
        direction_note="高=低换手=预期跑赢；raw换手IC为负",
        evidence_strength="强", field_ready=True, priority="P0",
    ),
    FactorHypothesis(
        factor_id="F04", name="低波动", category="风险",
        expression="0 - volatility_20d",
        direction_note="高=低波=预期跑赢；raw波动IC为负",
        evidence_strength="中强", field_ready=True, priority="P0",
    ),
    FactorHypothesis(
        factor_id="F05", name="抗博彩/低偏度", category="行为",
        expression="0 - skewness_20d",
        direction_note="高=低偏度=预期跑赢；raw偏度IC为负",
        evidence_strength="中", field_ready=True, priority="P0",
    ),
]

# P1 因子: 证据中 / 需补一步
P1_FACTORS: list[FactorHypothesis] = [
    FactorHypothesis(
        factor_id="F06", name="Amihud非流动性", category="流动性",
        expression="illiquidity_20d",
        direction_note="高=非流动性高=预期跑赢(流动性溢价)",
        evidence_strength="中", field_ready=True, priority="P1",
    ),
    FactorHypothesis(
        factor_id="F07", name="BP账面市值比", category="价值",
        expression="1 / pb_ratio",
        direction_note="高BP=便宜=预期跑赢；剔除PB<=0",
        evidence_strength="中", field_ready=True, priority="P1",
    ),
    FactorHypothesis(
        factor_id="F08", name="EP盈利市值比", category="价值",
        expression="1 / pe_ratio",
        direction_note="高EP=便宜=预期跑赢；处理PE<0",
        evidence_strength="中", field_ready=True, priority="P1",
    ),
    FactorHypothesis(
        factor_id="F09", name="ROE质量", category="质量",
        expression="roe_ttm",
        direction_note="高ROE=高质量=预期跑赢",
        evidence_strength="中", field_ready=True, priority="P1",
    ),
    FactorHypothesis(
        factor_id="F10", name="毛利率", category="质量",
        expression="gross_margin",
        direction_note="高毛利率=预期跑赢(Novy-Marx)",
        evidence_strength="中", field_ready=True, priority="P1",
    ),
]

# P2 因子: 对照 / 备选
P2_FACTORS: list[FactorHypothesis] = [
    FactorHypothesis(
        factor_id="F11", name="中期动量(对照)", category="量价",
        expression="return_60d",
        direction_note="A股动量弱/不稳，作反转对照",
        evidence_strength="弱", field_ready=True, priority="P2",
    ),
]

ALL_FACTORS: list[FactorHypothesis] = P0_FACTORS + P1_FACTORS + P2_FACTORS

FACTOR_BY_ID: dict[str, FactorHypothesis] = {f.factor_id: f for f in ALL_FACTORS}
FACTOR_BY_NAME: dict[str, FactorHypothesis] = {f.name: f for f in ALL_FACTORS}


def resolve_factors(factor_str: str) -> list[FactorHypothesis]:
    """解析逗号分隔的因子标识符( ID 或名称)，返回 FactorHypothesis 列表。

    支持:
      - "F01,F02,F03"  (ID)
      - "小市值,短期反转"  (名称)
      - "P0"  (优先级组)
      - "all"  (全部)
    """
    if factor_str.strip().lower() == "all":
        return list(ALL_FACTORS)
    if factor_str.strip().upper() in ("P0", "P1", "P2"):
        priority = factor_str.strip().upper()
        return [f for f in ALL_FACTORS if f.priority == priority]

    results: list[FactorHypothesis] = []
    for token in factor_str.split(","):
        token = token.strip()
        if not token:
            continue
        # Try ID first
        f = FACTOR_BY_ID.get(token.upper())
        if f is None:
            # Try name
            f = FACTOR_BY_NAME.get(token)
        if f is None:
            raise ValueError(f"Unknown factor: {token!r}. Use factor ID (F01) or name (小市值).")
        results.append(f)
    return results
```

- [ ] **Step 2: Write the FactorVerdict dataclass and judgment logic**

```python
# src/domain/strategy/factor_test/verdict.py
"""因子验证判决 — 硬门槛判定(§7)。"""

from dataclasses import dataclass

from src.domain.strategy.factor_test.report import ScoredFactorTestReport


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorVerdict:
    """单因子判决结果。"""
    factor_id: str
    factor_name: str
    expression: str
    # In-sample metrics
    ic_mean: float
    ir: float
    ic_positive_rate: float
    monotonicity_score: float
    long_short_return: float
    score: float
    grade: str
    # Out-of-sample metrics (empty dict if no split)
    oos_ic_mean: float = 0.0
    oos_ir: float = 0.0
    oos_long_short_return: float = 0.0
    # Verdict
    passed: bool = False
    reasons: list[str] = None     # why passed / failed

    def __post_init__(self):
        if self.reasons is None:
            object.__setattr__(self, "reasons", [])


# --- Hard thresholds from §7 ---
IC_MIN = 0.02
IR_MIN = 0.30
MONOTONICITY_MIN = 0.4       # moderate; design doc says "高"
LONG_SHORT_MIN = 0.0         # must be positive after costs
OOS_IC_SIGN_FLIP = False     # IC sign must not flip OOS


def judge_factor(
    report: ScoredFactorTestReport,
    oos_report: ScoredFactorTestReport | None = None,
    factor_id: str = "",
    factor_name: str = "",
) -> FactorVerdict:
    """Apply §7 hard thresholds to a factor test report.

    Args:
        report: In-sample scored report.
        oos_report: Out-of-sample scored report (None = no split).
        factor_id: Factor ID for labeling.
        factor_name: Factor name for labeling.

    Returns:
        FactorVerdict with pass/fail and reasons.
    """
    r = report.report
    reasons: list[str] = []
    passed = True

    # 1. IC 有效: |IC均值| >= 0.02, IR >= 0.3
    if abs(r.ic_mean) < IC_MIN:
        passed = False
        reasons.append(f"|IC|={abs(r.ic_mean):.4f} < {IC_MIN} (IC门槛)")
    else:
        reasons.append(f"|IC|={abs(r.ic_mean):.4f} >= {IC_MIN} ✓")

    if abs(r.ir) < IR_MIN:
        passed = False
        reasons.append(f"|IR|={abs(r.ir):.3f} < {IR_MIN} (IR门槛)")
    else:
        reasons.append(f"|IR|={abs(r.ir):.3f} >= {IR_MIN} ✓")

    # 2. IC 正率明显偏离 50%
    if r.ic_positive_rate < 0.52:
        passed = False
        reasons.append(f"IC正率={r.ic_positive_rate:.1%} < 52% (偏离不足)")
    else:
        reasons.append(f"IC正率={r.ic_positive_rate:.1%} ✓")

    # 3. 分层单调
    if r.monotonicity_score < MONOTONICITY_MIN:
        passed = False
        reasons.append(f"单调性={r.monotonicity_score:.2f} < {MONOTONICITY_MIN} (单调性不足)")
    else:
        reasons.append(f"单调性={r.monotonicity_score:.2f} ✓")

    # 4. 扣成本后多空为正
    if r.long_short_return <= LONG_SHORT_MIN:
        passed = False
        reasons.append(f"多空收益={r.long_short_return:.2%} <= 0 (扣成本后为负)")
    else:
        reasons.append(f"多空收益={r.long_short_return:.2%} > 0 ✓")

    # 5. 样本外一致性 (if available)
    oos_ic = 0.0
    oos_ir = 0.0
    oos_ls = 0.0
    if oos_report is not None:
        oos_r = oos_report.report
        oos_ic = oos_r.ic_mean
        oos_ir = oos_r.ir
        oos_ls = oos_r.long_short_return

        # IC 符号不翻转
        if (r.ic_mean > 0 and oos_r.ic_mean < 0) or (r.ic_mean < 0 and oos_r.ic_mean > 0):
            passed = False
            reasons.append(f"样本外IC符号翻转: IS={r.ic_mean:.4f} vs OOS={oos_r.ic_mean:.4f}")
        else:
            reasons.append(f"样本外IC符号一致: IS={r.ic_mean:.4f} vs OOS={oos_r.ic_mean:.4f} ✓")

        # OOS 多空仍为正
        if oos_r.long_short_return <= 0:
            passed = False
            reasons.append(f"样本外多空收益={oos_r.long_short_return:.2%} <= 0")
        else:
            reasons.append(f"样本外多空收益={oos_r.long_short_return:.2%} ✓")

    return FactorVerdict(
        factor_id=factor_id,
        factor_name=factor_name,
        expression=r.expression,
        ic_mean=r.ic_mean,
        ir=r.ir,
        ic_positive_rate=r.ic_positive_rate,
        monotonicity_score=r.monotonicity_score,
        long_short_return=r.long_short_return,
        score=report.score,
        grade=report.grade,
        oos_ic_mean=oos_ic,
        oos_ir=oos_ir,
        oos_long_short_return=oos_ls,
        passed=passed,
        reasons=reasons,
    )
```

- [ ] **Step 3: Write tests for verdict logic**

```python
# tests/domain/strategy/factor_test/test_verdict.py
"""Tests for factor verdict judgment logic."""

from src.domain.strategy.factor_test.report import FactorTestReport, ScoredFactorTestReport
from src.domain.strategy.factor_test.verdict import FactorVerdict, judge_factor


def _make_report(
    ic_mean: float = 0.04,
    ir: float = 0.5,
    ic_positive_rate: float = 0.6,
    monotonicity_score: float = 0.8,
    long_short_return: float = 0.1,
    expression: str = "0 - return_20d",
) -> ScoredFactorTestReport:
    r = FactorTestReport(
        expression=expression,
        test_period=("2021-01-01", "2025-12-31"),
        universe_count=3000,
        ic_mean=ic_mean,
        ic_std=abs(ic_mean / ir) if ir != 0 else 0.01,
        ir=ir,
        ic_positive_rate=ic_positive_rate,
        monotonicity_score=monotonicity_score,
        long_short_return=long_short_return,
    )
    return ScoredFactorTestReport(report=r, score=75.0, grade="B", grade_reasons=["test"])


class TestJudgeFactor:
    def test_all_pass(self):
        report = _make_report()
        verdict = judge_factor(report, factor_id="F02", factor_name="短期反转")
        assert verdict.passed is True
        assert len([r for r in verdict.reasons if "✓" in r]) >= 4

    def test_fail_low_ic(self):
        report = _make_report(ic_mean=0.005)
        verdict = judge_factor(report)
        assert verdict.passed is False
        assert any("IC" in r and "门槛" in r for r in verdict.reasons)

    def test_fail_low_ir(self):
        report = _make_report(ir=0.1)
        verdict = judge_factor(report)
        assert verdict.passed is False
        assert any("IR" in r and "门槛" in r for r in verdict.reasons)

    def test_fail_negative_long_short(self):
        report = _make_report(long_short_return=-0.05)
        verdict = judge_factor(report)
        assert verdict.passed is False
        assert any("多空" in r and "负" in r for r in verdict.reasons)

    def test_fail_low_monotonicity(self):
        report = _make_report(monotonicity_score=0.1)
        verdict = judge_factor(report)
        assert verdict.passed is False
        assert any("单调性" in r for r in verdict.reasons)

    def test_fail_ic_sign_flip_oos(self):
        is_report = _make_report(ic_mean=0.04)
        oos_report = _make_report(ic_mean=-0.03)
        verdict = judge_factor(is_report, oos_report=oos_report)
        assert verdict.passed is False
        assert any("翻转" in r for r in verdict.reasons)

    def test_pass_with_oos(self):
        is_report = _make_report(ic_mean=0.04, long_short_return=0.1)
        oos_report = _make_report(ic_mean=0.03, long_short_return=0.05)
        verdict = judge_factor(is_report, oos_report=oos_report)
        assert verdict.passed is True
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/domain/strategy/factor_test/test_verdict.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/domain/strategy/factor_test/factor_catalog.py src/domain/strategy/factor_test/verdict.py tests/domain/strategy/factor_test/test_verdict.py
git commit -m "feat: add factor catalog (P0/P1/P2) and verdict judgment logic (§7)"
```

---

### Task 2: Build FactorTestAppService (Application Layer)

**Files:**
- Create: `src/application/factor_test_app.py`
- Create: `tests/application/test_factor_test_app.py`

- [ ] **Step 1: Write the FactorTestAppService**

```python
# src/application/factor_test_app.py
"""因子测试应用服务 — 数据准备 + 批量测试 + 判决。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.factor_test.factor_catalog import FactorHypothesis
from src.domain.strategy.factor_test.report import ScoredFactorTestReport
from src.domain.strategy.factor_test.verdict import FactorVerdict, judge_factor
from src.domain.strategy.services.cross_section_builder import CrossSectionBuilder
from src.infrastructure.factor_test.test_runner import FactorTestRunner
from src.infrastructure.mock.mock_market import MockMarketGateway

if TYPE_CHECKING:
    from src.domain.market.interfaces.gateways.history_fetcher import IHistoryDataFetcher
    from src.domain.market.interfaces.gateways.fundamental_fetcher import IFundamentalFetcher


@dataclass(slots=True, kw_only=True)
class FactorTestResult:
    """单因子测试结果(含 IS/OOS 判决)。"""
    hypothesis: FactorHypothesis
    is_report: ScoredFactorTestReport
    oos_report: ScoredFactorTestReport | None = None
    verdict: FactorVerdict


class FactorTestAppService:
    """因子测试应用服务。

    职责:
    1. 加载历史数据 → 构建 snapshots_by_date
    2. 批量运行因子测试
    3. 样本内外切分
    4. 硬门槛判决
    """

    def __init__(
        self,
        history_fetcher: IHistoryDataFetcher,
        fundamental_fetcher: IFundamentalFetcher,
    ) -> None:
        self._history_fetcher = history_fetcher
        self._fundamental_fetcher = fundamental_fetcher
        self._runner = FactorTestRunner()

    def prepare_snapshots(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
    ) -> tuple[
        dict[str, list[StockSnapshot]],
        dict[str, dict[str, float]],
        dict[str, dict[str, float]],
    ]:
        """构建因子测试所需的数据结构。

        Returns:
            snapshots_by_date: {date_str: [StockSnapshot, ...]}
            returns_by_date: {date_str: {symbol: next_day_return}}
            prices_by_date: {date_str: {symbol: close_price}}
        """
        market = MockMarketGateway()
        tf = Timeframe.DAY_1

        # 1. 加载行情数据
        for symbol in symbols:
            bars = self._history_fetcher.fetch_history_bars(symbol, tf, start_date, end_date)
            market.load_bars(bars)

        # 2. 加载基本面数据
        registry = FundamentalRegistry()
        fund_snapshots = self._fundamental_fetcher.fetch_by_range(start_date, end_date, symbols=symbols)
        registry.load_snapshots(fund_snapshots)

        # 3. 按日构建 StockSnapshot
        all_timestamps = market.get_all_timestamps(tf)
        dt_start = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(end_date, "%Y-%m-%d")
        valid_timestamps = [ts for ts in all_timestamps if dt_start <= ts <= dt_end]

        snapshots_by_date: dict[str, list[StockSnapshot]] = {}
        prices_by_date: dict[str, dict[str, float]] = {}

        for ts in valid_timestamps:
            market.set_current_time(ts)
            date_str = ts.strftime("%Y-%m-%d")

            # 获取当日 bar + 历史 bar
            bars_today: dict[str, StockSnapshot] = {}
            bar_history: dict[str, list] = {}
            close_prices: dict[str, float] = {}

            for sym in symbols:
                recent = market.get_recent_bars(sym, tf, 120)
                if len(recent) < 2:
                    continue
                # info_bars = T-1 and earlier (no lookahead)
                info_bars = recent[:-1]
                exec_bar = recent[-1]
                if info_bars:
                    bars_today[sym] = info_bars[-1]
                    bar_history[sym] = info_bars
                    close_prices[sym] = exec_bar.close

            if not bars_today:
                continue

            # CrossSectionBuilder 需要 {symbol: Bar} (当日 bar for snapshot)
            day_bars = {sym: bar for sym, bar in bars_today.items()}
            snapshots = CrossSectionBuilder.build_cross_section(
                ts, day_bars, registry, bar_history
            )
            if snapshots:
                snapshots_by_date[date_str] = snapshots
                prices_by_date[date_str] = close_prices

        # 4. 计算次日收益 (returns_by_date)
        sorted_dates = sorted(snapshots_by_date.keys())
        returns_by_date: dict[str, dict[str, float]] = {}
        for i, date_str in enumerate(sorted_dates):
            if i + 1 >= len(sorted_dates):
                break
            next_date = sorted_dates[i + 1]
            today_prices = prices_by_date.get(date_str, {})
            next_prices = prices_by_date.get(next_date, {})
            day_returns: dict[str, float] = {}
            for sym in today_prices:
                if sym in next_prices and today_prices[sym] > 0:
                    day_returns[sym] = (next_prices[sym] - today_prices[sym]) / today_prices[sym]
            returns_by_date[date_str] = day_returns

        return snapshots_by_date, returns_by_date, prices_by_date

    def run_single(
        self,
        hypothesis: FactorHypothesis,
        snapshots_by_date: dict[str, list[StockSnapshot]],
        returns_by_date: dict[str, dict[str, float]],
        prices_by_date: dict[str, dict[str, float]],
        test_period: tuple[str, str],
        num_layers: int = 5,
    ) -> ScoredFactorTestReport:
        """测试单个因子假设。"""
        return self._runner.run(
            expression_str=hypothesis.expression,
            snapshots_by_date=snapshots_by_date,
            returns_by_date=returns_by_date,
            prices_by_date=prices_by_date,
            test_period=test_period,
            num_layers=num_layers,
        )

    def run_batch(
        self,
        hypotheses: list[FactorHypothesis],
        snapshots_by_date: dict[str, list[StockSnapshot]],
        returns_by_date: dict[str, dict[str, float]],
        prices_by_date: dict[str, dict[str, float]],
        test_period: tuple[str, str],
        split_date: str | None = None,
        num_layers: int = 5,
    ) -> list[FactorTestResult]:
        """批量测试因子假设，支持样本内外切分。

        Args:
            hypotheses: 因子假设列表。
            snapshots_by_date: 全量截面数据。
            returns_by_date: 全量收益数据。
            prices_by_date: 全量价格数据。
            test_period: (start_date, end_date)。
            split_date: 样本内截止日期 (如 "2023-12-31")，None=不做切分。
            num_layers: 分层数。

        Returns:
            list[FactorTestResult]: 每个因子的测试结果+判决。
        """
        results: list[FactorTestResult] = []

        for hyp in hypotheses:
            print(f"  Testing {hyp.factor_id} {hyp.name}: {hyp.expression}")

            # In-sample
            if split_date:
                is_snapshots = {d: v for d, v in snapshots_by_date.items() if d <= split_date}
                is_returns = {d: v for d, v in returns_by_date.items() if d <= split_date}
                is_prices = {d: v for d, v in prices_by_date.items() if d <= split_date}
                is_period = (test_period[0], split_date)
            else:
                is_snapshots = snapshots_by_date
                is_returns = returns_by_date
                is_prices = prices_by_date
                is_period = test_period

            is_report = self.run_single(
                hyp, is_snapshots, is_returns, is_prices, is_period, num_layers
            )

            # Out-of-sample (if split)
            oos_report: ScoredFactorTestReport | None = None
            if split_date:
                oos_snapshots = {d: v for d, v in snapshots_by_date.items() if d > split_date}
                oos_returns = {d: v for d, v in returns_by_date.items() if d > split_date}
                oos_prices = {d: v for d, v in prices_by_date.items() if d > split_date}
                oos_period = (split_date, test_period[1])
                if oos_snapshots:
                    oos_report = self.run_single(
                        hyp, oos_snapshots, oos_returns, oos_prices, oos_period, num_layers
                    )

            verdict = judge_factor(
                is_report, oos_report=oos_report,
                factor_id=hyp.factor_id, factor_name=hyp.name,
            )

            results.append(FactorTestResult(
                hypothesis=hyp,
                is_report=is_report,
                oos_report=oos_report,
                verdict=verdict,
            ))

            status = "PASS ✓" if verdict.passed else "FAIL ✗"
            print(f"    → {status} | IC={is_report.ic_mean:.4f} IR={is_report.ir:.3f} "
                  f"Score={is_report.score:.0f}({is_report.grade})")

        return results
```

- [ ] **Step 2: Write a minimal unit test for FactorTestAppService**

```python
# tests/application/test_factor_test_app.py
"""Tests for FactorTestAppService — mock-based integration test."""

from datetime import datetime
from unittest.mock import MagicMock

from src.application.factor_test_app import FactorTestAppService, FactorTestResult
from src.domain.strategy.factor_test.factor_catalog import P0_FACTORS
from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class TestFactorTestAppServiceRunSingle:
    def test_run_single_calls_runner(self):
        """Verify run_single delegates to FactorTestRunner."""
        mock_hist = MagicMock()
        mock_fund = MagicMock()
        service = FactorTestAppService(
            history_fetcher=mock_hist,
            fundamental_fetcher=mock_fund,
        )
        # Mock the runner
        service._runner = MagicMock()
        mock_report = MagicMock()
        service._runner.run.return_value = mock_report

        result = service.run_single(
            P0_FACTORS[0],
            snapshots_by_date={},
            returns_by_date={},
            prices_by_date={},
            test_period=("2021-01-01", "2025-12-31"),
        )

        service._runner.run.assert_called_once()
        assert result is mock_report


class TestFactorTestAppServiceRunBatch:
    def test_run_batch_with_split(self):
        """Verify batch run creates IS + OOS reports when split_date is set."""
        mock_hist = MagicMock()
        mock_fund = MagicMock()
        service = FactorTestAppService(
            history_fetcher=mock_hist,
            fundamental_fetcher=mock_fund,
        )
        # Mock runner to return a valid report
        from src.domain.strategy.factor_test.report import FactorTestReport, ScoredFactorTestReport
        mock_r = FactorTestReport(
            expression="0 - return_20d",
            test_period=("2021-01-01", "2025-12-31"),
            universe_count=100,
            ic_mean=0.04, ic_std=0.02, ir=0.5,
            ic_positive_rate=0.6, monotonicity_score=0.8,
            long_short_return=0.1,
        )
        mock_scored = ScoredFactorTestReport(
            report=mock_r, score=75.0, grade="B", grade_reasons=["test"]
        )
        service._runner = MagicMock()
        service._runner.run.return_value = mock_scored

        # Fake data with two dates
        snapshots = {"2023-01-01": [], "2024-01-01": []}
        returns = {"2023-01-01": {}, "2024-01-01": {}}
        prices = {"2023-01-01": {}, "2024-01-01": {}}

        results = service.run_batch(
            hypotheses=P0_FACTORS[:1],
            snapshots_by_date=snapshots,
            returns_by_date=returns,
            prices_by_date=prices,
            test_period=("2023-01-01", "2024-01-01"),
            split_date="2023-12-31",
        )

        assert len(results) == 1
        assert isinstance(results[0], FactorTestResult)
        # Runner called twice (IS + OOS)
        assert service._runner.run.call_count == 2
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/application/test_factor_test_app.py -v
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/application/factor_test_app.py tests/application/test_factor_test_app.py
git commit -m "feat: add FactorTestAppService with batch testing and sample split"
```

---

### Task 3: Wire CLI Command

**Files:**
- Modify: `src/interfaces/cli/commands/factor_test.py`
- Modify: `src/interfaces/cli/quant.py`
- Create: `tests/interfaces/cli/test_factor_test_cli.py`

- [ ] **Step 1: Update CLI argument parser in quant.py**

Add `--split-date`, `--num-layers`, `--output` arguments to the `factor-test` subparser.

Edit `src/interfaces/cli/quant.py`, replace the `factor-test` block (lines 56-60):

```python
    # --- factor-test ---
    p_ft = subparsers.add_parser("factor-test", help="因子假设测试")
    p_ft.add_argument("--factors", type=str, required=True,
                       help="因子标识: F01,F02 / 小市值,短期反转 / P0 / all")
    p_ft.add_argument("--start-date", type=str, default="2021-01-01", help="测试开始日期")
    p_ft.add_argument("--end-date", type=str, default="2025-12-31", help="测试结束日期")
    p_ft.add_argument("--split-date", type=str, default=None,
                       help="样本内截止日期(如 2023-12-31)，启用样本外验证")
    p_ft.add_argument("--num-layers", type=int, default=5, help="分层数")
    p_ft.add_argument("--output", type=str, default=None, help="报告输出路径(JSON)")
    p_ft.add_argument("--config", type=str, default="resources/backtest.yaml", help="配置文件")
```

- [ ] **Step 2: Rewrite factor_test.py CLI command**

```python
# src/interfaces/cli/commands/factor_test.py
"""quant factor-test 子命令实现 — 接通 FactorTestRunner 引擎。"""

import argparse
import json
from datetime import datetime


def run_factor_test(args: argparse.Namespace) -> None:
    """执行因子假设测试。"""
    from src.domain.strategy.factor_test.factor_catalog import resolve_factors

    factor_str: str = args.factors
    start_date: str = args.start_date
    end_date: str = args.end_date
    split_date: str | None = args.split_date
    num_layers: int = args.num_layers
    output_path: str | None = args.output
    config_path: str = args.config

    # 1. 解析因子列表
    try:
        hypotheses = resolve_factors(factor_str)
    except ValueError as e:
        print(f"Error: {e}")
        return

    print(f"=== Factor Hypothesis Test ===")
    print(f"Factors: {', '.join(f'{h.factor_id}({h.name})' for h in hypotheses)}")
    print(f"Period:  {start_date} → {end_date}")
    if split_date:
        print(f"Split:   IS={start_date}→{split_date} | OOS={split_date}→{end_date}")
    print(f"Layers:  {num_layers}")
    print()

    # 2. 加载配置 → 获取 symbols 和 fetcher
    try:
        from src.infrastructure.config.settings import load_backtest_config
        settings = load_backtest_config(config_path)
        symbols = settings.backtest.symbols
        history_fetcher_type = settings.data.history_fetcher
        tushare_token = settings.data.tushare.token
    except FileNotFoundError:
        print(f"Config not found ({config_path}), using default symbols.")
        symbols = ["000021.SZ"]
        history_fetcher_type = "TushareHistoryDataFetcher"
        tushare_token = None

    # 3. 初始化 fetchers
    if history_fetcher_type == "TushareHistoryDataFetcher":
        from src.infrastructure.gateway.tushare_history_data import TushareHistoryDataFetcher
        from src.infrastructure.gateway.tushare_fundamental_fetcher import TushareFundamentalFetcher

        history_fetcher = TushareHistoryDataFetcher(token=tushare_token)
        fundamental_fetcher = TushareFundamentalFetcher(token=tushare_token)
    else:
        from src.infrastructure.gateway.qmt_history_data import QmtHistoryDataFetcher
        from src.infrastructure.gateway.qmt_fundamental_fetcher import QmtFundamentalFetcher

        history_fetcher = QmtHistoryDataFetcher()
        fundamental_fetcher = QmtFundamentalFetcher()

    # 4. 如果是截面策略需要全市场，扩大 symbols
    if len(symbols) <= 5:
        print(f"Warning: Only {len(symbols)} symbols configured. Factor testing works best with 200+ stocks.")
        print(f"Consider adding more symbols to {config_path}.")

    # 5. 创建服务并执行
    from src.application.factor_test_app import FactorTestAppService

    service = FactorTestAppService(
        history_fetcher=history_fetcher,
        fundamental_fetcher=fundamental_fetcher,
    )

    print(f"[Step 1] Preparing data ({len(symbols)} symbols)...")
    try:
        snapshots_by_date, returns_by_date, prices_by_date = service.prepare_snapshots(
            symbols, start_date, end_date,
        )
    except Exception as e:
        print(f"Error preparing data: {e}")
        return

    print(f"  → {len(snapshots_by_date)} trading days, "
          f"avg {sum(len(v) for v in snapshots_by_date.values()) / max(len(snapshots_by_date), 1):.0f} stocks/day")

    print(f"\n[Step 2] Running factor tests...")
    results = service.run_batch(
        hypotheses=hyptheses,
        snapshots_by_date=snapshots_by_date,
        returns_by_date=returns_by_date,
        prices_by_date=prices_by_date,
        test_period=(start_date, end_date),
        split_date=split_date,
        num_layers=num_layers,
    )

    # 6. 输出汇总
    print(f"\n{'=' * 80}")
    print(f"{'FACTOR VERDICT SUMMARY':^80}")
    print(f"{'=' * 80}")
    print(f"{'ID':<5} {'Name':<12} {'IC':>8} {'IR':>8} {'Mono':>6} {'L/S':>8} {'Score':>6} {'Grade':>6} {'Verdict':>8}")
    print(f"{'-' * 80}")

    passed_count = 0
    for r in results:
        v = r.verdict
        status = "PASS ✓" if v.passed else "FAIL ✗"
        if v.passed:
            passed_count += 1
        print(f"{v.factor_id:<5} {v.factor_name:<12} {v.ic_mean:>8.4f} {v.ir:>8.3f} "
              f"{v.monotonicity_score:>6.2f} {v.long_short_return:>8.2%} "
              f"{v.score:>6.0f} {v.grade:>6} {status:>8}")

    print(f"{'-' * 80}")
    print(f"Passed: {passed_count}/{len(results)}")

    # 7. 详细判决原因
    print(f"\n{'DETAILED VERDICTS':^80}")
    for r in results:
        v = r.verdict
        status = "PASS" if v.passed else "FAIL"
        print(f"\n[{v.factor_id}] {v.factor_name} — {status}")
        for reason in v.reasons:
            print(f"  {reason}")

    # 8. 输出 JSON (if requested)
    if output_path:
        output = {
            "test_period": [start_date, end_date],
            "split_date": split_date,
            "num_layers": num_layers,
            "results": [],
        }
        for r in results:
            v = r.verdict
            output["results"].append({
                "factor_id": v.factor_id,
                "factor_name": v.factor_name,
                "expression": v.expression,
                "ic_mean": v.ic_mean,
                "ir": v.ir,
                "ic_positive_rate": v.ic_positive_rate,
                "monotonicity_score": v.monotonicity_score,
                "long_short_return": v.long_short_return,
                "score": v.score,
                "grade": v.grade,
                "oos_ic_mean": v.oos_ic_mean,
                "oos_ir": v.oos_ir,
                "oos_long_short_return": v.oos_long_short_return,
                "passed": v.passed,
                "reasons": v.reasons,
            })
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to {output_path}")
```

- [ ] **Step 3: Fix typo in factor_test.py**

There is a typo: `hyptheses` should be `hypotheses`. Fix in the file.

- [ ] **Step 4: Write a smoke test for the CLI wiring**

```python
# tests/interfaces/cli/test_factor_test_cli.py
"""Smoke test for factor-test CLI wiring."""

import argparse
from unittest.mock import MagicMock, patch

from src.interfaces.cli.commands.factor_test import run_factor_test


class TestFactorTestCLI:
    @patch("src.interfaces.cli.commands.factor_test.FactorTestAppService")
    def test_run_factor_test_calls_service(self, mock_service_cls):
        """Verify CLI command creates service and calls run_batch."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.prepare_snapshots.return_value = ({}, {}, {})
        mock_service.run_batch.return_value = []

        args = argparse.Namespace(
            factors="F01,F02",
            start_date="2021-01-01",
            end_date="2025-12-31",
            split_date=None,
            num_layers=5,
            output=None,
            config="nonexistent.yaml",
        )

        run_factor_test(args)

        mock_service.prepare_snapshots.assert_called_once()
        mock_service.run_batch.assert_called_once()
```

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/interfaces/cli/test_factor_test_cli.py tests/application/test_factor_test_app.py tests/domain/strategy/factor_test/test_verdict.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/interfaces/cli/commands/factor_test.py src/interfaces/cli/quant.py tests/interfaces/cli/test_factor_test_cli.py
git commit -m "feat: wire quant factor-test CLI to FactorTestRunner engine"
```

---

### Task 4: Run P0 Factors End-to-End

**Files:**
- No new files. This is a manual verification task.

- [ ] **Step 1: Run P0 factors with a small universe (smoke test)**

```bash
python -m src.interfaces.cli.quant factor-test --factors P0 --start-date 2023-01-01 --end-date 2024-12-31 --output data/factor_results_p0.json
```

Expected: Output shows 5 factor test results with IC/IR/score/verdict. Some may PASS, some may FAIL depending on data.

- [ ] **Step 2: Run with sample split**

```bash
python -m src.interfaces.cli.quant factor-test --factors P0 --start-date 2021-01-01 --end-date 2025-12-31 --split-date 2023-12-31 --output data/factor_results_p0_split.json
```

Expected: Output shows IS and OOS metrics for each factor.

- [ ] **Step 3: Run all factors**

```bash
python -m src.interfaces.cli.quant factor-test --factors all --start-date 2021-01-01 --end-date 2025-12-31 --split-date 2023-12-31 --output data/factor_results_all.json
```

Expected: Output shows all 12 factors tested.

- [ ] **Step 4: Verify JSON output**

```bash
python -c "import json; d=json.load(open('data/factor_results_p0.json')); print(json.dumps(d['results'][0], indent=2, ensure_ascii=False))"
```

Expected: Valid JSON with all fields populated.

- [ ] **Step 5: Commit results data (optional)**

```bash
git add data/factor_results_p0.json data/factor_results_p0_split.json
git commit -m "data: P0 factor test results (2021-2025)"
```

---

### Task 5: Run Full Test Suite & Lint

**Files:**
- No new files.

- [ ] **Step 1: Run ruff lint**

```bash
ruff check src/application/factor_test_app.py src/domain/strategy/factor_test/factor_catalog.py src/domain/strategy/factor_test/verdict.py src/interfaces/cli/commands/factor_test.py
```

Expected: No errors.

- [ ] **Step 2: Run full test suite**

```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -v
```

Expected: All tests PASS, no regressions.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: factor hypothesis library — end-to-end validation pipeline"
```
