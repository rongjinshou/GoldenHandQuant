from datetime import datetime, timedelta
from src.infrastructure.ml_engine.feature_pipeline import FeaturePipeline
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
from src.domain.market.services.fundamental_registry import FundamentalRegistry

def _bar(symbol, dt, close, volume=1000):
    return Bar(
        symbol=symbol, timeframe=Timeframe.DAY_1, timestamp=dt,
        open=close, high=close, low=close, close=close, volume=volume,
    )

class TestBuildCrossSection:
    def test_merges_bars_with_fundamentals(self):
        date = datetime(2024, 6, 15)
        registry = FundamentalRegistry()
        registry.add(FundamentalSnapshot(
            symbol="000001.SZ", date=date, name="Stock A",
            list_date=datetime(2000, 1, 1), market_cap=1e10,
            roe_ttm=0.15, ocf_ttm=5e8,
        ))
        registry.add(FundamentalSnapshot(
            symbol="000002.SZ", date=date, name="Stock B",
            list_date=datetime(2001, 1, 1), market_cap=5e9,
            roe_ttm=None, ocf_ttm=None,
        ))

        bars = {
            "000001.SZ": _bar("000001.SZ", date, 10.0),
            "000002.SZ": _bar("000002.SZ", date, 8.0),
        }

        result = FeaturePipeline.build_cross_section(date, bars, registry)
        assert len(result) == 2
        snap_a = next(s for s in result if s.symbol == "000001.SZ")
        snap_b = next(s for s in result if s.symbol == "000002.SZ")
        assert snap_a.name == "Stock A"
        assert snap_a.roe_ttm == 0.15
        assert snap_a.close == 10.0
        assert snap_b.name == "Stock B"
        assert snap_b.roe_ttm is None

    def test_skips_symbols_without_fundamental_data(self):
        date = datetime(2024, 6, 15)
        registry = FundamentalRegistry()
        bars = {"000001.SZ": _bar("000001.SZ", date, 10.0)}
        result = FeaturePipeline.build_cross_section(date, bars, registry)
        assert result == []

    def test_skips_symbols_without_bar_data(self):
        date = datetime(2024, 6, 15)
        registry = FundamentalRegistry()
        registry.add(FundamentalSnapshot(
            symbol="000001.SZ", date=date, name="A",
            list_date=datetime(2000, 1, 1), market_cap=1e10,
        ))
        bars: dict[str, Bar] = {}
        result = FeaturePipeline.build_cross_section(date, bars, registry)
        assert result == []
