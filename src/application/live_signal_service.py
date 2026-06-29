import logging
from dataclasses import dataclass
from datetime import datetime
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

    流程: 拉行情 -> 跑策略 -> 计算仓位 -> 产出 SignalDisplay 列表。
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
        fundamental_registry=None,
    ) -> None:
        self.market_gateway = market_gateway
        self.account_gateway = account_gateway
        self.trade_gateway = trade_gateway
        self.sizer = sizer or FixedRatioSizer(ratio=0.1)
        self.slippage_buy = slippage_buy
        self.slippage_sell = slippage_sell
        self.bar_lookback = bar_lookback
        self.fundamental_registry = fundamental_registry

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
        """时序(bar)策略扫描 —— 决策与回测同源, 执行/展示按 live 语义。

        刻意未并入回测的 SingleStrategyRunner.evaluate(架构重构 0628 剩余债, 经评估
        不强行统一, 否则回退 live 质量): 决策(strategy.generate_signals + sizer)已
        与回测同源, 截面那种"漏趋势闸/基本面"的决策分叉在此不存在; 差异只在执行/
        展示层且是 live 正当差异 ——
          · 限价用 bars[-1].close±slippage(当前价), 非 runner 的 T 日开盘(回测产物,
            T-1 决策/T 开盘成交); 塞进 live 等于按错价下单。
          · 保留 per-signal confidence/reason: 供半自动复核展示, 且
            AutoTradeAppService._select 的 min_confidence 闸依赖之 —— 走 runner 会被
            抹成 1.0/"决策核心", 闸语义失效。
        触发统一: 任一 bar 策略成为 live 候选(dual_ma 现非主线), 届时让
        SingleStrategyRunner 透出 signals 以保住 confidence/reason 再并轨。
        设计: docs/feat/0628-backtest-live-unification/。
        """
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

    def _scan_cross_sectional(self, strategy, symbols, positions, asset):
        """截面策略扫描 — 统一走决策核心 CrossSectionalStrategyRunner。

        positions/asset 保留签名兼容(分流调用方传入), runner 内部自取真账户。
        """
        from src.application.strategy_runner import CrossSectionalStrategyRunner, DayContext
        runner = CrossSectionalStrategyRunner(
            strategy=strategy, sizer=self.sizer,
            market_gateway=self.market_gateway, trade_gateway=self.trade_gateway,
            fundamental_registry=self.fundamental_registry,
        )
        targets, prices = runner.evaluate(DayContext(
            current_time=datetime.now(), symbols=symbols, base_timeframe=Timeframe.DAY_1,
        ))
        return [self._target_to_display(t, prices) for t in targets]

    def _target_to_display(self, t, prices):
        current = prices.get(t.symbol, t.price)
        return SignalDisplay(
            symbol=t.symbol,
            direction=SignalDirection(t.direction.value),
            current_price=current,
            suggested_price=t.price,
            suggested_volume=t.volume,
            required_capital=round(t.price * t.volume, 2),
            reason=f"决策核心({t.strategy_name})",
            strategy_name=t.strategy_name,
            confidence_score=1.0,
        )

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
