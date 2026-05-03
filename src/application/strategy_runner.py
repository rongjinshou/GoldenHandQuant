from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.suspension import StockStatusRegistry
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.portfolio.entities.order_target import OrderTarget
from src.domain.portfolio.interfaces.position_sizer import IPositionSizer
from src.domain.risk.services.risk_policies.hard_stop_loss_policy import HardStopLossPolicy
from src.domain.risk.services.risk_policies.limit_up_break_policy import LimitUpBreakPolicy
from src.domain.risk.services.risk_signal_generator import RiskSignalGenerator
from src.domain.risk.services.system_risk_gate import SystemRiskGate
from src.domain.strategy.services.base_strategy import BaseStrategy
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.trade.interfaces.gateways.trade_gateway import ITradeGateway
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.infrastructure.ml_engine.feature_pipeline import FeaturePipeline


@dataclass(slots=True, kw_only=True)
class DayContext:
    current_time: datetime
    symbols: list[str]
    base_timeframe: Timeframe


class StrategyRunner(ABC):
    @abstractmethod
    def evaluate(self, context: DayContext) -> tuple[list[OrderTarget], dict[str, float]]:
        """执行策略并返回当天的目标订单和收盘价。

        Returns:
            targets: 目标订单列表
            close_prices: 当天各标的的收盘价，用于快照估值
        """
        pass

class SingleStrategyRunner(StrategyRunner):
    LOOKBACK_WINDOW = 101

    def __init__(
        self,
        strategy: BaseStrategy,
        sizer: IPositionSizer,
        market_gateway: IMarketGateway,
        trade_gateway: ITradeGateway,
        status_registry: StockStatusRegistry | None = None,
    ):
        self.strategy = strategy
        self.sizer = sizer
        self.market_gateway = market_gateway
        self.trade_gateway = trade_gateway
        self.status_registry = status_registry

    def evaluate(self, context: DayContext) -> tuple[list[OrderTarget], dict[str, float]]:
        strategy_market_data: dict[str, list[Bar]] = {}
        execution_prices: dict[str, float] = {}
        current_prices: dict[str, float] = {}

        for symbol in context.symbols:
            all_bars = self.market_gateway.get_recent_bars(symbol, context.base_timeframe, self.LOOKBACK_WINDOW)
            if not all_bars:
                continue
            if len(all_bars) >= 2:
                strategy_market_data[symbol] = all_bars[:-1]
            current_bar = all_bars[-1]
            execution_prices[symbol] = current_bar.open
            current_prices[symbol] = current_bar.close

        current_positions = self.trade_gateway.get_positions()
        signals = self.strategy.generate_signals(strategy_market_data, current_positions)

        position_map = {p.ticker: p for p in current_positions}
        targets: list[OrderTarget] = []
        asset = self.trade_gateway.get_asset()
        if asset is None:
            raise ValueError("Asset not available from trade gateway.")

        for signal in signals:
            if self.status_registry and not self.status_registry.is_tradable(signal.symbol, context.current_time):
                continue
            price = execution_prices.get(signal.symbol)
            if not price or price <= 0:
                continue

            position = position_map.get(signal.symbol)
            volume = self.sizer.calculate_target(signal, price, asset, position)

            if volume > 0:
                targets.append(OrderTarget(
                    symbol=signal.symbol,
                    direction=OrderDirection(signal.direction.value),
                    volume=volume,
                    price=price,
                    strategy_name=signal.strategy_name
                ))

        return targets, current_prices

class CrossSectionalStrategyRunner(StrategyRunner):
    def __init__(
        self,
        strategy: CrossSectionalStrategy,
        sizer: IPositionSizer,
        market_gateway: IMarketGateway,
        trade_gateway: ITradeGateway,
        fundamental_registry=None,
        index_symbol: str = "000852.SH",
        risk_settings=None,
    ):
        self.strategy = strategy
        self.sizer = sizer
        self.market_gateway = market_gateway
        self.trade_gateway = trade_gateway
        self.fundamental_registry = fundamental_registry

        if risk_settings and getattr(risk_settings, "system_gate", {}).get("index_symbol"):
            self.index_symbol = risk_settings.system_gate.get("index_symbol")
        else:
            self.index_symbol = index_symbol

        self.system_gate = SystemRiskGate()

        max_loss = 0.03
        if risk_settings and getattr(risk_settings, "stop_loss", {}).get("max_loss_ratio"):
            max_loss = risk_settings.stop_loss.get("max_loss_ratio")

        self.risk_signal_gen = RiskSignalGenerator([
            LimitUpBreakPolicy(),
            HardStopLossPolicy(max_loss_ratio=max_loss),
        ])

    def evaluate(self, context: DayContext) -> tuple[list[OrderTarget], dict[str, float]]:
        # Inject index data to system_gate
        index_bars = self.market_gateway.get_recent_bars(self.index_symbol, context.base_timeframe, 100)
        if index_bars:
            self.system_gate.set_index_data(index_bars)

        bars: dict[str, Bar] = {}
        for sym in context.symbols:
            recent = self.market_gateway.get_recent_bars(sym, context.base_timeframe, 1)
            if recent:
                bars[sym] = recent[-1]

        universe = []
        if self.fundamental_registry:
            universe = FeaturePipeline.build_cross_section(
                context.current_time, bars, self.fundamental_registry
            )

        gate = self.system_gate.check_gate(context.current_time)

        current_positions = self.trade_gateway.get_positions()
        strategy_signals = self.strategy.generate_cross_sectional_signals(
            universe, current_positions, context.current_time
        )
        risk_signals = self.risk_signal_gen.evaluate(current_positions, bars)
        all_signals = strategy_signals + risk_signals

        if not gate.pass_buy:
            all_signals = [s for s in all_signals if s.direction != SignalDirection.BUY]

        prices = {sym: bar.open for sym, bar in bars.items()}
        asset = self.trade_gateway.get_asset()
        if asset is None:
            raise ValueError("Asset not available from trade gateway.")

        targets = self.sizer.calculate_targets(
            all_signals, prices, asset, current_positions
        )

        targets.sort(key=lambda t: 0 if t.direction == OrderDirection.SELL else 1)

        current_prices = {sym: bar.close for sym, bar in bars.items()}
        return targets, current_prices
