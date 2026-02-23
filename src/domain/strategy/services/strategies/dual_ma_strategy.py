from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.strategy.services.base_strategy import BaseStrategy
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection


class DualMaStrategy(BaseStrategy):
    """双均线策略 (Dual Moving Average Strategy)。

    逻辑:
    - 接收 Bar 列表。
    - 计算 MA5 和 MA10。
    - 金叉 (MA5 上穿 MA10) -> BUY。
    - 死叉 (MA5 下穿 MA10) -> SELL。
    """

    @property
    def name(self) -> str:
        return "DualMaStrategy"

    def generate_signals(
        self,
        market_data: dict[str, list[Bar]],
        current_positions: list[Position],
    ) -> list[Signal]:
        """生成交易信号。

        Args:
            market_data: 市场数据。
            current_positions: 当前持仓。

        Returns:
            信号列表。
        """
        signals: list[Signal] = []

        # 将持仓转换为字典以便快速查找: symbol -> Position
        position_map: dict[str, Position] = {
            p.ticker: p for p in current_positions
        }

        for symbol, bars in market_data.items():
            if not bars or len(bars) < 11:
                # 数据不足以计算上一时刻的 MA10 (需要 11 个点: -11~-2)
                continue

            # 1. 计算当前时刻 (T) 的 MA5, MA10
            # 取最后 5 个点
            ma5_curr = self._calculate_ma(bars[-5:], 5)
            # 取最后 10 个点
            ma10_curr = self._calculate_ma(bars[-10:], 10)

            # 2. 计算上一时刻 (T-1) 的 MA5, MA10
            # 取 -6 到 -1 (不含 -1)
            ma5_prev = self._calculate_ma(bars[-6:-1], 5)
            # 取 -11 到 -1 (不含 -1)
            ma10_prev = self._calculate_ma(bars[-11:-1], 10)

            # 3. 判断交叉
            # 金叉: 上一时刻 MA5 <= MA10，当前时刻 MA5 > MA10
            is_golden_cross = (ma5_prev <= ma10_prev) and (ma5_curr > ma10_curr)

            # 死叉: 上一时刻 MA5 >= MA10，当前时刻 MA5 < MA10
            is_death_cross = (ma5_prev >= ma10_prev) and (ma5_curr < ma10_curr)

            if is_golden_cross:
                # 金叉买入
                # 简单策略: 固定买入 100 股 (示例)
                # 实际中可能需要资金管理模块计算
                signals.append(Signal(
                    symbol=symbol,
                    direction=SignalDirection.BUY,
                    target_volume=100,
                    confidence_score=1.0,
                    strategy_name=self.name,
                    reason=f"Golden Cross: MA5({ma5_curr:.2f}) > MA10({ma10_curr:.2f})"
                ))

            elif is_death_cross:
                # 死叉卖出
                # 检查持仓
                position = position_map.get(symbol)
                if position and position.available_volume > 0:
                    signals.append(Signal(
                        symbol=symbol,
                        direction=SignalDirection.SELL,
                        target_volume=position.available_volume,
                        confidence_score=1.0,
                        strategy_name=self.name,
                        reason=f"Death Cross: MA5({ma5_curr:.2f}) < MA10({ma10_curr:.2f})"
                    ))

        return signals

    def _calculate_ma(self, bars_slice: list[Bar], period: int) -> float:
        """纯 Python 计算移动平均线。"""
        if len(bars_slice) != period:
            # 理论上调用前已检查，这里做防御
            return 0.0

        # 使用列表推导式和 sum 计算总和
        total_close = sum(bar.close for bar in bars_slice)
        return total_close / period
