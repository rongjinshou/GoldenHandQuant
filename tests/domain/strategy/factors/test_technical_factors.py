from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.technical_factors import (
    ClosePositionFactor,
    GapFactor,
    High20dProximityFactor,
    Low20dProximityFactor,
    MACDCrossFactor,
    MA5CrossFactor,
    MA20CrossFactor,
    MA60CrossFactor,
    OBVSlope20dFactor,
    PriceRangeFactor,
)


def _make_snapshot(symbol: str, **kwargs) -> StockSnapshot:
    defaults = dict(
        symbol=symbol,
        date=datetime(2024, 1, 1),
        open=10.0,
        high=11.0,
        low=9.0,
        close=10.5,
        volume=1000.0,
        name="test",
        list_date=datetime(2020, 1, 1),
        market_cap=1e10,
    )
    defaults.update(kwargs)
    return StockSnapshot(**defaults)


class TestMA5CrossFactor:
    def test_compute_returns_close_div_ma5(self):
        factor = MA5CrossFactor()
        snapshots = [_make_snapshot("A", close=10.0, ma_5=5.0)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 2.0

    def test_compute_skips_none_ma5(self):
        factor = MA5CrossFactor()
        snapshots = [_make_snapshot("A", close=10.0, ma_5=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw

    def test_compute_skips_zero_ma5(self):
        factor = MA5CrossFactor()
        snapshots = [_make_snapshot("A", close=10.0, ma_5=0.0)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestMA20CrossFactor:
    def test_compute_returns_close_div_ma20(self):
        factor = MA20CrossFactor()
        snapshots = [_make_snapshot("A", close=20.0, ma_20=10.0)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 2.0

    def test_compute_skips_none_ma20(self):
        factor = MA20CrossFactor()
        snapshots = [_make_snapshot("A", close=10.0, ma_20=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestMA60CrossFactor:
    def test_compute_returns_close_div_ma60(self):
        factor = MA60CrossFactor()
        snapshots = [_make_snapshot("A", close=12.0, ma_60=6.0)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 2.0

    def test_compute_skips_none_ma60(self):
        factor = MA60CrossFactor()
        snapshots = [_make_snapshot("A", close=10.0, ma_60=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestHigh20dProximityFactor:
    def test_compute_returns_normalized_position(self):
        factor = High20dProximityFactor()
        snapshots = [_make_snapshot("A", close=15.0, high_20d=20.0, low_20d=10.0)]
        raw = factor.compute(snapshots)
        # (15 - 10) / (20 - 10) = 0.5
        assert raw["A"] == 0.5

    def test_compute_skips_none_high_20d(self):
        factor = High20dProximityFactor()
        snapshots = [_make_snapshot("A", close=15.0, high_20d=None, low_20d=10.0)]
        raw = factor.compute(snapshots)
        assert "A" not in raw

    def test_compute_skips_equal_high_low(self):
        factor = High20dProximityFactor()
        snapshots = [_make_snapshot("A", close=10.0, high_20d=10.0, low_20d=10.0)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestLow20dProximityFactor:
    def test_compute_returns_one_minus_position(self):
        factor = Low20dProximityFactor()
        snapshots = [_make_snapshot("A", close=15.0, high_20d=20.0, low_20d=10.0)]
        raw = factor.compute(snapshots)
        # 1 - (15-10)/(20-10) = 0.5
        assert raw["A"] == 0.5

    def test_compute_close_near_low_gives_high_score(self):
        factor = Low20dProximityFactor()
        snapshots = [_make_snapshot("A", close=11.0, high_20d=20.0, low_20d=10.0)]
        raw = factor.compute(snapshots)
        # 1 - (11-10)/(20-10) = 0.9
        assert abs(raw["A"] - 0.9) < 1e-9

    def test_compute_skips_none_low_20d(self):
        factor = Low20dProximityFactor()
        snapshots = [_make_snapshot("A", close=15.0, high_20d=20.0, low_20d=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestOBVSlope20dFactor:
    def test_compute_returns_obv_slope(self):
        factor = OBVSlope20dFactor()
        snapshots = [_make_snapshot("A", obv_slope_20d=0.5)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.5

    def test_compute_skips_none_obv_slope(self):
        factor = OBVSlope20dFactor()
        snapshots = [_make_snapshot("A", obv_slope_20d=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw

    def test_compute_accepts_negative_slope(self):
        factor = OBVSlope20dFactor()
        snapshots = [_make_snapshot("A", obv_slope_20d=-0.3)]
        raw = factor.compute(snapshots)
        assert raw["A"] == -0.3


class TestPriceRangeFactor:
    def test_compute_returns_hl_ratio(self):
        factor = PriceRangeFactor()
        snapshots = [_make_snapshot("A", high=12.0, low=8.0, close=10.0)]
        raw = factor.compute(snapshots)
        # (12 - 8) / 10 = 0.4
        assert raw["A"] == 0.4

    def test_compute_skips_none_close(self):
        factor = PriceRangeFactor()
        snapshots = [_make_snapshot("A", high=12.0, low=8.0, close=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw

    def test_compute_skips_zero_close(self):
        factor = PriceRangeFactor()
        snapshots = [_make_snapshot("A", high=12.0, low=8.0, close=0.0)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestClosePositionFactor:
    def test_compute_returns_close_position(self):
        factor = ClosePositionFactor()
        snapshots = [_make_snapshot("A", high=12.0, low=8.0, close=10.0)]
        raw = factor.compute(snapshots)
        # (10 - 8) / (12 - 8) = 0.5
        assert raw["A"] == 0.5

    def test_compute_close_at_high(self):
        factor = ClosePositionFactor()
        snapshots = [_make_snapshot("A", high=12.0, low=8.0, close=12.0)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 1.0

    def test_compute_skips_equal_high_low(self):
        factor = ClosePositionFactor()
        snapshots = [_make_snapshot("A", high=10.0, low=10.0, close=10.0)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestGapFactor:
    def test_compute_returns_gap(self):
        factor = GapFactor()
        snapshots = [_make_snapshot("A", open=11.0, prev_close=10.0)]
        raw = factor.compute(snapshots)
        # (11 - 10) / 10 = 0.1
        assert raw["A"] == 0.1

    def test_compute_negative_gap(self):
        factor = GapFactor()
        snapshots = [_make_snapshot("A", open=9.0, prev_close=10.0)]
        raw = factor.compute(snapshots)
        assert raw["A"] == -0.1

    def test_compute_skips_none_prev_close(self):
        factor = GapFactor()
        snapshots = [_make_snapshot("A", open=11.0, prev_close=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw

    def test_compute_skips_zero_prev_close(self):
        factor = GapFactor()
        snapshots = [_make_snapshot("A", open=11.0, prev_close=0.0)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestMACDCrossFactor:
    def test_compute_returns_macd_minus_signal(self):
        factor = MACDCrossFactor()
        snapshots = [_make_snapshot("A", macd=0.5, macd_signal=0.2)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.3

    def test_compute_skips_none_macd(self):
        factor = MACDCrossFactor()
        snapshots = [_make_snapshot("A", macd=None, macd_signal=0.2)]
        raw = factor.compute(snapshots)
        assert "A" not in raw

    def test_compute_skips_none_signal(self):
        factor = MACDCrossFactor()
        snapshots = [_make_snapshot("A", macd=0.5, macd_signal=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw

    def test_compute_negative_histogram(self):
        factor = MACDCrossFactor()
        snapshots = [_make_snapshot("A", macd=0.1, macd_signal=0.3)]
        raw = factor.compute(snapshots)
        assert abs(raw["A"] - (-0.2)) < 1e-9
