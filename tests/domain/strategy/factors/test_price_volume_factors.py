from datetime import datetime

import pytest

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.price_volume_factors import (
    ATR14Factor,
    AvgTurnover20dFactor,
    Illiquidity20dFactor,
    MACDFactor,
    Return5dFactor,
    Return60dFactor,
    RSI14Factor,
    Skewness20dFactor,
    TurnoverFactor,
    Volatility60dFactor,
)


def _make_snapshot(symbol: str, **kwargs) -> StockSnapshot:
    defaults = dict(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name="test", list_date=datetime(2020, 1, 1),
        market_cap=1e10,
    )
    defaults.update(kwargs)
    return StockSnapshot(**defaults)


class TestReturn5dFactor:
    def test_compute_returns_5d_return(self):
        factor = Return5dFactor()
        snapshots = [_make_snapshot("A", return_5d=-0.03), _make_snapshot("B", return_5d=0.05)]
        raw = factor.compute(snapshots)
        assert raw["A"] == -0.03
        assert raw["B"] == 0.05

    def test_compute_skips_none(self):
        factor = Return5dFactor()
        snapshots = [_make_snapshot("A", return_5d=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestReturn60dFactor:
    def test_compute_returns_60d_return(self):
        factor = Return60dFactor()
        snapshots = [_make_snapshot("A", return_60d=0.15), _make_snapshot("B", return_60d=-0.10)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.15
        assert raw["B"] == -0.10

    def test_compute_skips_none(self):
        factor = Return60dFactor()
        snapshots = [_make_snapshot("A", return_60d=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestVolatility60dFactor:
    def test_compute_returns_volatility(self):
        factor = Volatility60dFactor()
        snapshots = [_make_snapshot("A", volatility_60d=0.25), _make_snapshot("B", volatility_60d=0.40)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.25
        assert raw["B"] == 0.40

    def test_compute_skips_none(self):
        factor = Volatility60dFactor()
        snapshots = [_make_snapshot("A", volatility_60d=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestTurnoverFactor:
    def test_compute_returns_turnover(self):
        factor = TurnoverFactor()
        snapshots = [_make_snapshot("A", turnover_rate=0.05), _make_snapshot("B", turnover_rate=0.12)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.05
        assert raw["B"] == 0.12

    def test_compute_skips_none(self):
        factor = TurnoverFactor()
        snapshots = [_make_snapshot("A", turnover_rate=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestAvgTurnover20dFactor:
    def test_compute_returns_avg_turnover(self):
        factor = AvgTurnover20dFactor()
        snapshots = [_make_snapshot("A", avg_turnover_20d=0.03), _make_snapshot("B", avg_turnover_20d=0.08)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.03
        assert raw["B"] == 0.08

    def test_compute_skips_none(self):
        factor = AvgTurnover20dFactor()
        snapshots = [_make_snapshot("A", avg_turnover_20d=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestRSI14Factor:
    def test_compute_returns_rsi(self):
        factor = RSI14Factor()
        snapshots = [_make_snapshot("A", rsi_14=30.0), _make_snapshot("B", rsi_14=70.0)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 30.0
        assert raw["B"] == 70.0

    def test_compute_skips_none(self):
        factor = RSI14Factor()
        snapshots = [_make_snapshot("A", rsi_14=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestMACDFactor:
    def test_compute_returns_macd_histogram(self):
        factor = MACDFactor()
        snapshots = [_make_snapshot("A", macd=0.5, macd_signal=0.3), _make_snapshot("B", macd=-0.2, macd_signal=0.1)]
        raw = factor.compute(snapshots)
        assert raw["A"] == pytest.approx(0.2)
        assert raw["B"] == pytest.approx(-0.3)

    def test_compute_skips_when_macd_none(self):
        factor = MACDFactor()
        snapshots = [_make_snapshot("A", macd=None, macd_signal=0.3)]
        raw = factor.compute(snapshots)
        assert "A" not in raw

    def test_compute_skips_when_signal_none(self):
        factor = MACDFactor()
        snapshots = [_make_snapshot("A", macd=0.5, macd_signal=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestATR14Factor:
    def test_compute_returns_atr(self):
        factor = ATR14Factor()
        snapshots = [_make_snapshot("A", atr_14=1.5), _make_snapshot("B", atr_14=3.0)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 1.5
        assert raw["B"] == 3.0

    def test_compute_skips_none(self):
        factor = ATR14Factor()
        snapshots = [_make_snapshot("A", atr_14=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestSkewness20dFactor:
    def test_compute_returns_skewness(self):
        factor = Skewness20dFactor()
        snapshots = [_make_snapshot("A", skewness_20d=-0.5), _make_snapshot("B", skewness_20d=1.0)]
        raw = factor.compute(snapshots)
        assert raw["A"] == -0.5
        assert raw["B"] == 1.0

    def test_compute_skips_none(self):
        factor = Skewness20dFactor()
        snapshots = [_make_snapshot("A", skewness_20d=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw


class TestIlliquidity20dFactor:
    def test_compute_returns_illiquidity(self):
        factor = Illiquidity20dFactor()
        snapshots = [_make_snapshot("A", illiquidity_20d=0.001), _make_snapshot("B", illiquidity_20d=0.005)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.001
        assert raw["B"] == 0.005

    def test_compute_skips_none(self):
        factor = Illiquidity20dFactor()
        snapshots = [_make_snapshot("A", illiquidity_20d=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw
