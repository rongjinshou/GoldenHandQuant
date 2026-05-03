from src.domain.market.value_objects.stock_snapshot import StockSnapshot


def filter_trading_status(snapshots: list[StockSnapshot]) -> list[StockSnapshot]:
    """剔除停牌（volume==0）或一字涨跌停（open==high==low==close，含非零）的标的。"""
    return [
        s for s in snapshots
        if s.volume > 0 and not (s.open == s.high == s.low == s.close)
    ]
