from dataclasses import dataclass
from datetime import datetime
from src.domain.trade.value_objects.order_direction import OrderDirection

@dataclass(slots=True, kw_only=True)
class TradeRecord:
    """回测交易记录实体。

    Attributes:
        symbol: 标的代码。
        direction: 买卖方向。
        execute_at: 成交时间。
        price: 成交价格。
        volume: 成交数量。
        commission: 交易总费用 (含佣金、印花税、过户费)。
        remark: 备注。
    """
    symbol: str
    direction: OrderDirection
    execute_at: datetime
    price: float
    volume: int
    commission: float = 0.0  # 包含所有费用 (Commission + Tax + Transfer Fee)
    realized_pnl: float = 0.0  # 仅卖出时计算 (已扣除费用)
    remark: str = ""
