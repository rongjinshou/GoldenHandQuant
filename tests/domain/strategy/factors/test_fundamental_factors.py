from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.fundamental_factors import (
    AssetTurnoverFactor,
    CurrentRatioFactor,
    DebtToEquityFactor,
    DividendYieldFactor,
    EarningsGrowthFactor,
    GrossMarginFactor,
    NetMarginFactor,
    PCFRatioFactor,
    PSRatioFactor,
    ROAFactor,
)


def _make_snapshot(symbol: str, **kwargs) -> StockSnapshot:
    defaults = dict(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name="test", list_date=datetime(2020, 1, 1), market_cap=1e10,
    )
    defaults.update(kwargs)
    return StockSnapshot(**defaults)


class TestROAFactor:
    def test_compute_returns_roa_values(self):
        factor = ROAFactor()
        snapshots = [
            _make_snapshot("A", roa_ttm=0.15),
            _make_snapshot("B", roa_ttm=0.08),
            _make_snapshot("C", roa_ttm=0.20),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.15
        assert raw["B"] == 0.08
        assert raw["C"] == 0.20

    def test_compute_skips_none_roa(self):
        factor = ROAFactor()
        snapshots = [_make_snapshot("A", roa_ttm=0.15), _make_snapshot("B", roa_ttm=None)]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw

    def test_compute_empty(self):
        factor = ROAFactor()
        assert factor.compute([]) == {}


class TestGrossMarginFactor:
    def test_compute_returns_gross_margin_values(self):
        factor = GrossMarginFactor()
        snapshots = [
            _make_snapshot("A", gross_margin=0.45),
            _make_snapshot("B", gross_margin=0.30),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.45
        assert raw["B"] == 0.30

    def test_compute_skips_none(self):
        factor = GrossMarginFactor()
        snapshots = [_make_snapshot("A", gross_margin=0.45), _make_snapshot("B")]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw

    def test_compute_empty(self):
        assert GrossMarginFactor().compute([]) == {}


class TestNetMarginFactor:
    def test_compute_returns_net_margin_values(self):
        factor = NetMarginFactor()
        snapshots = [
            _make_snapshot("A", net_margin=0.12),
            _make_snapshot("B", net_margin=0.05),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.12
        assert raw["B"] == 0.05

    def test_compute_skips_none(self):
        factor = NetMarginFactor()
        snapshots = [_make_snapshot("A", net_margin=0.12), _make_snapshot("B")]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw


class TestAssetTurnoverFactor:
    def test_compute_returns_asset_turnover_values(self):
        factor = AssetTurnoverFactor()
        snapshots = [
            _make_snapshot("A", asset_turnover=1.5),
            _make_snapshot("B", asset_turnover=0.8),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 1.5
        assert raw["B"] == 0.8

    def test_compute_skips_none(self):
        factor = AssetTurnoverFactor()
        snapshots = [_make_snapshot("A", asset_turnover=1.5), _make_snapshot("B")]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw

    def test_compute_skips_negative(self):
        factor = AssetTurnoverFactor()
        snapshots = [_make_snapshot("A", asset_turnover=1.5), _make_snapshot("B", asset_turnover=-0.5)]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw


class TestCurrentRatioFactor:
    def test_compute_returns_current_ratio_values(self):
        factor = CurrentRatioFactor()
        snapshots = [
            _make_snapshot("A", current_ratio=2.0),
            _make_snapshot("B", current_ratio=1.5),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 2.0
        assert raw["B"] == 1.5

    def test_compute_skips_none(self):
        factor = CurrentRatioFactor()
        snapshots = [_make_snapshot("A", current_ratio=2.0), _make_snapshot("B")]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw


class TestDebtToEquityFactor:
    def test_compute_returns_debt_to_equity_values(self):
        factor = DebtToEquityFactor()
        snapshots = [
            _make_snapshot("A", debt_to_equity=0.5),
            _make_snapshot("B", debt_to_equity=1.2),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.5
        assert raw["B"] == 1.2

    def test_compute_skips_none(self):
        factor = DebtToEquityFactor()
        snapshots = [_make_snapshot("A", debt_to_equity=0.5), _make_snapshot("B")]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw

    def test_compute_skips_negative(self):
        factor = DebtToEquityFactor()
        snapshots = [_make_snapshot("A", debt_to_equity=0.5), _make_snapshot("B", debt_to_equity=-0.3)]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw


class TestPCFRatioFactor:
    def test_compute_returns_pcf_values(self):
        factor = PCFRatioFactor()
        snapshots = [
            _make_snapshot("A", pcf_ratio=10.0),
            _make_snapshot("B", pcf_ratio=25.0),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 10.0
        assert raw["B"] == 25.0

    def test_compute_skips_none(self):
        factor = PCFRatioFactor()
        snapshots = [_make_snapshot("A", pcf_ratio=10.0), _make_snapshot("B")]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw

    def test_compute_skips_negative(self):
        factor = PCFRatioFactor()
        snapshots = [_make_snapshot("A", pcf_ratio=10.0), _make_snapshot("B", pcf_ratio=-5.0)]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw


class TestPSRatioFactor:
    def test_compute_returns_ps_values(self):
        factor = PSRatioFactor()
        snapshots = [
            _make_snapshot("A", ps_ratio=3.0),
            _make_snapshot("B", ps_ratio=8.0),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 3.0
        assert raw["B"] == 8.0

    def test_compute_skips_none(self):
        factor = PSRatioFactor()
        snapshots = [_make_snapshot("A", ps_ratio=3.0), _make_snapshot("B")]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw

    def test_compute_skips_negative(self):
        factor = PSRatioFactor()
        snapshots = [_make_snapshot("A", ps_ratio=3.0), _make_snapshot("B", ps_ratio=-2.0)]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw


class TestDividendYieldFactor:
    def test_compute_returns_dividend_yield_values(self):
        factor = DividendYieldFactor()
        snapshots = [
            _make_snapshot("A", dividend_yield=0.03),
            _make_snapshot("B", dividend_yield=0.06),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.03
        assert raw["B"] == 0.06

    def test_compute_skips_none(self):
        factor = DividendYieldFactor()
        snapshots = [_make_snapshot("A", dividend_yield=0.03), _make_snapshot("B")]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw

    def test_compute_skips_negative(self):
        factor = DividendYieldFactor()
        snapshots = [_make_snapshot("A", dividend_yield=0.03), _make_snapshot("B", dividend_yield=-0.01)]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw


class TestEarningsGrowthFactor:
    def test_compute_returns_earnings_growth_values(self):
        factor = EarningsGrowthFactor()
        snapshots = [
            _make_snapshot("A", earnings_growth=0.25),
            _make_snapshot("B", earnings_growth=-0.10),
        ]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.25
        assert raw["B"] == -0.10

    def test_compute_skips_none(self):
        factor = EarningsGrowthFactor()
        snapshots = [_make_snapshot("A", earnings_growth=0.25), _make_snapshot("B")]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw

    def test_compute_empty(self):
        assert EarningsGrowthFactor().compute([]) == {}
