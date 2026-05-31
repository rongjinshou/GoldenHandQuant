from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class ExecutionStats:
    """执行统计值对象。"""

    total_orders: int
    successful_orders: int
    failed_orders: int
    success_rate: float
    avg_slippage_buy: float
    avg_slippage_sell: float
    max_slippage: float
    avg_fill_time_seconds: float
