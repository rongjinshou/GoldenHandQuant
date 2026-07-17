"""st_status_periods 表: 全删全建往返(设计 0711-st-honesty §3.1/§3.5)。"""
from datetime import date

from src.infrastructure.gateway.st_status_source import StPeriod
from src.infrastructure.persistence.market_data_store import MarketDataStore


def _mk(symbol="000021.SZ", start=date(2022, 5, 6), end=date(2023, 6, 1),
        label="ST", source="szse_name_change"):
    return StPeriod(symbol=symbol, start=start, end=end, label=label,
                    source=source, evidence="ev")


def test_save_and_load_roundtrip_including_sentinels():
    store = MarketDataStore(":memory:")
    n = store.save_st_periods([
        _mk(),
        _mk(symbol="600186.SH", start=date.min, end=date(2021, 3, 1), source="cninfo_notice"),
        _mk(symbol="600696.SH", start=date(2024, 1, 4), end=None, label="*ST",
            source="cninfo_notice"),
    ])
    assert n == 3
    loaded = store.load_st_periods()
    assert {p.symbol for p in loaded} == {"000021.SZ", "600186.SH", "600696.SH"}
    open_p = next(p for p in loaded if p.symbol == "600696.SH")
    assert open_p.end is None and open_p.label == "*ST"
    sentinel = next(p for p in loaded if p.symbol == "600186.SH")
    assert sentinel.start == date.min


def test_save_is_full_replace():
    store = MarketDataStore(":memory:")
    store.save_st_periods([_mk()])
    store.save_st_periods([_mk(symbol="000100.SZ")])
    assert [p.symbol for p in store.load_st_periods()] == ["000100.SZ"]
