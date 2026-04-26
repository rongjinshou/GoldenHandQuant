from dataclasses import dataclass
from src.domain.trade.value_objects.order_direction import OrderDirection

@dataclass(slots=True, kw_only=True)
class OrderTarget:
    """仓位目标实体。
    
    Attributes:
        symbol: 标的代码。
        direction: 交易方向。
        volume: 目标数量。
        price: 目标价格 (通常为当前价格或限价)。
        strategy_name: 来源策略名称。
    """
    symbol: str
    direction: OrderDirection
    volume: int
    price: float
    strategy_name: str
