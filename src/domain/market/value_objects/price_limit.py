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
        prev_close: 前一日收盘价(前复权或不复权均可,比例判断不受复权影响)。
        board_multiplier: 涨跌停幅度,可配合 get_price_limit_ratio 按板块获取。

    Returns:
        PriceLimit 对象，涨停价和跌停价均四舍五入到分。
    """
    limit_up = round(prev_close * (1 + board_multiplier), 2)
    limit_down = round(prev_close * (1 - board_multiplier), 2)
    return PriceLimit(limit_up=limit_up, limit_down=limit_down)


def get_price_limit_ratio(symbol: str, is_st: bool = False) -> float:
    """根据证券代码与 ST 状态返回涨跌停幅度。

    Args:
        symbol: 证券代码(如 "600000.SH")。
        is_st: 是否 ST/*ST。注:ST 状态需外部数据源,本系统当前默认 False(见 spec 已知限制)。
    """
    if is_st:
        return 0.05
    code, _, market = symbol.partition(".")
    if market == "BJ":          # 北交所
        return 0.30
    if code.startswith("688"):  # 科创板
        return 0.20
    if code.startswith(("300", "301")):  # 创业板
        return 0.20
    return 0.10                 # 主板
