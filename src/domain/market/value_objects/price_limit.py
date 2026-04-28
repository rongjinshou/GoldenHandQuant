from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class PriceLimit:
    """A 股涨跌停价格限制。"""
    limit_up: float    # 涨停价
    limit_down: float  # 跌停价

    def is_limit_up(self, price: float) -> bool:
        """检查价格是否触及涨停。"""
        return price >= self.limit_up

    def is_limit_down(self, price: float) -> bool:
        """检查价格是否触及跌停。"""
        return price <= self.limit_down

    def can_buy(self, price: float) -> bool:
        """涨停时无法买入。"""
        return not self.is_limit_up(price)

    def can_sell(self, price: float) -> bool:
        """跌停时无法卖出。"""
        return not self.is_limit_down(price)


def calculate_price_limits(prev_close: float, board_multiplier: float = 0.10) -> PriceLimit:
    """根据前收盘价计算涨跌停价格。

    Args:
        prev_close: 前一日收盘价（不复权）。
        board_multiplier: 涨跌停幅度，主板 0.10，科创/创业 0.20。

    Returns:
        PriceLimit 对象，涨停价和跌停价均四舍五入到分。
    """
    limit_up = round(prev_close * (1 + board_multiplier), 2)
    limit_down = round(prev_close * (1 - board_multiplier), 2)
    return PriceLimit(limit_up=limit_up, limit_down=limit_down)
