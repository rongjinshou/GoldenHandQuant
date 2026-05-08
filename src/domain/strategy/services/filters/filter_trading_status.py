from src.domain.market.value_objects.price_limit import calculate_price_limits
from src.domain.market.value_objects.stock_snapshot import StockSnapshot


def _is_limit_locked(s: StockSnapshot) -> bool:
    """判断是否一字涨跌停（open==high==low==close 且等于涨停或跌停价）。"""
    if not (s.open == s.high == s.low == s.close):
        return False
    if s.prev_close is not None and s.prev_close > 0:
        limits = calculate_price_limits(s.prev_close)
        return s.close >= limits.limit_up or s.close <= limits.limit_down
    # 无 prev_close 时回退到启发式：OHLC 全等即视为涨跌停
    return True


def filter_trading_status(snapshots: list[StockSnapshot]) -> list[StockSnapshot]:
    """剔除停牌（volume==0）或一字涨跌停的标的。"""
    return [s for s in snapshots if s.volume > 0 and not _is_limit_locked(s)]
