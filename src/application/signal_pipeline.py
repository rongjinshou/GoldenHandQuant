import logging

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.portfolio.entities.order_target import OrderTarget
from src.domain.portfolio.interfaces.position_sizer import IPositionSizer
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.trade.value_objects.order_direction import OrderDirection

logger = logging.getLogger(__name__)

# 默认数量（当未注入 IPositionSizer 时的回退值）
_DEFAULT_VOLUME = 100


class SignalPipeline:
    """信号生成管线。

    聚合多策略信号，执行去重、置信度过滤、冲突解决。
    支持通过 IPositionSizer 计算目标仓位，消除 volume=100 硬编码。
    """

    def __init__(
        self,
        min_confidence: float = 0.6,
        position_sizer: IPositionSizer | None = None,
    ) -> None:
        self._min_confidence = min_confidence
        self._position_sizer = position_sizer

    def deduplicate(self, signals: list[Signal]) -> list[Signal]:
        """信号去重: 同一标的多策略信号取置信度最高的。"""
        best: dict[str, Signal] = {}
        for signal in signals:
            key = signal.symbol
            existing = best.get(key)
            if existing is None or signal.confidence_score > existing.confidence_score:
                best[key] = signal
        return list(best.values())

    def filter_by_confidence(self, signals: list[Signal]) -> list[Signal]:
        """过滤低于置信度阈值的信号。"""
        return [s for s in signals if s.confidence_score >= self._min_confidence]

    def resolve_conflicts(self, signals: list[Signal]) -> list[Signal]:
        """解决 BUY/SELL 冲突: 同一标的同时有 BUY 和 SELL 时优先 SELL。"""
        by_symbol: dict[str, list[Signal]] = {}
        for signal in signals:
            by_symbol.setdefault(signal.symbol, []).append(signal)

        resolved: list[Signal] = []
        for symbol, symbol_signals in by_symbol.items():
            has_sell = any(s.direction == SignalDirection.SELL for s in symbol_signals)
            if has_sell:
                sell_signals = [s for s in symbol_signals if s.direction == SignalDirection.SELL]
                resolved.append(max(sell_signals, key=lambda s: s.confidence_score))
            else:
                resolved.append(max(symbol_signals, key=lambda s: s.confidence_score))

        return resolved

    def signals_to_targets(
        self,
        signals: list[Signal],
        prices: dict[str, float],
        strategy_name: str = "",
        asset: Asset | None = None,
        positions: list[Position] | None = None,
    ) -> list[OrderTarget]:
        """将信号转换为订单目标。

        当注入了 IPositionSizer 且传入 asset 时，使用 sizer 计算目标仓位；
        否则回退到默认数量（_DEFAULT_VOLUME=100）。

        Args:
            signals: 过滤后的策略信号列表。
            prices: symbol -> 当前价格映射。
            strategy_name: 默认策略名称（当信号未指定时使用）。
            asset: 账户资产（供 IPositionSizer 计算仓位）。
            positions: 当前持仓列表（供 IPositionSizer 计算仓位）。

        Returns:
            订单目标列表。
        """
        targets: list[OrderTarget] = []
        position_map: dict[str, Position] = {}
        if positions:
            position_map = {p.ticker: p for p in positions}

        for signal in signals:
            price = prices.get(signal.symbol)
            if not price or price <= 0:
                continue
            direction = OrderDirection(signal.direction.value)

            volume = _DEFAULT_VOLUME
            if self._position_sizer and asset is not None:
                position = position_map.get(signal.symbol)
                volume = int(self._position_sizer.calculate_target(
                    signal, price, asset, position,
                ))
                if volume <= 0:
                    continue

            targets.append(OrderTarget(
                symbol=signal.symbol,
                direction=direction,
                volume=volume,
                price=price,
                strategy_name=signal.strategy_name or strategy_name,
            ))
        return targets

    def process(
        self,
        signals: list[Signal],
        prices: dict[str, float],
        asset: Asset | None = None,
        positions: list[Position] | None = None,
    ) -> list[OrderTarget]:
        """完整处理流程: 去重 -> 过滤 -> 冲突解决 -> 转换。

        Args:
            signals: 多策略聚合信号列表。
            prices: symbol -> 当前价格映射。
            asset: 账户资产（可选，用于 IPositionSizer 仓位计算）。
            positions: 当前持仓列表（可选，用于 IPositionSizer 仓位计算）。
        """
        deduped = self.deduplicate(signals)
        filtered = self.filter_by_confidence(deduped)
        resolved = self.resolve_conflicts(filtered)
        return self.signals_to_targets(
            resolved, prices, asset=asset, positions=positions,
        )
