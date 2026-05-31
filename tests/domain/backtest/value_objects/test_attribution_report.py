"""AttributionReport 值对象测试。"""
from datetime import datetime

from src.domain.backtest.value_objects.attribution_report import (
    AttributionReport,
    BrinsonAttributionResult,
    FactorAttributionResult,
    FactorExposure,
    SectorAttributionRow,
)


class TestSectorAttributionRow:
    def test_frozen(self):
        """SectorAttributionRow 是不可变的。"""
        row = SectorAttributionRow(
            name="tech",
            portfolio_weight=0.6,
            benchmark_weight=0.5,
            portfolio_return=0.10,
            benchmark_return=0.08,
            allocation_effect=0.008,
            selection_effect=0.010,
            interaction_effect=0.002,
        )
        assert row.name == "tech"
        try:
            row.name = "finance"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestBrinsonAttributionResult:
    def test_fields(self):
        result = BrinsonAttributionResult(
            total_return=0.08,
            benchmark_return=0.07,
            active_return=0.01,
            allocation_effect=0.002,
            selection_effect=0.005,
            interaction_effect=0.003,
        )
        assert result.total_return == 0.08
        assert result.sectors == []

    def test_with_sectors(self):
        sectors = [
            SectorAttributionRow(
                name="A",
                portfolio_weight=0.5,
                benchmark_weight=0.5,
                portfolio_return=0.10,
                benchmark_return=0.08,
                allocation_effect=0.0,
                selection_effect=0.01,
                interaction_effect=0.0,
            ),
        ]
        result = BrinsonAttributionResult(
            total_return=0.10,
            benchmark_return=0.08,
            active_return=0.02,
            allocation_effect=0.0,
            selection_effect=0.01,
            interaction_effect=0.0,
            sectors=sectors,
        )
        assert len(result.sectors) == 1


class TestFactorExposure:
    def test_fields(self):
        exp = FactorExposure(
            factor_name="market",
            portfolio_exposure=1.1,
            benchmark_exposure=1.0,
            factor_spread=0.1,
            factor_return=0.05,
            contribution=0.005,
        )
        assert exp.factor_name == "market"
        assert exp.contribution == 0.005


class TestFactorAttributionResult:
    def test_default_residual(self):
        result = FactorAttributionResult(
            total_return=0.08,
            benchmark_return=0.06,
            active_return=0.02,
        )
        assert result.residual_return == 0.0
        assert result.factor_contributions == []


class TestAttributionReport:
    def test_basic_fields(self):
        now = datetime.now()
        report = AttributionReport(
            strategy_name="test_strategy",
            generated_at=now,
            total_return=0.08,
            benchmark_return=0.06,
            allocation_effect=0.005,
            selection_effect=0.008,
            interaction_effect=0.002,
        )
        assert report.strategy_name == "test_strategy"
        assert report.factor_contributions == {}
        assert report.brinson_detail is None
        assert report.factor_detail is None

    def test_full_report(self):
        brinson = BrinsonAttributionResult(
            total_return=0.08,
            benchmark_return=0.06,
            active_return=0.02,
            allocation_effect=0.005,
            selection_effect=0.008,
            interaction_effect=0.002,
        )
        factor = FactorAttributionResult(
            total_return=0.08,
            benchmark_return=0.06,
            active_return=0.02,
            factor_contributions=[
                FactorExposure(
                    factor_name="market",
                    portfolio_exposure=1.1,
                    benchmark_exposure=1.0,
                    factor_spread=0.1,
                    factor_return=0.05,
                    contribution=0.005,
                ),
            ],
            residual_return=0.015,
        )

        report = AttributionReport(
            strategy_name="full_test",
            generated_at=datetime.now(),
            total_return=0.08,
            benchmark_return=0.06,
            allocation_effect=0.005,
            selection_effect=0.008,
            interaction_effect=0.002,
            factor_contributions={"market": 0.005},
            brinson_detail=brinson,
            factor_detail=factor,
        )

        assert report.brinson_detail is not None
        assert report.factor_detail is not None
        assert report.factor_detail.residual_return == 0.015
        assert report.factor_contributions["market"] == 0.005
