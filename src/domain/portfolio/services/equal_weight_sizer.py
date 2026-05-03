from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.portfolio.interfaces.position_sizer import IPositionSizer
from src.domain.strategy.value_objects.signal import Signal
from src.domain.trade.value_objects.order_direction import OrderDirection


class EqualWeightSizer(IPositionSizer):
    """等权重仓位再平衡器。

    将总资金均分给 N 个标的，每个标的目标市值 = total_asset / n_symbols。
    根据当前持仓偏离度生成买入/卖出信号以达到等权重。
    """

    def __init__(self, n_symbols: int, rebalance_threshold: float = 0.05) -> None:
        self._n_symbols = n_symbols
        self._threshold = rebalance_threshold

    def calculate_target(
        self, signal: Signal, price: float, asset: Asset, position: Position | None
    ) -> int:
        if asset is None or price <= 0 or self._n_symbols <= 0:
            return 0

        target_value_per_symbol = asset.total_asset / self._n_symbols
        current_value = (position.total_volume * price) if position else 0.0
        deviation = (current_value - target_value_per_symbol) / target_value_per_symbol

        if abs(deviation) < self._threshold:
            return 0

        target_volume = int((target_value_per_symbol - current_value) / price)
        target_volume = (target_volume // 100) * 100

        if target_volume > 0 and signal.direction == OrderDirection.SELL:
            target_volume = 0
        elif target_volume < 0 and signal.direction == OrderDirection.BUY:
            target_volume = 0

        if target_volume < 0 and position is not None:
            target_volume = max(target_volume, -position.available_volume)

        return abs(target_volume) if target_volume > 0 else 0

    def calculate_targets(
        self, signals: list[Signal], prices: dict[str, float],
        asset: Asset, positions: list[Position],
    ) -> list:
        from src.domain.portfolio.entities.order_target import OrderTarget
        from src.domain.trade.value_objects.order_direction import OrderDirection

        targets: list[OrderTarget] = []
        pos_map = {p.ticker: p for p in positions}

        sell_signals = [s for s in signals if s.direction == OrderDirection.SELL]
        sell_symbols = {s.symbol for s in sell_signals}

        buy_signals = [s for s in signals if s.direction == OrderDirection.BUY and s.symbol not in sell_symbols]

        if not buy_signals:
            # 目标池为空 → 清仓所有持仓，除了无法卖出的（已被冻结或无可用）
            for pos in positions:
                if pos.available_volume > 0:
                    p = prices.get(pos.ticker, pos.average_cost)
                    # 确定 strategy_name
                    s_name = next((s.strategy_name for s in sell_signals if s.symbol == pos.ticker), "EqualWeightSizer")
                    targets.append(OrderTarget(
                        symbol=pos.ticker, direction=OrderDirection.SELL,
                        volume=pos.available_volume, price=p,
                        strategy_name=s_name
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
                s_name = next((s.strategy_name for s in sell_signals if s.symbol == pos.ticker), "EqualWeightSizer")
                targets.append(OrderTarget(
                    symbol=pos.ticker, direction=OrderDirection.SELL,
                    volume=pos.available_volume, price=price,
                    strategy_name=s_name,
                ))

        return targets
