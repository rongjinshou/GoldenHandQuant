"""Tests for factor verdict judgment logic."""

from src.domain.strategy.factor_test.report import FactorTestReport, ScoredFactorTestReport
from src.domain.strategy.factor_test.verdict import judge_factor


def _make_report(
    ic_mean: float = 0.04,
    ir: float = 0.5,
    ic_positive_rate: float = 0.6,
    monotonicity_score: float = 0.8,
    long_short_return: float = 0.1,
    expression: str = "0 - return_20d",
) -> ScoredFactorTestReport:
    r = FactorTestReport(
        expression=expression,
        test_period=("2021-01-01", "2025-12-31"),
        universe_count=3000,
        ic_mean=ic_mean,
        ic_std=abs(ic_mean / ir) if ir != 0 else 0.01,
        ir=ir,
        ic_positive_rate=ic_positive_rate,
        monotonicity_score=monotonicity_score,
        long_short_return=long_short_return,
    )
    return ScoredFactorTestReport(report=r, score=75.0, grade="B", grade_reasons=["test"])


class TestJudgeFactor:
    def test_all_pass(self):
        report = _make_report()
        verdict = judge_factor(report, factor_id="F02", factor_name="短期反转")
        assert verdict.passed is True
        assert len([r for r in verdict.reasons if "✓" in r]) >= 4

    def test_fail_low_ic(self):
        report = _make_report(ic_mean=0.005)
        verdict = judge_factor(report)
        assert verdict.passed is False
        assert any("IC" in r and "门槛" in r for r in verdict.reasons)

    def test_fail_low_ir(self):
        report = _make_report(ir=0.1)
        verdict = judge_factor(report)
        assert verdict.passed is False
        assert any("IR" in r and "门槛" in r for r in verdict.reasons)

    def test_fail_negative_long_short(self):
        report = _make_report(long_short_return=-0.05)
        verdict = judge_factor(report)
        assert verdict.passed is False
        assert any("多空" in r and "负" in r for r in verdict.reasons)

    def test_fail_low_monotonicity(self):
        report = _make_report(monotonicity_score=0.1)
        verdict = judge_factor(report)
        assert verdict.passed is False
        assert any("单调性" in r for r in verdict.reasons)

    def test_fail_ic_sign_flip_oos(self):
        is_report = _make_report(ic_mean=0.04)
        oos_report = _make_report(ic_mean=-0.03)
        verdict = judge_factor(is_report, oos_report=oos_report)
        assert verdict.passed is False
        assert any("翻转" in r for r in verdict.reasons)

    def test_pass_with_oos(self):
        is_report = _make_report(ic_mean=0.04, long_short_return=0.1)
        oos_report = _make_report(ic_mean=0.03, long_short_return=0.05)
        verdict = judge_factor(is_report, oos_report=oos_report)
        assert verdict.passed is True

    def test_fail_negative_ic_direction(self):
        """已定向因子 IC 为负(方向错) → 判负 (不再用 abs 放过)。"""
        report = _make_report(ic_mean=-0.04, ir=-0.5)
        verdict = judge_factor(report)
        assert verdict.passed is False
        assert any("方向" in r for r in verdict.reasons)

    def test_fail_mediocre_monotonicity(self):
        """单调性 0.5(≈随机) → 判负 (门槛收紧到 0.6)。"""
        report = _make_report(monotonicity_score=0.5)
        verdict = judge_factor(report)
        assert verdict.passed is False
        assert any("单调性" in r for r in verdict.reasons)

    def test_fail_neutralized_ic_collapse(self):
        """raw 全过, 但中性化(剥离市值/反转)后 IC 崩塌 → 判负(疑似影子)。"""
        report = _make_report()
        verdict = judge_factor(report, neutralized_ic=0.005)
        assert verdict.passed is False
        assert any("中性化" in r for r in verdict.reasons)

    def test_pass_with_neutralized_increment(self):
        """中性化后仍有 IC → 该门槛通过, 且记录 neutralized_ic。"""
        report = _make_report()
        verdict = judge_factor(report, neutralized_ic=0.03)
        assert verdict.passed is True
        assert verdict.neutralized_ic == 0.03
