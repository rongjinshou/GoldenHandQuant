from datetime import datetime

from src.domain.account.entities.position import Position
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.domain.strategy.services.filters.filter_new_listing import filter_new_listing
from src.domain.strategy.services.filters.filter_penny_stock import filter_penny_stock
from src.domain.strategy.services.filters.filter_quality import filter_quality
from src.domain.strategy.services.filters.filter_st import filter_st
from src.domain.strategy.services.filters.filter_trading_status import filter_trading_status
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
