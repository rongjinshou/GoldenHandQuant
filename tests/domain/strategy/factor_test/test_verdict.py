"""Tests for factor verdict judgment logic."""

from src.domain.strategy.factor_test import verdict as verdict_module
from src.domain.strategy.factor_test.report import FactorTestReport, ScoredFactorTestReport
from src.domain.strategy.factor_test.verdict import judge_factor


def _make_report(
    ic_mean: float = 0.04,
    ir: float = 0.5,
    ic_positive_rate: float = 0.6,
    monotonicity_score: float = 0.8,
    long_short_return: float = 0.1,
    expression: str = "0 - return_20d",
    top_excess_return: float = 0.0,
    excess_ir: float = 0.0,
    excess_positive_rate: float = 0.0,
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
        top_excess_return=top_excess_return,
        excess_ir=excess_ir,
        excess_positive_rate=excess_positive_rate,
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

    def test_ic_positive_rate_gate_reads_from_gates_config(self, monkeypatch):
        """债 D2 遗留(2026-07-05 全项目排查发现): IC正率闸此前仍硬编码 0.52 字面量,
        未从 gates_config 读取, 与模块顶部"单一真相源"docstring 承诺不符——调阈值会
        静默失配。patch 常量后判决须跟着变, 而不是继续用编译时冻结的字面量。"""
        report = _make_report(ic_positive_rate=0.6)
        monkeypatch.setattr(verdict_module, "IC_POSITIVE_RATE_MIN", 0.9)
        v = judge_factor(report, factor_id="F02", factor_name="短期反转")
        assert v.passed is False
        assert any("IC正率" in r for r in v.reasons)


class TestJudgeFactorLongOnly:
    """long_only 记分牌: 稳定性/一致性/变现闸改用 Top 超额口径。"""

    def test_long_only_passes_when_excess_and_ir_ok(self):
        is_r = _make_report(ic_mean=0.03, ir=0.1, monotonicity_score=0.8,
                            top_excess_return=0.06, excess_ir=0.7, excess_positive_rate=0.6)
        oos_r = _make_report(ic_mean=0.025, top_excess_return=0.04, excess_ir=0.5)
        v = judge_factor(is_r, oos_report=oos_r, objective="long_only", neutralized_ic=None)
        assert v.passed
        assert v.objective == "long_only"
        assert v.top_excess_return == 0.06
        assert v.oos_top_excess_return == 0.04

    def test_long_only_fails_low_excess_ir(self):
        is_r = _make_report(ic_mean=0.03, monotonicity_score=0.8,
                            top_excess_return=0.06, excess_ir=0.30, excess_positive_rate=0.6)
        v = judge_factor(is_r, objective="long_only", neutralized_ic=None)
        assert not v.passed
        assert any("超额信息比" in r for r in v.reasons)

    def test_long_only_fails_low_excess_positive_rate(self):
        is_r = _make_report(ic_mean=0.03, monotonicity_score=0.8,
                            top_excess_return=0.06, excess_ir=0.7, excess_positive_rate=0.40)
        v = judge_factor(is_r, objective="long_only", neutralized_ic=None)
        assert not v.passed
        assert any("超额正率" in r for r in v.reasons)

    def test_long_only_fails_negative_top_excess(self):
        is_r = _make_report(ic_mean=0.03, monotonicity_score=0.8,
                            top_excess_return=-0.02, excess_ir=0.7, excess_positive_rate=0.6)
        v = judge_factor(is_r, objective="long_only", neutralized_ic=None)
        assert not v.passed
        assert any("Top超额" in r for r in v.reasons)

    def test_long_only_fails_negative_oos_excess(self):
        is_r = _make_report(ic_mean=0.03, monotonicity_score=0.8,
                            top_excess_return=0.06, excess_ir=0.7, excess_positive_rate=0.6)
        oos_r = _make_report(ic_mean=0.02, top_excess_return=-0.05, excess_ir=0.1)
        v = judge_factor(is_r, oos_report=oos_r, objective="long_only", neutralized_ic=None)
        assert not v.passed
        assert any("样本外Top超额" in r for r in v.reasons)

    def test_long_only_bypasses_ic_ir_gate(self):
        """关键: long_only 下多空 IC-IR(0.11)不再卡(F01/F03 场景), 改由 excess_ir 判。"""
        is_r = _make_report(ic_mean=0.021, ir=0.11, monotonicity_score=0.8,
                            top_excess_return=0.06, excess_ir=0.7, excess_positive_rate=0.6)
        v = judge_factor(is_r, objective="long_only", neutralized_ic=None)
        assert v.passed  # 多空 IR 闸不再适用, 长多用超额信息比
