# Spec 1 · 回测引擎正确性修复 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development(推荐)或 superpowers:executing-plans 逐任务执行本计划。步骤用 `- [ ]` checkbox 跟踪。

**Goal:** 消除回测引擎两个 P0(截面前视偏差、复权口径割裂)+ 四个 P1(成交价语义、Sortino、买入费用、板块涨跌停),并建立金标准测试网。

**Architecture:** 在 `recent` 序列上提取 `BarWindow` 值对象,显式分离「信息边界(info_bars,截至 T-1)」与「成交 bar(exec_bar,T 日)」,两个 runner 共用以根治"两套尺子";`MockTradeGateway` 改用 `order.price`(前复权)成交,全链路前复权;指标公式按标准定义修正。

**Tech Stack:** Python 3.13、pytest、dataclass(slots/kw_only)、DDD 分层(domain 禁第三方库)。

---

## 执行约定

- **分支**:已在 `feat/backtest-correctness`(spec 提交所在分支),全部任务在此分支推进。
- **Commit**:每个任务末尾提交一次;commit message 结尾统一附下面这行(各任务命令为简洁省略,默认遵循):
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- **测试命令前缀**:`python -m pytest`(WSL Python,本 spec 不涉及 xtquant)。
- **TDD 纪律**:先写会失败的测试 → 运行确认失败 → 最小实现 → 运行确认通过 → 提交。不得跳步。
- **批次顺序**:Task 1–4(成交假设核心)→ Task 5–7(指标)→ Task 8–10(测试网/回归/清理)。

---

## File Structure

**新增:**
- `src/domain/backtest/value_objects/bar_window.py` — `BarWindow` 值对象 + `make_bar_window`(信息/成交 bar 分离;T+0 扩展点)
- `tests/domain/backtest/value_objects/test_bar_window.py`
- `tests/application/test_strategy_runner_lookahead.py` — 前视金标准
- `tests/domain/backtest/entities/test_backtest_report.py` — Sortino/Sharpe 单元
- `tests/infrastructure/mock/test_mock_trade_adjustment.py` — 成交价语义 + 复权一致性金标准

**修改:**
- `src/application/strategy_runner.py` — 两个 runner 改用 `BarWindow`
- `src/infrastructure/mock/mock_trade.py` — `place_order` 用 `order.price` 成交、涨跌停前复权 + 板块幅度、买入费用传参
- `src/domain/account/entities/position.py` — `on_buy_filled` 增 `fee`
- `src/domain/backtest/entities/backtest_report.py` — Sortino 修正 + Sharpe 清理
- `src/domain/market/value_objects/price_limit.py` — `get_price_limit_ratio`
- `tests/domain/account/test_position.py`、`tests/domain/market/test_price_limit.py` — 追加用例

---

## Task 1: BarWindow 值对象

**Files:**
- Create: `src/domain/backtest/value_objects/bar_window.py`
- Test: `tests/domain/backtest/value_objects/test_bar_window.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/domain/backtest/value_objects/test_bar_window.py
from datetime import datetime

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.backtest.value_objects.bar_window import BarWindow, make_bar_window


def _bar(dt: datetime, open_: float, close: float) -> Bar:
    return Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=dt,
               open=open_, high=close * 1.02, low=open_ * 0.98, close=close, volume=1e6)


def test_make_bar_window_splits_info_and_exec():
    recent = [
        _bar(datetime(2024, 6, 1), 9.0, 9.5),
        _bar(datetime(2024, 6, 2), 9.5, 10.0),
        _bar(datetime(2024, 6, 3), 10.0, 12.0),  # 成交 bar(T 日)
    ]
    window = make_bar_window(recent)
    assert window is not None
    assert len(window.info_bars) == 2
    assert window.info_bars[-1].timestamp == datetime(2024, 6, 2)   # 信息止于 T-1
    assert window.exec_bar.timestamp == datetime(2024, 6, 3)        # 成交 bar 是 T 日
    assert window.exec_price == 10.0   # 成交价 = T 日开盘
    assert window.mark_price == 12.0   # 估值价 = T 日收盘


def test_make_bar_window_returns_none_when_too_few_bars():
    assert make_bar_window([]) is None
    assert make_bar_window([_bar(datetime(2024, 6, 3), 10.0, 12.0)]) is None
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/domain/backtest/value_objects/test_bar_window.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.domain.backtest.value_objects.bar_window'`

- [ ] **Step 3: 实现**

```python
# src/domain/backtest/value_objects/bar_window.py
from dataclasses import dataclass

from src.domain.market.value_objects.bar import Bar


@dataclass(frozen=True, slots=True, kw_only=True)
class BarWindow:
    """从一段连续 bar 派生回测决策所需的价格视图,统一信息边界与成交时点。

    信息边界(info_bars)严格早于成交时点(exec_bar),消除前视偏差。
    这是将来 T+0 / 日内交易的单一职责扩展点。
    """

    info_bars: list[Bar]   # 决策可见:截至 T-1(不含成交 bar)
    exec_bar: Bar          # 成交 bar:T 日

    @property
    def exec_price(self) -> float:
        """成交参考价:T 日开盘价(前复权)。"""
        return self.exec_bar.open

    @property
    def mark_price(self) -> float:
        """估值价:T 日收盘价(前复权)。"""
        return self.exec_bar.close


def make_bar_window(recent: list[Bar]) -> BarWindow | None:
    """recent 需至少 2 根(≥1 根信息 + 1 根成交),否则返回 None 由调用方跳过。"""
    if len(recent) < 2:
        return None
    return BarWindow(info_bars=recent[:-1], exec_bar=recent[-1])
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/domain/backtest/value_objects/test_bar_window.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add src/domain/backtest/value_objects/bar_window.py tests/domain/backtest/value_objects/test_bar_window.py
git commit -m "feat(backtest): 新增 BarWindow 分离信息边界与成交时点"
```

---

## Task 2: 截面 runner 前视修复(P0-1 金标准)

**Files:**
- Modify: `src/application/strategy_runner.py`（`CrossSectionalStrategyRunner.evaluate`,约 142-196 行）
- Test: `tests/application/test_strategy_runner_lookahead.py`

- [ ] **Step 1: 写失败的金标准测试**

该测试拦截 `build_cross_section`,捕获 runner 喂给因子的 bar——断言它是 T-1(close=10),而非 T 日(close=99)。

```python
# tests/application/test_strategy_runner_lookahead.py
from datetime import datetime

from src.application.strategy_runner import CrossSectionalStrategyRunner, DayContext
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway
from src.infrastructure.ml_engine.feature_pipeline import FeaturePipeline


class _EmptyCS(CrossSectionalStrategy):
    @property
    def name(self) -> str:
        return "EmptyCS"

    def generate_cross_sectional_signals(self, universe, current_positions, current_date):
        return []


def _bar(sym, dt, close):
    return Bar(symbol=sym, timeframe=Timeframe.DAY_1, timestamp=dt,
               open=close, high=close * 1.02, low=close * 0.98, close=close, volume=1e6)


def test_cross_sectional_runner_feeds_only_past_bars_to_factor(monkeypatch):
    sym = "000001.SZ"
    t_minus_1 = datetime(2024, 6, 3)
    t = datetime(2024, 6, 4)
    market = MockMarketGateway()
    market.add_bars(sym, [_bar(sym, t_minus_1, 10.0), _bar(sym, t, 99.0)])
    market.set_current_time(t)

    captured = {}

    def fake_build_cross_section(date, bars, registry, bar_history=None):
        captured["snapshot_bar"] = bars[sym]
        captured["history"] = bar_history[sym]
        return []

    monkeypatch.setattr(FeaturePipeline, "build_cross_section",
                        staticmethod(fake_build_cross_section))

    runner = CrossSectionalStrategyRunner(
        strategy=_EmptyCS(), sizer=EqualWeightSizer(n_symbols=1),
        market_gateway=market, trade_gateway=MockTradeGateway(market, initial_capital=1_000_000),
        fundamental_registry=FundamentalRegistry(),
    )
    runner.evaluate(DayContext(current_time=t, symbols=[sym], base_timeframe=Timeframe.DAY_1))

    # 喂给因子的必须是 T-1(close=10),而非 T 日(close=99)——否则即前视
    assert captured["snapshot_bar"].close == 10.0
    assert captured["history"][-1].close == 10.0
    assert all(b.timestamp < t for b in captured["history"])
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/application/test_strategy_runner_lookahead.py -v`
Expected: FAIL — `assert 99.0 == 10.0`（修复前 runner 把 T 日 bar 喂给因子）

- [ ] **Step 3: 修复 `CrossSectionalStrategyRunner.evaluate`**

将原循环（构造 `bars`/`bar_history` 与 `prices`/`current_prices`）替换为基于 `BarWindow` 的版本。文件顶部新增 import：

```python
from src.domain.backtest.value_objects.bar_window import make_bar_window
```

`evaluate` 内：原

```python
        bars: dict[str, Bar] = {}
        bar_history: dict[str, list[Bar]] = {}
        for sym in context.symbols:
            recent = self.market_gateway.get_recent_bars(sym, context.base_timeframe, 120)
            if recent:
                bars[sym] = recent[-1]
                bar_history[sym] = recent
```

改为

```python
        bars: dict[str, Bar] = {}
        bar_history: dict[str, list[Bar]] = {}
        exec_bars: dict[str, Bar] = {}
        for sym in context.symbols:
            recent = self.market_gateway.get_recent_bars(sym, context.base_timeframe, 120)
            window = make_bar_window(recent)
            if window is None:
                continue
            bars[sym] = window.info_bars[-1]      # 因子快照:T-1(不偷看当日)
            bar_history[sym] = window.info_bars   # 因子历史:截至 T-1
            exec_bars[sym] = window.exec_bar      # 成交/估值:T 日
```

同一方法内，成交价与估值价改用 `exec_bars`。原

```python
        prices = {sym: bar.open for sym, bar in bars.items()}
```

改为

```python
        prices = {sym: bar.open for sym, bar in exec_bars.items()}   # 成交价 = T 日开盘(前复权)
```

原

```python
        current_prices = {sym: bar.close for sym, bar in bars.items()}
        return targets, current_prices
```

改为

```python
        current_prices = {sym: bar.close for sym, bar in exec_bars.items()}  # 估值 = T 日收盘(前复权)
        return targets, current_prices
```

> `risk_signal_gen.evaluate(current_positions, bars)` 保持传 `bars`(现为 T-1 快照)——风控止损也基于昨收判断、今开执行,与因子口径一致。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/application/test_strategy_runner_lookahead.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: 提交**

```bash
git add src/application/strategy_runner.py tests/application/test_strategy_runner_lookahead.py
git commit -m "fix(backtest): 修复截面策略前视偏差,因子只用截至 T-1 的数据 (P0-1)"
```

---

## Task 3: 单标的 runner 归一 BarWindow（DD-4）

**Files:**
- Modify: `src/application/strategy_runner.py`（`SingleStrategyRunner.evaluate`,约 62-109 行）
- Test: `tests/application/test_strategy_runner_lookahead.py`（追加）

- [ ] **Step 1: 追加对称测试**

```python
def test_single_runner_feeds_only_past_bars_to_strategy():
    from src.application.strategy_runner import SingleStrategyRunner
    from src.domain.strategy.services.base_strategy import BaseStrategy
    from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer

    sym = "000001.SZ"
    t_minus_1 = datetime(2024, 6, 3)
    t = datetime(2024, 6, 4)
    market = MockMarketGateway()
    market.add_bars(sym, [_bar(sym, t_minus_1, 10.0), _bar(sym, t, 99.0)])
    market.set_current_time(t)

    captured = {}

    class _CaptureStrategy(BaseStrategy):
        @property
        def name(self): return "Capture"
        def generate_signals(self, market_data, current_positions):
            captured["data"] = market_data
            return []

    runner = SingleStrategyRunner(
        strategy=_CaptureStrategy(), sizer=FixedRatioSizer(ratio=0.2),
        market_gateway=market, trade_gateway=MockTradeGateway(market, initial_capital=1_000_000),
    )
    runner.evaluate(DayContext(current_time=t, symbols=[sym], base_timeframe=Timeframe.DAY_1))

    # 策略只应看到 T-1(close=10),不含 T 日(close=99)
    assert captured["data"][sym][-1].close == 10.0
    assert all(b.timestamp < t for b in captured["data"][sym])
```

> 该测试在修复前也可能通过（`SingleStrategyRunner` 已用 `all_bars[:-1]`），它是**防回归锚点**,确保归一到 `BarWindow` 后行为不变。

- [ ] **Step 2: 运行（应通过，记录基线）**

Run: `python -m pytest tests/application/test_strategy_runner_lookahead.py::test_single_runner_feeds_only_past_bars_to_strategy -v`
Expected: PASS（行为正确的基线）

- [ ] **Step 3: 归一到 BarWindow**

`SingleStrategyRunner.evaluate` 内，原

```python
        for symbol in context.symbols:
            all_bars = self.market_gateway.get_recent_bars(symbol, context.base_timeframe, self.LOOKBACK_WINDOW)
            if not all_bars:
                continue
            if len(all_bars) >= 2:
                strategy_market_data[symbol] = all_bars[:-1]
            current_bar = all_bars[-1]
            execution_prices[symbol] = current_bar.open
            current_prices[symbol] = current_bar.close
```

改为

```python
        for symbol in context.symbols:
            recent = self.market_gateway.get_recent_bars(symbol, context.base_timeframe, self.LOOKBACK_WINDOW)
            window = make_bar_window(recent)
            if window is None:
                continue
            strategy_market_data[symbol] = window.info_bars   # 截至 T-1
            execution_prices[symbol] = window.exec_price       # T 日开盘
            current_prices[symbol] = window.mark_price          # T 日收盘
```

- [ ] **Step 4: 运行确认仍通过 + 现有 runner 测试不破**

Run: `python -m pytest tests/application/test_strategy_runner_lookahead.py tests/application/test_strategy_runner_with_breaker.py -v`
Expected: PASS（行为等价重构）

- [ ] **Step 5: 提交**

```bash
git add src/application/strategy_runner.py tests/application/test_strategy_runner_lookahead.py
git commit -m "refactor(backtest): 单标的 runner 归一到 BarWindow,消除两套尺子 (DD-4)"
```

---

## Task 4: MockGateway 用 order.price 成交（P0-2 / P1-1）

**Files:**
- Modify: `src/infrastructure/mock/mock_trade.py`（`place_order`,约 140-177 行）
- Test: `tests/infrastructure/mock/test_mock_trade_adjustment.py`

- [ ] **Step 1: 写失败测试**

构造 `close`（前复权）与 `unadjusted_close`（不复权）显著不同的 bar，断言成交价跟随 `order.price`（前复权 open），而非 `unadjusted_close`。

```python
# tests/infrastructure/mock/test_mock_trade_adjustment.py
from datetime import datetime

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway


def test_exec_price_follows_order_price_not_unadjusted_close():
    market = MockMarketGateway()
    # 前复权 open/close = 10,但 unadjusted_close = 20(模拟回测后段有除权)
    bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 3),
              open=10.0, high=10.5, low=9.5, close=10.0, volume=1_000_000, unadjusted_close=20.0)
    market.add_bars("000001.SZ", [bar])
    market.set_current_time(datetime(2024, 1, 3))
    gateway = MockTradeGateway(market, initial_capital=1_000_000.0)

    order = Order(order_id="B1", account_id=MockTradeGateway.DEFAULT_ACCOUNT_ID, ticker="000001.SZ",
                  direction=OrderDirection.BUY, price=10.0, volume=100, type=OrderType.LIMIT)
    gateway.place_order(order)

    pos = gateway.get_position("000001.SZ")
    # 成交价应≈ order.price*1.001 = 10.01(前复权),而非 unadjusted_close 20*1.001=20.02
    assert pos.average_cost < 11.0, f"成交价疑似用了不复权价: average_cost={pos.average_cost}"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/infrastructure/mock/test_mock_trade_adjustment.py::test_exec_price_follows_order_price_not_unadjusted_close -v`
Expected: FAIL — `average_cost` ≈ 20.02（修复前用 `unadjusted_close`）

- [ ] **Step 3: 修复成交价 + 涨跌停前复权**

`place_order` 内，原

```python
        # 4. 计算成交价格 (基于不复权价进行账本结算)
        if bar.unadjusted_close > 0:
            ref_price = bar.unadjusted_close
        else:
            ref_price = bar.close  # 向后兼容：若无不复权数据则回退
```

改为

```python
        # 4. 计算成交价格 (前复权坐标系,使用 runner 传入的 order.price)
        if order.price <= 0:
            order.status = OrderStatus.REJECTED
            raise OrderSubmitError(f"Invalid order price {order.price}")
        ref_price = order.price
```

涨跌停校验处，原

```python
            prev_close = prev_bars[-2].unadjusted_close or prev_bars[-2].close
```

改为

```python
            prev_close = prev_bars[-2].close  # 前复权:涨跌停比例判断不受复权影响
```

- [ ] **Step 4: 运行确认通过 + mock_trade 现有测试不破**

Run: `python -m pytest tests/infrastructure/mock/test_mock_trade_adjustment.py tests/infrastructure/mock/test_mock_trade.py -v`
Expected: PASS（现有测试里 `order.price == bar.close` 且 `unadjusted_close=0`,结果不变）

- [ ] **Step 5: 提交**

```bash
git add src/infrastructure/mock/mock_trade.py tests/infrastructure/mock/test_mock_trade_adjustment.py
git commit -m "fix(backtest): 成交价改用 order.price 前复权,统一复权口径 (P0-2/P1-1)"
```

---

## Task 5: Sortino 公式修正 + Sharpe 清理（P1-2）

**Files:**
- Modify: `src/domain/backtest/entities/backtest_report.py`（`sortino_ratio` 66-79、`sharpe_ratio` 57 行）
- Test: `tests/domain/backtest/entities/test_backtest_report.py`

- [ ] **Step 1: 写失败测试（含手算值）**

```python
# tests/domain/backtest/entities/test_backtest_report.py
from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport


def _report(daily_returns):
    return BacktestReport(
        start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 5),
        initial_capital=1e6, final_capital=1e6, total_return=0.0,
        annualized_return=0.0, max_drawdown=0.0, win_rate=0.0,
        profit_loss_ratio=0.0, trade_count=0, daily_returns=daily_returns,
    )


def test_sortino_uses_standard_downside_deviation():
    # daily_returns = [-0.01, 0.02, -0.03, 0.01]
    # mean = -0.0025
    # downside_dev = sqrt((0.0001 + 0 + 0.0009 + 0)/4) = sqrt(0.00025) = 0.0158113883
    # sortino = (-0.0025 / 0.0158113883) * sqrt(252) = -2.5098
    report = _report([-0.01, 0.02, -0.03, 0.01])
    assert abs(report.sortino_ratio - (-2.5098)) < 0.01


def test_sortino_zero_when_no_downside():
    report = _report([0.01, 0.02, 0.03])
    assert report.sortino_ratio == 0.0
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/domain/backtest/entities/test_backtest_report.py -v`
Expected: FAIL — 旧公式（减自身均值）算出的值 ≠ -2.5098

- [ ] **Step 3: 修复**

`backtest_report.py`,原 `sortino_ratio` 整段（66-79）替换为：

```python
    @property
    def sortino_ratio(self) -> float:
        """索提诺比率(年化):标准下行偏差,目标收益 MAR=0,分母用全样本 N。"""
        if len(self.daily_returns) < 2:
            return 0.0
        mean_return = sum(self.daily_returns) / len(self.daily_returns)
        downside_dev = math.sqrt(
            sum(min(r, 0) ** 2 for r in self.daily_returns) / len(self.daily_returns)
        )
        if downside_dev == 0:
            return 0.0
        return (mean_return / downside_dev) * math.sqrt(252)
```

并删除 `sharpe_ratio` 中多余的浮点早返回（57-58 行）：

```python
        mean_return = sum(self.daily_returns) / len(self.daily_returns)
        if mean_return == 0:        # ← 删除这两行
            return 0.0
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/domain/backtest/entities/test_backtest_report.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add src/domain/backtest/entities/backtest_report.py tests/domain/backtest/entities/test_backtest_report.py
git commit -m "fix(backtest): Sortino 改标准下行偏差,清理 Sharpe 冗余早返回 (P1-2)"
```

---

## Task 6: 买入费用计入成本（P1-3）

**Files:**
- Modify: `src/domain/account/entities/position.py`（`on_buy_filled` 30-57 行）
- Modify: `src/infrastructure/mock/mock_trade.py`（`_simulate_fill` 买入分支,约 300 行）
- Test: `tests/domain/account/test_position.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/domain/account/test_position.py
def test_on_buy_filled_includes_fee_in_average_cost():
    from src.domain.account.entities.position import Position
    pos = Position(account_id="A", ticker="000001.SZ")
    pos.on_buy_filled(100, 10.0, fee=5.0)
    # average_cost = (100*10 + 5) / 100 = 10.05
    assert pos.average_cost == 10.05
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/domain/account/test_position.py::test_on_buy_filled_includes_fee_in_average_cost -v`
Expected: FAIL — `TypeError: on_buy_filled() got an unexpected keyword argument 'fee'`

- [ ] **Step 3: 修改 `Position.on_buy_filled`**

签名与成本基替换：

```python
    def on_buy_filled(self, volume: int, price: float, fee: float = 0.0) -> None:
        if volume <= 0:
            raise ValueError("Buy volume must be positive")
        if price < 0:
            raise ValueError("Price cannot be negative")

        current_total_cost = self.total_volume * self.average_cost
        new_cost_basis = volume * price + fee      # 成本含买入费用

        self.total_volume += volume
        if self.total_volume > 0:
            self.average_cost = (current_total_cost + new_cost_basis) / self.total_volume
        else:
            self.average_cost = 0.0
        self.updated_at = datetime.now()
```

- [ ] **Step 4: mock_trade 传入买入费用**

`_simulate_fill` 买入分支,原 `position.on_buy_filled(volume, price)` 改为：

```python
            position.on_buy_filled(volume, price, fee=commission + transfer_fee)  # 买入无印花税
```

- [ ] **Step 5: 运行确认通过 + position/mock_trade 测试不破**

Run: `python -m pytest tests/domain/account/test_position.py tests/infrastructure/mock/test_mock_trade.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/domain/account/entities/position.py src/infrastructure/mock/mock_trade.py tests/domain/account/test_position.py
git commit -m "fix(backtest): 买入费用计入 average_cost,realized_pnl 反映双边费用 (P1-3)"
```

---

## Task 7: 板块涨跌停识别（P1-4）

**Files:**
- Modify: `src/domain/market/value_objects/price_limit.py`（新增函数）
- Modify: `src/infrastructure/mock/mock_trade.py`（涨跌停校验接入,约 167 行）
- Test: `tests/domain/market/test_price_limit.py`（追加）、`tests/infrastructure/mock/test_mock_trade_adjustment.py`（追加）

- [ ] **Step 1: 写失败测试（纯函数）**

```python
# 追加到 tests/domain/market/test_price_limit.py
def test_get_price_limit_ratio_by_board():
    from src.domain.market.value_objects.price_limit import get_price_limit_ratio
    assert get_price_limit_ratio("600000.SH") == 0.10   # 沪主板
    assert get_price_limit_ratio("000001.SZ") == 0.10   # 深主板
    assert get_price_limit_ratio("688001.SH") == 0.20   # 科创板
    assert get_price_limit_ratio("300750.SZ") == 0.20   # 创业板
    assert get_price_limit_ratio("830799.BJ") == 0.30   # 北交所
    assert get_price_limit_ratio("000001.SZ", is_st=True) == 0.05  # ST
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/domain/market/test_price_limit.py::test_get_price_limit_ratio_by_board -v`
Expected: FAIL — `ImportError: cannot import name 'get_price_limit_ratio'`

- [ ] **Step 3: 实现纯函数**

```python
# 追加到 src/domain/market/value_objects/price_limit.py
def get_price_limit_ratio(symbol: str, is_st: bool = False) -> float:
    """根据证券代码与 ST 状态返回涨跌停幅度。

    Args:
        symbol: 证券代码(如 "600000.SH")。
        is_st: 是否 ST/*ST。注:ST 状态需外部数据源,本系统当前默认 False(见 spec 已知限制)。
    """
    if is_st:
        return 0.05
    code, _, market = symbol.partition(".")
    if market == "BJ":          # 北交所
        return 0.30
    if code.startswith("688"):  # 科创板
        return 0.20
    if code.startswith(("300", "301")):  # 创业板
        return 0.20
    return 0.10                 # 主板
```

- [ ] **Step 4: 接入 mock_trade 涨跌停校验**

`place_order` 内，原 `limits = calculate_price_limits(prev_close)` 改为：

```python
                ratio = get_price_limit_ratio(order.ticker)
                limits = calculate_price_limits(prev_close, ratio)
```

文件顶部 import 补 `get_price_limit_ratio`：原 `from src.domain.market.value_objects.price_limit import calculate_price_limits` 改为 `from src.domain.market.value_objects.price_limit import calculate_price_limits, get_price_limit_ratio`。

- [ ] **Step 5: 写端到端测试（创业板 20% 可成交）**

```python
# 追加到 tests/infrastructure/mock/test_mock_trade_adjustment.py
def test_chinext_allows_15pct_move():
    market = MockMarketGateway()
    # 创业板,前一日收盘 10,当日买入价 11.5(涨 15%)。主板 10% 会拒,创业板 20% 应放行。
    market.add_bars("300750.SZ", [
        Bar(symbol="300750.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 2),
            open=10.0, high=10.0, low=10.0, close=10.0, volume=1_000_000),
        Bar(symbol="300750.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 3),
            open=11.5, high=12.0, low=11.0, close=11.5, volume=1_000_000),
    ])
    market.set_current_time(datetime(2024, 1, 3))
    gateway = MockTradeGateway(market, initial_capital=1_000_000.0)

    order = Order(order_id="B2", account_id=MockTradeGateway.DEFAULT_ACCOUNT_ID, ticker="300750.SZ",
                  direction=OrderDirection.BUY, price=11.5, volume=100, type=OrderType.LIMIT)
    gateway.place_order(order)  # 不应抛出涨停拒单
    assert gateway.get_position("300750.SZ").total_volume == 100
```

- [ ] **Step 6: 运行确认通过**

Run: `python -m pytest tests/domain/market/test_price_limit.py tests/infrastructure/mock/test_mock_trade_adjustment.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add src/domain/market/value_objects/price_limit.py src/infrastructure/mock/mock_trade.py tests/domain/market/test_price_limit.py tests/infrastructure/mock/test_mock_trade_adjustment.py
git commit -m "fix(backtest): 按代码前缀识别板块涨跌停幅度 (P1-4)"
```

---

## Task 8: 复权一致性金标准（P0-2 守护）

**Files:**
- Test: `tests/infrastructure/mock/test_mock_trade_adjustment.py`（追加）

- [ ] **Step 1: 写金标准测试**

验证「成交 + 估值同口径 → 建仓不产生虚假浮亏」。修复后该测试通过；若有人退回不复权成交,它会失败。

```python
# 追加到 tests/infrastructure/mock/test_mock_trade_adjustment.py
def test_no_phantom_pnl_from_adjustment_mismatch():
    market = MockMarketGateway()
    # 前复权 close=10(用于估值),unadjusted_close=20(若误用则建仓即虚假浮亏 50%)
    bar = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 1, 3),
              open=10.0, high=10.5, low=9.5, close=10.0, volume=1_000_000, unadjusted_close=20.0)
    market.add_bars("000001.SZ", [bar])
    market.set_current_time(datetime(2024, 1, 3))
    gateway = MockTradeGateway(market, initial_capital=1_000_000.0)

    order = Order(order_id="B3", account_id=MockTradeGateway.DEFAULT_ACCOUNT_ID, ticker="000001.SZ",
                  direction=OrderDirection.BUY, price=10.0, volume=100, type=OrderType.LIMIT)
    gateway.place_order(order)

    pos = gateway.get_position("000001.SZ")
    market_value = pos.total_volume * bar.close          # 前复权估值
    cost_basis = pos.total_volume * pos.average_cost     # 成交成本
    # 同口径下,二者差异仅滑点+费用(<2%);若成交用了 unadjusted_close 则差异约 50%
    assert abs(market_value - cost_basis) < market_value * 0.02
```

- [ ] **Step 2: 运行确认通过**

Run: `python -m pytest tests/infrastructure/mock/test_mock_trade_adjustment.py::test_no_phantom_pnl_from_adjustment_mismatch -v`
Expected: PASS（Task 4 已让成交走前复权;此测试锁死防回归）

- [ ] **Step 3: 提交**

```bash
git add tests/infrastructure/mock/test_mock_trade_adjustment.py
git commit -m "test(backtest): 复权一致性金标准,锁死建仓无虚假浮亏 (P0-2)"
```

---

## Task 9: 全套回归与旧断言更新

**Files:**
- Modify: 运行后确定的失败测试（预计:`test_micro_value_integration.py`、`test_strategy_runner_with_breaker.py`、`test_integration_backtest.py` 等断言旧成交/收益行为的用例）

- [ ] **Step 1: 跑全套，收集失败**

Run: `python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q`
Expected: 多数通过；少数因行为变更而失败——逐一记录。

- [ ] **Step 2: 逐个判定失败性质**

对每个失败用例,判断属于哪类（**这是判断,不是机械改数**）：
- **(a) 修对了**:旧断言锁的是错误行为（如截面策略偷看未来后的收益、`unadjusted_close` 成交价、不含买入费的 `average_cost`)→ 更新断言到新的正确预期。
- **(b) 真回归**:修复引入了非预期的破坏 → 回到对应 Task 修实现,不改测试。

判定线索:若失败值与「前复权成交 / 因子用 T-1 / 成本含买入费 / 标准 Sortino」一致,则属 (a)。

- [ ] **Step 3: 更新 (a) 类断言**

对每个 (a) 类失败,把期望值更新为新口径下手算的正确值,并在该用例加一行注释说明「因 Spec 1 正确性修复更新预期」。

- [ ] **Step 4: 全套转绿**

Run: `python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q`
Expected: all passed。再跑 `ruff check src/` 确认无新增告警。

- [ ] **Step 5: 提交**

```bash
git add tests/
git commit -m "test(backtest): 更新受正确性修复影响的现有用例预期"
```

---

## Task 10: unadjusted_close 字段退役清理

**Files:**
- Modify: `src/domain/market/value_objects/bar.py`（注释)；视依赖扫描结果决定是否删字段

- [ ] **Step 1: 扫描字段消费者**

Run: `grep -rn "unadjusted_close" src/ --include="*.py"`
Expected: 列出所有引用。`mock_trade.py` 的成交/涨跌停引用应已在 Task 4 移除;预计剩余为数据加载层(`mock_market.load_data`、`data_loader`)填充端。

- [ ] **Step 2: 决策并执行**

- 若**仅剩加载层填充、回测路径无消费**:保留字段（实盘账本将来可能用),在 `bar.py` 该字段注释补一行:`# 回测路径已不使用(前复权口径);保留供将来实盘账本对账`。
- 若**已无任何消费者**:从 `Bar` 删除该字段,并同步移除 `mock_market.load_data` 中 `unadjusted_close` 的填充逻辑（87、98 行）。

- [ ] **Step 3: 全套回归确认**

Run: `python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q`
Expected: all passed。

- [ ] **Step 4: 提交**

```bash
git add src/domain/market/value_objects/bar.py
git commit -m "chore(backtest): unadjusted_close 退役标注,回测全程前复权"
```

---

## Spec 覆盖矩阵（自审）

| Spec 需求 | 对应 Task |
|---|---|
| P0-1 截面前视偏差 | Task 1（BarWindow）+ Task 2（截面 runner）+ Task 3（单标的归一） |
| P0-2 复权口径割裂 | Task 4（成交前复权）+ Task 8（一致性金标准）+ Task 10（字段退役） |
| P1-1 成交价语义 | Task 4（用 order.price） |
| P1-2 Sortino 公式 | Task 5 |
| P1-3 买入费用入成本 | Task 6 |
| P1-4 板块涨跌停 | Task 7 |
| 金标准测试网 | Task 2（前视）+ Task 8（复权）+ Task 5/6/7（单元） |
| 回归（更新旧断言） | Task 9 |
| 留路(信息/成交分离) | Task 1（BarWindow 单一职责点） |
| Non-goals(T+0/分红/架构/裁剪) | 不在任何 Task — 已确认排除 |
