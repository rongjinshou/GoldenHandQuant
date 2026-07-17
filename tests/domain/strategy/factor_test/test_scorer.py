"""因子评分器测试。"""

import pytest

from src.domain.strategy.factor_test.report import FactorTestReport
from src.domain.strategy.factor_test.scorer import FactorScorer, _grade, _linear_score


def _make_report(**kwargs) -> FactorTestReport:
    defaults = dict(
        expression="test",
        test_period=("2023-01-01", "2024-01-01"),
        universe_count=100,
        ic_mean=0.0,
        ic_std=0.1,
        ir=0.0,
        ic_positive_rate=0.5,
    )
    defaults.update(kwargs)
    return FactorTestReport(**defaults)


class TestLinearScore:
    def test_above_high(self):
        assert _linear_score(0.1, 0.01, 0.05) == 1.0

    def test_below_low(self):
        assert _linear_score(0.005, 0.01, 0.05) == 0.0

    def test_midpoint(self):
        assert _linear_score(0.03, 0.01, 0.05) == pytest.approx(0.5)


class TestGrade:
    def test_grade_a(self):
        assert _grade(80) == "A"
        assert _grade(95) == "A"

    def test_grade_b(self):
        assert _grade(60) == "B"
        assert _grade(79) == "B"

    def test_grade_c(self):
        assert _grade(40) == "C"
        assert _grade(59) == "C"

    def test_grade_d(self):
        assert _grade(0) == "D"
        assert _grade(39) == "D"


class TestScorer:
    def test_perfect_score(self):
        report = _make_report(
            ic_mean=0.06,
            ir=0.6,
            long_short_return=0.20,
            monotonicity_score=1.0,
            decay_periods=[1, 5, 10, 20, 60],
            decay_ics=[0.06, 0.05, 0.04, 0.035, 0.02],
        )
        scorer = FactorScorer()
        score, grade, reasons = scorer.score(report)
        assert score >= 80
        assert grade == "A"
        assert len(reasons) == 5

    def test_zero_score(self):
        report = _make_report(
            ic_mean=0.001,
            ir=0.01,
            long_short_return=0.01,
            monotonicity_score=0.0,
            decay_periods=[1, 20],
            decay_ics=[0.1, 0.001],
        )
        scorer = FactorScorer()
        score, grade, _ = scorer.score(report)
        assert score < 40
        assert grade == "D"

    def test_medium_score(self):
        report = _make_report(
            ic_mean=0.03,
            ir=0.3,
            long_short_return=0.10,
            monotonicity_score=0.7,
            decay_periods=[1, 5, 10, 20, 60],
            decay_ics=[0.03, 0.025, 0.02, 0.018, 0.01],
        )
        scorer = FactorScorer()
        score, grade, _ = scorer.score(report)
        assert 40 <= score < 80
        assert grade in ("B", "C")

    def test_long_only_uses_top_excess(self):
        """objective=long_only 时变现项改记 Top 超额。"""
        report = _make_report(
            ic_mean=0.03, ir=0.2, long_short_return=0.0, top_excess_return=0.05,
            monotonicity_score=1.0,
        )
        score, _, reasons = FactorScorer().score(report, objective="long_only")
        assert any("Top超额" in r for r in reasons)
        assert score > 0

    def test_long_short_default_uses_long_short(self):
        """默认 objective=long_short, 变现项仍记多空收益。"""
        report = _make_report(ic_mean=0.03, ir=0.3, long_short_return=0.10, monotonicity_score=0.7)
        _, _, reasons = FactorScorer().score(report)
        assert any("多空收益" in r for r in reasons)

    def test_ic_clamped(self):
        """IC 超过阈值也应满分，不超 30 分。"""
        report = _make_report(
            ic_mean=1.0,  # 极端值
            ir=0.0,
            long_short_return=0.0,
            monotonicity_score=0.0,
        )
        scorer = FactorScorer()
        score, _, _ = scorer.score(report)
        # IC 部分最多 30 分
        assert score <= 30 + 0.001
