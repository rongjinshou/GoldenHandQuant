# 半自动 CLI 交易系统 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现半自动 CLI 交易——策略生成信号，终端展示，人工确认后通过 QMT 下单。

**Architecture:** 在现有 DDD 四层架构上增量扩展。Domain 层新增策略注册表；Application 层新增信号编排服务；Interfaces 层新增 CLI 交互入口。复用现有 `resources/trading.yaml` 配置和 `load_trading_config()` 加载逻辑。

**Tech Stack:** Python 3.13+, pytest, ruff, dataclasses, PyYAML, QMT/xtquant

**Spec:** `docs/feat/0509-semi-auto-live-trade/2026-05-09-semi-auto-live-trade-design.md`

---

## 文件结构总览

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/domain/strategy/registry.py` | 策略注册表：名称 → 策略实例工厂 |
| `tests/domain/strategy/test_registry.py` | 注册表单元测试 |
| `src/application/live_signal_service.py` | 信号编排服务：拉行情 → 跑策略 → 计算展示信息 |
| `tests/application/test_live_signal_service.py` | 信号服务单元测试 |
| `src/interfaces/cli/live_trade.py` | CLI 入口：信号展示 + 交互确认 + 下单 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/infrastructure/config/settings.py` | 新增 `LiveTradeSettings`，扩展 `AppSettings` |
| `resources/trading.yaml` | 新增 `live_trade` 配置节 |
| `src/interfaces/cli/run_backtest.py` | 重构为使用 `StrategyRegistry` |

---

## Task 1: 策略注册表

**Files:**
- Create: `src/domain/strategy/registry.py`
- Create: `tests/domain/strategy/test_registry.py`

- [ ] **Step 1: 编写注册表单元测试**

```python
# tests/domain/strategy/test_registry.py
from src.domain.strategy.registry import get_strategy, list_strategies, create_strategy


class TestStrategyRegistry:
    def test_list_strategies_should_return_all_registered(self):
        strategies = list_strategies()
        names = [s.name for s in strategies]
        assert "dual_ma" in names
        assert "micro_value" in names

    def test_get_strategy_dual_ma_should_return_config(self):
        config = get_strategy("dual_ma")
        assert config.name == "dual_ma"
        assert config.strategy_type == "bar"
        assert "DualMa" in config.description

    def test_get_strategy_unknown_should_raise(self):
        import pytest
        with pytest.raises(KeyError, match="unknown_strategy"):
            get_strategy("unknown_strategy")

    def test_create_strategy_dual_ma_should_return_instance(self):
        from src.domain.strategy.services.strategies.dual_ma_strategy import DualMaStrategy
        strategy = create_strategy("dual_ma")
        assert isinstance(strategy, DualMaStrategy)

    def test_create_strategy_micro_value_should_pass_params(self):
        from src.domain.strategy.services.strategies.micro_value_strategy import MicroValueStrategy
        strategy = create_strategy("micro_value", {"top_n": 5})
        assert isinstance(strategy, MicroValueStrategy)
        assert strategy._top_n == 5

    def test_create_strategy_micro_value_default_params(self):
        from src.domain.strategy.services.strategies.micro_value_strategy import MicroValueStrategy
        strategy = create_strategy("micro_value")
        assert isinstance(strategy, MicroValueStrategy)
        assert strategy._top_n == 9
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/domain/strategy/test_registry.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: 实现策略注册表**

```python
# src/domain/strategy/registry.py
from dataclasses import dataclass, field
from typing import Any, Callable

from src.domain.strategy.services.base_strategy import BaseStrategy


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyConfig:
    """策略注册配置。"""
    name: str
    factory: Callable[[dict[str, Any]], BaseStrategy]
    strategy_type: str  # "bar" | "cross_section"
    description: str
    default_params: dict[str, Any] = field(default_factory=dict)


_REGISTRY: dict[str, StrategyConfig] = {}


def _register(config: StrategyConfig) -> None:
    _REGISTRY[config.name] = config


def get_strategy(name: str) -> StrategyConfig:
    """获取策略配置。不存在则抛 KeyError。"""
    if name not in _REGISTRY:
        raise KeyError(f"Unknown strategy: {name}")
    return _REGISTRY[name]


def list_strategies() -> list[StrategyConfig]:
    """列出所有已注册策略。"""
    return list(_REGISTRY.values())


def create_strategy(name: str, params: dict[str, Any] | None = None) -> BaseStrategy:
    """创建策略实例。"""
    config = get_strategy(name)
    merged = {**config.default_params, **(params or {})}
    return config.factory(merged)


# ── 内置策略注册 ──────────────────────────────────────────────

def _build_dual_ma(params: dict[str, Any]) -> BaseStrategy:
    from src.domain.strategy.services.strategies.dual_ma_strategy import DualMaStrategy
    return DualMaStrategy()


def _build_micro_value(params: dict[str, Any]) -> BaseStrategy:
    from src.domain.strategy.services.strategies.micro_value_strategy import MicroValueStrategy
    return MicroValueStrategy(top_n=params.get("top_n", 9))


_register(StrategyConfig(
    name="dual_ma",
    factory=_build_dual_ma,
    strategy_type="bar",
    description="双均线策略 (MA5/MA10 金叉死叉)",
))

_register(StrategyConfig(
    name="micro_value",
    factory=_build_micro_value,
    strategy_type="cross_section",
    description="微盘价值质量增强策略",
    default_params={"top_n": 9},
))
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/domain/strategy/test_registry.py -v
```
Expected: 6 passed

- [ ] **Step 5: 运行 lint**

```bash
ruff check src/domain/strategy/registry.py tests/domain/strategy/test_registry.py
```

- [ ] **Step 6: 提交**

```bash
git add src/domain/strategy/registry.py tests/domain/strategy/test_registry.py
git commit -m "feat: 新增策略注册表 (StrategyRegistry)"
```

---

## Task 2: 扩展配置加载

**Files:**
- Modify: `src/infrastructure/config/settings.py`
- Modify: `resources/trading.yaml`

- [ ] **Step 1: 新增 LiveTradeSettings 数据类**

在 `src/infrastructure/config/settings.py` 末尾追加：

```python
@dataclass(slots=True, kw_only=True)
class LiveTradeSettings:
    strategy: str = "dual_ma"
    symbols: list[str] = field(default_factory=list)
    position_ratio: float = 0.1
    slippage_buy: float = 0.001
    slippage_sell: float = 0.001
    bar_lookback: int = 100
```

并在 `AppSettings` 中新增字段：

```python
live_trade: LiveTradeSettings = field(default_factory=LiveTradeSettings)
```

- [ ] **Step 2: 扩展 load_trading_config**

在 `load_trading_config` 函数中加载 `live_trade` 节：

```python
def load_trading_config(path: str = "resources/trading.yaml") -> AppSettings:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    live_trade_data = data.get("live_trade", {})
    strategy_params = live_trade_data.pop("strategy_params", {})
    live_trade = LiveTradeSettings(**live_trade_data)

    qmt_data = data.get("qmt", {})
    qmt = QmtSettings(**qmt_data)

    return AppSettings(
        qmt=qmt,
        live_trade=live_trade,
    )
```

- [ ] **Step 3: 更新 resources/trading.yaml**

```yaml
qmt:
  userdata_path: "D:\\国金QMT交易端模拟\\userdata_mini"
  session_id: 123456
  account_id: "88888888"
  account_type: "STOCK"

risk:
  policies:
    - "SimpleRiskPolicy"

trading:
  symbols:
    - "600000.SH"
  timeframe: "1d"
  bar_lookback: 100

live_trade:
  strategy: "dual_ma"
  symbols:
    - "600000.SH"
    - "000001.SZ"
  position_ratio: 0.1
  slippage_buy: 0.001
  slippage_sell: 0.001
  bar_lookback: 100
  # strategy_params:
  #   top_n: 9
```

- [ ] **Step 4: 运行现有测试确认不破坏**

```bash
python -m pytest tests/infrastructure/config/test_settings.py -v
```

- [ ] **Step 5: 运行全量测试**

```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q
```
Expected: all pass

- [ ] **Step 6: 提交**

```bash
git add src/infrastructure/config/settings.py resources/trading.yaml
git commit -m "feat: 扩展配置加载支持 live_trade 设置"
```

---

## Task 3: 信号展示值对象 + 信号编排服务

**Files:**
- Create: `src/application/live_signal_service.py`
- Create: `tests/application/test_live_signal_service.py`

- [ ] **Step 1: 编写信号服务单元测试**

```python
# tests/application/test_live_signal_service.py
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.application.live_signal_service import LiveSignalService, SignalDisplay
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection


def _make_bars(symbol: str, prices: list[float]) -> list[Bar]:
    bars = []
    base = datetime.now() - timedelta(days=len(prices))
    for i, p in enumerate(prices):
        bars.append(Bar(
            symbol=symbol, timeframe=Timeframe.DAY_1,
            timestamp=base + timedelta(days=i),
            open=p, high=p, low=p, close=p, volume=1000,
        ))
    return bars


class TestLiveSignalService:
    def _make_service(self) -> tuple[LiveSignalService, MagicMock, MagicMock, MagicMock]:
        market_gw = MagicMock()
        account_gw = MagicMock()
        trade_gw = MagicMock()

        account_gw.get_asset.return_value = Asset(
            account_id="test_acc", total_asset=1_000_000, available_cash=500_000,
        )
        account_gw.get_positions.return_value = []

        service = LiveSignalService(
            market_gateway=market_gw,
            account_gateway=account_gw,
            trade_gateway=trade_gw,
        )
        return service, market_gw, account_gw, trade_gw

    def test_scan_bar_strategy_should_return_signal_displays(self):
        service, market_gw, _, _ = self._make_service()
        market_gw.get_recent_bars.return_value = _make_bars("600000.SH", [10]*10 + [20])

        displays = service.scan(strategy_name="dual_ma", symbols=["600000.SH"])

        assert len(displays) == 1
        d = displays[0]
        assert d.symbol == "600000.SH"
        assert d.direction == SignalDirection.BUY
        assert d.current_price == 20.0
        assert d.suggested_volume > 0
        assert d.required_capital > 0
        assert "Golden Cross" in d.reason

    def test_scan_no_signals_should_return_empty(self):
        service, market_gw, _, _ = self._make_service()
        # 平盘行情，不会触发交叉
        market_gw.get_recent_bars.return_value = _make_bars("600000.SH", [10]*20)

        displays = service.scan(strategy_name="dual_ma", symbols=["600000.SH"])

        assert len(displays) == 0

    def test_scan_insufficient_data_should_skip(self):
        service, market_gw, _, _ = self._make_service()
        market_gw.get_recent_bars.return_value = _make_bars("600000.SH", [10]*5)

        displays = service.scan(strategy_name="dual_ma", symbols=["600000.SH"])

        assert len(displays) == 0

    def test_scan_no_market_data_should_skip(self):
        service, market_gw, _, _ = self._make_service()
        market_gw.get_recent_bars.return_value = []

        displays = service.scan(strategy_name="dual_ma", symbols=["600000.SH"])

        assert len(displays) == 0

    def test_place_confirmed_orders_should_call_trade_gateway(self):
        service, _, _, trade_gw = self._make_service()
        trade_gw.place_order.return_value = "order_123"

        display = SignalDisplay(
            symbol="600000.SH", direction=SignalDirection.BUY,
            current_price=12.50, suggested_price=12.52,
            suggested_volume=500, required_capital=6260.0,
            reason="Golden Cross", strategy_name="DualMaStrategy",
            confidence_score=1.0,
        )

        results = service.place_confirmed_orders([display])

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].order_id == "order_123"
        trade_gw.place_order.assert_called_once()

    def test_place_confirmed_orders_failure_should_return_error(self):
        service, _, _, trade_gw = self._make_service()
        from src.domain.trade.exceptions import OrderSubmitError
        trade_gw.place_order.side_effect = OrderSubmitError("QMT error")

        display = SignalDisplay(
            symbol="600000.SH", direction=SignalDirection.BUY,
            current_price=12.50, suggested_price=12.52,
            suggested_volume=500, required_capital=6260.0,
            reason="test", strategy_name="test", confidence_score=1.0,
        )

        results = service.place_confirmed_orders([display])

        assert len(results) == 1
        assert results[0].success is False
        assert "QMT error" in results[0].error_message
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/application/test_live_signal_service.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: 实现信号展示值对象和信号编排服务**

```python
# src/application/live_signal_service.py
import logging
from dataclasses import dataclass
from uuid import uuid4

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway
from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.portfolio.interfaces.position_sizer import IPositionSizer
from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer
from src.domain.strategy.registry import create_strategy, get_strategy
from src.domain.strategy.services.base_strategy import BaseStrategy
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.trade.entities.order import Order
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.trade.interfaces.gateways.trade_gateway import ITradeGateway
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_status import OrderStatus
from src.domain.trade.value_objects.order_type import OrderType

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class SignalDisplay:
    """信号展示模型 — 包含 CLI 表格所需的全部字段。"""
    symbol: str
    direction: SignalDirection
    current_price: float
    suggested_price: float
    suggested_volume: int
    required_capital: float
    reason: str
    strategy_name: str
    confidence_score: float


@dataclass(slots=True, kw_only=True)
class OrderResult:
    """下单结果。"""
    symbol: str
    direction: SignalDirection
    success: bool
    order_id: str = ""
    error_message: str = ""


class LiveSignalService:
    """半自动交易信号编排服务。

    流程: 拉行情 → 跑策略 → 计算仓位 → 产出 SignalDisplay 列表。
    """

    def __init__(
        self,
        market_gateway: IMarketGateway,
        account_gateway: IAccountGateway,
        trade_gateway: ITradeGateway,
        sizer: IPositionSizer | None = None,
        slippage_buy: float = 0.001,
        slippage_sell: float = 0.001,
        bar_lookback: int = 100,
    ) -> None:
        self.market_gateway = market_gateway
        self.account_gateway = account_gateway
        self.trade_gateway = trade_gateway
        self.sizer = sizer or FixedRatioSizer(ratio=0.1)
        self.slippage_buy = slippage_buy
        self.slippage_sell = slippage_sell
        self.bar_lookback = bar_lookback

    def scan(self, strategy_name: str, symbols: list[str]) -> list[SignalDisplay]:
        """扫描信号并返回展示列表。"""
        strategy = create_strategy(strategy_name)
        config = get_strategy(strategy_name)

        asset = self.account_gateway.get_asset()
        if asset is None:
            logger.error("无法获取账户资产")
            return []

        positions = self.account_gateway.get_positions()

        if config.strategy_type == "cross_section":
            return self._scan_cross_sectional(
                strategy, symbols, positions, asset,
            )
        return self._scan_bar(strategy, symbols, positions, asset)

    def _scan_bar(
        self,
        strategy: BaseStrategy,
        symbols: list[str],
        positions: list[Position],
        asset: Asset,
    ) -> list[SignalDisplay]:
        market_data: dict[str, list[Bar]] = {}
        for symbol in symbols:
            bars = self.market_gateway.get_recent_bars(
                symbol, timeframe=Timeframe.DAY_1, limit=self.bar_lookback,
            )
            if bars:
                market_data[symbol] = bars

        if not market_data:
            return []

        signals = strategy.generate_signals(market_data, positions)
        return self._signals_to_displays(signals, market_data, positions, asset)

    def _scan_cross_sectional(
        self,
        strategy: BaseStrategy,
        symbols: list[str],
        positions: list[Position],
        asset: Asset,
    ) -> list[SignalDisplay]:
        """截面策略需要 StockSnapshot，暂不支持实时扫描。"""
        logger.warning(
            "截面策略 (%s) 需要全市场基本面数据，半自动模式暂不支持实时扫描。"
            "请使用 bar 类型策略（如 dual_ma）。",
            strategy.name,
        )
        return []

    def _signals_to_displays(
        self,
        signals: list[Signal],
        market_data: dict[str, list[Bar]],
        positions: list[Position],
        asset: Asset,
    ) -> list[SignalDisplay]:
        position_map = {p.ticker: p for p in positions}
        displays: list[SignalDisplay] = []

        for signal in signals:
            bars = market_data.get(signal.symbol)
            if not bars:
                continue

            current_price = bars[-1].close
            slippage = (
                self.slippage_buy
                if signal.direction == SignalDirection.BUY
                else -self.slippage_sell
            )
            suggested_price = round(current_price * (1 + slippage), 2)

            position = position_map.get(signal.symbol)
            volume = self.sizer.calculate_target(
                signal, current_price, asset, position,
            )
            volume = int(max(volume, 0))

            if volume <= 0:
                continue

            required_capital = round(suggested_price * volume, 2)

            displays.append(SignalDisplay(
                symbol=signal.symbol,
                direction=signal.direction,
                current_price=current_price,
                suggested_price=suggested_price,
                suggested_volume=volume,
                required_capital=required_capital,
                reason=signal.reason,
                strategy_name=signal.strategy_name,
                confidence_score=signal.confidence_score,
            ))

        return displays

    def place_confirmed_orders(self, displays: list[SignalDisplay]) -> list[OrderResult]:
        """对用户确认的信号执行下单。"""
        results: list[OrderResult] = []

        for display in displays:
            order_direction = (
                OrderDirection.BUY
                if display.direction == SignalDirection.BUY
                else OrderDirection.SELL
            )

            order = Order(
                order_id=str(uuid4()),
                account_id="",
                ticker=display.symbol,
                direction=order_direction,
                price=display.suggested_price,
                volume=display.suggested_volume,
                type=OrderType.LIMIT,
                status=OrderStatus.CREATED,
            )

            try:
                order_id = self.trade_gateway.place_order(order)
                results.append(OrderResult(
                    symbol=display.symbol,
                    direction=display.direction,
                    success=True,
                    order_id=str(order_id),
                ))
            except OrderSubmitError as e:
                results.append(OrderResult(
                    symbol=display.symbol,
                    direction=display.direction,
                    success=False,
                    error_message=str(e),
                ))
            except Exception as e:
                logger.error("下单异常: %s", e, exc_info=True)
                results.append(OrderResult(
                    symbol=display.symbol,
                    direction=display.direction,
                    success=False,
                    error_message=str(e),
                ))

        return results
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/application/test_live_signal_service.py -v
```
Expected: 6 passed

- [ ] **Step 5: 运行 lint**

```bash
ruff check src/application/live_signal_service.py tests/application/test_live_signal_service.py
```

- [ ] **Step 6: 提交**

```bash
git add src/application/live_signal_service.py tests/application/test_live_signal_service.py
git commit -m "feat: 新增信号编排服务 (LiveSignalService)"
```

---

## Task 4: CLI 半自动交易入口

**Files:**
- Create: `src/interfaces/cli/live_trade.py`

- [ ] **Step 1: 实现 CLI 入口**

```python
# src/interfaces/cli/live_trade.py
"""
半自动 CLI 交易入口。

使用方式:
    python -m src.interfaces.cli.live_trade --strategy dual_ma --symbols 600000.SH,000001.SZ
    python -m src.interfaces.cli.live_trade  # 使用 resources/trading.yaml 默认配置
"""

import argparse
import logging
import sys
from datetime import datetime

from src.application.live_signal_service import LiveSignalService, SignalDisplay, OrderResult
from src.domain.strategy.registry import list_strategies, get_strategy
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.infrastructure.config.settings import load_trading_config

logger = logging.getLogger(__name__)

# ── 颜色常量 ──────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QuantFlow 半自动交易")
    parser.add_argument(
        "--strategy", "-s", type=str, default=None,
        help="策略名称 (如 dual_ma, micro_value)",
    )
    parser.add_argument(
        "--symbols", type=str, default=None,
        help="标的列表，逗号分隔 (如 600000.SH,000001.SZ)",
    )
    parser.add_argument(
        "--config", type=str, default="resources/trading.yaml",
        help="配置文件路径",
    )
    return parser.parse_args()


def print_header() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print()
    print(f"{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN}  QuantFlow 半自动交易信号{' '*40}{now}{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}")


def print_signal_table(displays: list[SignalDisplay]) -> None:
    """打印信号表格。"""
    if not displays:
        print(f"\n{YELLOW}当前无交易信号。{RESET}\n")
        return

    # 表头
    header = (
        f"{'序号':>4}  {'标的':<12} {'方向':<6} {'当前价':>8} {'挂单价':>8} "
        f"{'数量':>6} {'所需资金':>10} {'触发原因'}"
    )
    print(f"\n{BOLD}{header}{RESET}")
    print("-" * 80)

    for i, d in enumerate(displays, 1):
        dir_color = GREEN if d.direction == SignalDirection.BUY else RED
        dir_text = "BUY " if d.direction == SignalDirection.BUY else "SELL"

        print(
            f"{i:>4}  {d.symbol:<12} {dir_color}{dir_text:<6}{RESET} "
            f"{d.current_price:>8.2f} {d.suggested_price:>8.2f} "
            f"{d.suggested_volume:>6} {d.required_capital:>10,.0f} "
            f"{d.reason}"
        )

    print("-" * 80)


def print_status_bar(displays: list[SignalDisplay], asset, position_count: int) -> None:
    """打印底部状态栏。"""
    if displays:
        strategy_name = displays[0].strategy_name
    else:
        strategy_name = "-"
    available = asset.available_cash if asset else 0
    print(
        f"{CYAN}策略: {strategy_name}  |  "
        f"可用资金: {available:,.0f}  |  "
        f"当前持仓: {position_count} 只{RESET}"
    )


def confirm_single(display: SignalDisplay) -> bool:
    """单笔二次确认。"""
    dir_text = "买入" if display.direction == SignalDirection.BUY else "卖出"
    print(
        f"\n{YELLOW}⚠ 确认下单: {dir_text} {display.symbol} "
        f"{display.suggested_volume}股 @ {display.suggested_price:.2f} "
        f"(约 ¥{display.required_capital:,.0f})?{RESET} [y/N]: ",
        end="",
    )
    answer = input().strip().lower()
    return answer == "y"


def print_order_results(results: list[OrderResult]) -> None:
    """打印下单结果。"""
    print(f"\n{BOLD}{'─'*40}{RESET}")
    for r in results:
        if r.success:
            print(f"{GREEN}✅ {r.symbol} {r.direction.value} 订单已提交: {r.order_id}{RESET}")
        else:
            print(f"{RED}❌ {r.symbol} {r.direction.value} 下单失败: {r.error_message}{RESET}")
    print(f"{BOLD}{'─'*40}{RESET}\n")


def main() -> None:
    args = parse_args()

    # 加载配置
    try:
        settings = load_trading_config(args.config)
    except FileNotFoundError:
        print(f"{RED}配置文件未找到: {args.config}{RESET}")
        sys.exit(1)

    lt = settings.live_trade
    strategy_name = args.strategy or lt.strategy
    symbols = args.symbols.split(",") if args.symbols else lt.symbols

    if not symbols:
        print(f"{RED}未指定标的列表。请通过 --symbols 或配置文件指定。{RESET}")
        sys.exit(1)

    # 显示策略信息
    try:
        config = get_strategy(strategy_name)
    except KeyError:
        available = [s.name for s in list_strategies()]
        print(f"{RED}未知策略: {strategy_name}。可选: {', '.join(available)}{RESET}")
        sys.exit(1)

    print_header()
    print(f"\n{BOLD}加载策略:{RESET} {config.description}")
    print(f"{BOLD}标的列表:{RESET} {', '.join(symbols)}")
    print(f"{BOLD}策略类型:{RESET} {config.strategy_type}")

    if config.strategy_type == "cross_section":
        print(f"\n{YELLOW}截面策略需要全市场基本面数据，半自动模式暂不支持。{RESET}")
        print(f"{YELLOW}请使用 bar 类型策略（如 dual_ma）。{RESET}")
        sys.exit(0)

    # 初始化基础设施
    from src.infrastructure.gateway.qmt_market import QmtMarketGateway
    from src.infrastructure.gateway.qmt_trade import QmtTradeGateway

    qmt = settings.qmt
    if not qmt.userdata_path:
        print(f"{RED}QMT 路径未配置。请在 {args.config} 中设置 qmt.userdata_path。{RESET}")
        sys.exit(1)

    print(f"\n{BOLD}连接 QMT...{RESET}")
    try:
        market_gw = QmtMarketGateway()
        trade_gw = QmtTradeGateway(
            path=qmt.userdata_path,
            session_id=qmt.session_id,
            account_id=qmt.account_id,
            account_type=qmt.account_type,
        )
        account_gw = trade_gw  # QmtTradeGateway 同时实现 IAccountGateway
    except Exception as e:
        print(f"{RED}QMT 连接失败: {e}{RESET}")
        sys.exit(1)

    # 初始化信号服务
    service = LiveSignalService(
        market_gateway=market_gw,
        account_gateway=account_gw,
        trade_gateway=trade_gw,
        slippage_buy=lt.slippage_buy,
        slippage_sell=lt.slippage_sell,
        bar_lookback=lt.bar_lookback,
    )

    # 获取账户信息
    asset = account_gw.get_asset()
    positions = account_gw.get_positions()

    # 扫描信号
    print(f"\n{BOLD}正在扫描信号...{RESET}")
    displays = service.scan(strategy_name=strategy_name, symbols=symbols)

    # 展示
    print_signal_table(displays)
    print_status_bar(displays, asset, len(positions))

    if not displays:
        return

    # 交互确认
    print(f"\n{BOLD}输入序号确认下单 (逗号分隔, a=全部, q=退出):{RESET} ", end="")
    choice = input().strip().lower()

    if choice == "q":
        print(f"{YELLOW}已退出，未执行任何交易。{RESET}")
        return

    if choice == "a":
        selected = displays
    else:
        try:
            indices = [int(x.strip()) for x in choice.split(",")]
            selected = [displays[i - 1] for i in indices if 1 <= i <= len(displays)]
        except (ValueError, IndexError):
            print(f"{RED}输入无效。{RESET}")
            return

    if not selected:
        print(f"{YELLOW}未选择任何信号。{RESET}")
        return

    # 逐笔二次确认
    confirmed: list[SignalDisplay] = []
    for d in selected:
        if confirm_single(d):
            confirmed.append(d)

    if not confirmed:
        print(f"{YELLOW}未确认任何订单。{RESET}")
        return

    # 下单
    print(f"\n{BOLD}正在下单...{RESET}")
    results = service.place_confirmed_orders(confirmed)
    print_order_results(results)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行 lint**

```bash
ruff check src/interfaces/cli/live_trade.py
```

- [ ] **Step 3: 运行全量测试确认不破坏**

```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q
```
Expected: all pass

- [ ] **Step 4: 提交**

```bash
git add src/interfaces/cli/live_trade.py
git commit -m "feat: 新增半自动 CLI 交易入口 (live_trade)"
```

---

## Task 5: 重构 run_backtest 使用策略注册表

**Files:**
- Modify: `src/interfaces/cli/run_backtest.py`

- [ ] **Step 1: 重构策略初始化逻辑**

将 `run_backtest.py` 中 74-118 行的 if/else 策略选择逻辑替换为使用 `StrategyRegistry`：

```python
# 替换原来的:
#   if strategy_name == "MicroValueStrategy":
#       ...
#   else:
#       strategy = DualMaStrategy()
# 改为:

from src.domain.strategy.registry import create_strategy, get_strategy

# 映射配置名到注册表名
STRATEGY_NAME_MAP = {
    "DualMaStrategy": "dual_ma",
    "MicroValueStrategy": "micro_value",
}
registry_name = STRATEGY_NAME_MAP.get(strategy_name, strategy_name.lower())

try:
    config = get_strategy(registry_name)
except KeyError:
    print(f"Unknown strategy: {strategy_name}, falling back to dual_ma")
    registry_name = "dual_ma"
    config = get_strategy(registry_name)

strategy_params = {}
if hasattr(settings, 'strategy') and hasattr(settings.strategy, 'top_n'):
    strategy_params["top_n"] = settings.strategy.top_n

strategy = create_strategy(registry_name, strategy_params)
print(f"Strategy: {config.description}")
```

同时保留 `fundamental_registry` 的初始化逻辑（截面策略需要），但改为基于 `config.strategy_type` 判断：

```python
fundamental_registry = None
stock_universe: list[str] = []
if config.strategy_type == "cross_section":
    from src.domain.market.services.fundamental_registry import FundamentalRegistry
    fundamental_registry = FundamentalRegistry()
    # ... 原有的基本面数据加载逻辑不变 ...
```

- [ ] **Step 2: 运行现有回测测试**

```bash
python -m pytest tests/application/test_backtest_app.py -v
```
Expected: all pass

- [ ] **Step 3: 运行全量测试**

```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q
```
Expected: all pass

- [ ] **Step 4: 提交**

```bash
git add src/interfaces/cli/run_backtest.py
git commit -m "refactor: run_backtest 使用策略注册表替代 if/else"
```

---

## Task 6: 集成验证

- [ ] **Step 1: 运行全部测试**

```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -v
```
Expected: all pass

- [ ] **Step 2: 运行 ruff lint**

```bash
ruff check src/
```
Expected: no errors

- [ ] **Step 3: 干运行 CLI 确认参数解析正常**

```bash
python -m src.interfaces.cli.live_trade --help
```
Expected: 显示帮助信息，包含 --strategy, --symbols, --config 参数说明

- [ ] **Step 4: 干运行 CLI 确认策略列表**

```bash
python -c "from src.domain.strategy.registry import list_strategies; [print(f'{s.name}: {s.description}') for s in list_strategies()]"
```
Expected:
```
dual_ma: 双均线策略 (MA5/MA10 金叉死叉)
micro_value: 微盘价值质量增强策略
```
