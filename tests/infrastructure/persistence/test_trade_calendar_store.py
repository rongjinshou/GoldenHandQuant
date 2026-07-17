"""trade_calendar 表: 交易所日历(含未来)入库与装载(0711 tushare 沉淀·兑现①)。"""
from datetime import date

from src.infrastructure.persistence.market_data_store import MarketDataStore


def _rows():
    # (cal_date, is_open): 含未来节假日(2026-10-06 国庆周二闭市)与已知末端(非开市日)
    return [
        (date(2026, 7, 10), True),
        (date(2026, 7, 13), True),
        (date(2026, 7, 14), True),
        (date(2026, 10, 6), False),
        (date(2026, 12, 31), True),
    ]


def test_save_and_load_roundtrip_known_until_is_table_max():
    store = MarketDataStore(":memory:")
    n = store.save_trade_calendar(_rows(), source="tushare")
    assert n == 5
    loaded = store.load_trade_calendar()
    assert loaded is not None
    open_days, known_until = loaded
    assert date(2026, 7, 14) in open_days
    assert date(2026, 10, 6) not in open_days      # 闭市日不在开市集
    assert known_until == date(2026, 12, 31)        # 已知边界=表末端(含闭市日)


def test_save_is_full_replace():
    store = MarketDataStore(":memory:")
    store.save_trade_calendar(_rows(), source="tushare")
    store.save_trade_calendar([(date(2027, 1, 4), True)], source="tushare")
    open_days, known_until = store.load_trade_calendar()
    assert open_days == frozenset({date(2027, 1, 4)}) and known_until == date(2027, 1, 4)


def test_empty_table_returns_none():
    store = MarketDataStore(":memory:")
    assert store.load_trade_calendar() is None
