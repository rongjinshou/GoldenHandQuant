"""因子研发流水线领域服务测试。"""

from __future__ import annotations

import copy
from datetime import datetime

import pytest

from src.domain.strategy.factor_test.report import FactorTestReport
from src.domain.strategy.services.factor_pipeline import (
    DecayCheckResult,
    FactorCombiner,
    FactorDecayMonitor,
    FactorLifecycleEntry,
    FactorPipelineService,
)
from src.domain.strategy.value_objects.factor_lifecycle_status import FactorLifecycleStatus


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

def _make_report(
    ic_mean: float = 0.05,
    ir: float = 0.5,
    long_short_return: float = 0.12,
    monotonicity_score: float = 0.8,
    **kwargs,
) -> FactorTestReport:
    defaults = dict(
        expression="rank(close / earnings)",
        test_period=("2024-01-01", "2024-12-31"),
        universe_count=500,
        ic_mean=ic_mean,
        ic_std=0.03,
        ir=ir,
        ic_positive_rate=0.65,
        layer_count=5,
        layer_returns=[0.15, 0.12, 0.10, 0.08, 0.05],
        long_short_return=long_short_return,
        monotonicity_score=monotonicity_score,
    )
    defaults.update(kwargs)
    return FactorTestReport(**defaults)


def _make_good_report() -> FactorTestReport:
    """高分报告（评分 >= 60，应通过验证）。"""
    return _make_report(
        ic_mean=0.06,
        ir=0.6,
        long_short_return=0.18,
        monotonicity_score=0.9,
    )


def _make_bad_report() -> FactorTestReport:
    """低分报告（评分 < 40，不应通过验证）。"""
    return _make_report(
        ic_mean=0.005,
        ir=0.05,
        long_short_return=0.01,
        monotonicity_score=0.1,
    )


# ---------------------------------------------------------------------------
# FactorLifecycleEntry 测试
# ---------------------------------------------------------------------------

class TestFactorLifecycleEntry:
    def test_default_status_is_discovered(self):
        entry = FactorLifecycleEntry(factor_name="test", expression="close")
        assert entry.status == FactorLifecycleStatus.DISCOVERED

    def test_valid_transition_discovered_to_testing(self):
        entry = FactorLifecycleEntry(factor_name="test", expression="close")
        entry.transition_to(FactorLifecycleStatus.TESTING)
        assert entry.status == FactorLifecycleStatus.TESTING

    def test_valid_transition_testing_to_validated(self):
        entry = FactorLifecycleEntry(factor_name="test", expression="close")
        entry.transition_to(FactorLifecycleStatus.TESTING)
        entry.transition_to(FactorLifecycleStatus.VALIDATED)
        assert entry.status == FactorLifecycleStatus.VALIDATED

    def test_valid_transition_testing_back_to_discovered(self):
        entry = FactorLifecycleEntry(factor_name="test", expression="close")
        entry.transition_to(FactorLifecycleStatus.TESTING)
        entry.transition_to(FactorLifecycleStatus.DISCOVERED)
        assert entry.status == FactorLifecycleStatus.DISCOVERED

    def test_valid_transition_validated_to_active(self):
        entry = FactorLifecycleEntry(factor_name="test", expression="close")
        entry.transition_to(FactorLifecycleStatus.TESTING)
        entry.transition_to(FactorLifecycleStatus.VALIDATED)
        entry.transition_to(FactorLifecycleStatus.ACTIVE)
        assert entry.status == FactorLifecycleStatus.ACTIVE

    def test_valid_transition_active_to_decayed(self):
        entry = FactorLifecycleEntry(factor_name="test", expression="close")
        entry.transition_to(FactorLifecycleStatus.TESTING)
        entry.transition_to(FactorLifecycleStatus.VALIDATED)
        entry.transition_to(FactorLifecycleStatus.ACTIVE)
        entry.transition_to(FactorLifecycleStatus.DECAYED)
        assert entry.status == FactorLifecycleStatus.DECAYED

    def test_valid_transition_decayed_to_testing(self):
        entry = FactorLifecycleEntry(factor_name="test", expression="close")
        entry.transition_to(FactorLifecycleStatus.TESTING)
        entry.transition_to(FactorLifecycleStatus.VALIDATED)
        entry.transition_to(FactorLifecycleStatus.ACTIVE)
        entry.transition_to(FactorLifecycleStatus.DECAYED)
        entry.transition_to(FactorLifecycleStatus.TESTING)
        assert entry.status == FactorLifecycleStatus.TESTING

    def test_invalid_transition_raises(self):
        entry = FactorLifecycleEntry(factor_name="test", expression="close")
        with pytest.raises(ValueError, match="Invalid factor lifecycle transition"):
            entry.transition_to(FactorLifecycleStatus.ACTIVE)

    def test_retired_is_terminal(self):
        entry = FactorLifecycleEntry(factor_name="test", expression="close")
        entry.transition_to(FactorLifecycleStatus.RETIRED)
        assert entry.status == FactorLifecycleStatus.RETIRED
        with pytest.raises(ValueError, match="Invalid factor lifecycle transition"):
            entry.transition_to(FactorLifecycleStatus.ACTIVE)

    def test_transition_sets_reason_and_timestamp(self):
        entry = FactorLifecycleEntry(factor_name="test", expression="close")
        old_ts = entry.updated_at
        entry.transition_to(FactorLifecycleStatus.TESTING, reason="starting test")
        assert entry.reason == "starting test"
        assert entry.updated_at >= old_ts

    def test_update_metrics(self):
        entry = FactorLifecycleEntry(factor_name="test", expression="close")
        entry.update_metrics(score=75.0, grade="B", ic_mean=0.05, ir=0.4)
        assert entry.score == 75.0
        assert entry.grade == "B"
        assert entry.ic_mean == 0.05
        assert entry.ir == 0.4


# ---------------------------------------------------------------------------
# FactorDecayMonitor 测试
# ---------------------------------------------------------------------------

class TestFactorDecayMonitor:
    def test_no_decay_when_ic_above_threshold(self):
        monitor = FactorDecayMonitor(decay_ic_ratio=0.5)
        entry = FactorLifecycleEntry(
            factor_name="f1", expression="close",
            status=FactorLifecycleStatus.ACTIVE,
            validation_ic=0.05,
        )
        result = monitor.check_decay(entry, current_ic_mean=0.04)
        assert not result.is_decayed
        assert result.ic_ratio == pytest.approx(0.8)

    def test_decay_when_ic_below_threshold(self):
        monitor = FactorDecayMonitor(decay_ic_ratio=0.5)
        entry = FactorLifecycleEntry(
            factor_name="f1", expression="close",
            status=FactorLifecycleStatus.ACTIVE,
            validation_ic=0.05,
        )
        result = monitor.check_decay(entry, current_ic_mean=0.02)
        assert result.is_decayed
        assert result.ic_ratio == pytest.approx(0.4)

    def test_should_retire_after_consecutive_decays(self):
        monitor = FactorDecayMonitor(retire_after=3)
        entry = FactorLifecycleEntry(
            factor_name="f1", expression="close",
            status=FactorLifecycleStatus.DECAYED,
            decay_count=3,
        )
        assert monitor.should_retire(entry)

    def test_should_not_retire_before_threshold(self):
        monitor = FactorDecayMonitor(retire_after=3)
        entry = FactorLifecycleEntry(
            factor_name="f1", expression="close",
            status=FactorLifecycleStatus.DECAYED,
            decay_count=2,
        )
        assert not monitor.should_retire(entry)


# ---------------------------------------------------------------------------
# FactorPipelineService 测试
# ---------------------------------------------------------------------------

class TestFactorPipelineService:
    def setup_method(self):
        self.pipeline = FactorPipelineService(
            activate_score=60.0,
            validate_score=40.0,
        )

    # -- 注册 --

    def test_register_factor(self):
        entry = self.pipeline.register_factor("f1", "rank(close)")
        assert entry.status == FactorLifecycleStatus.DISCOVERED
        assert entry.factor_name == "f1"

    def test_register_duplicate_raises(self):
        self.pipeline.register_factor("f1", "rank(close)")
        with pytest.raises(ValueError, match="already registered"):
            self.pipeline.register_factor("f1", "rank(close)")

    # -- 检验推进 --

    def test_start_testing(self):
        self.pipeline.register_factor("f1", "rank(close)")
        entry = self.pipeline.start_testing("f1")
        assert entry.status == FactorLifecycleStatus.TESTING

    def test_process_test_result_validates_when_score_high(self):
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.start_testing("f1")
        report = _make_good_report()
        entry = self.pipeline.process_test_result("f1", report)
        assert entry.status == FactorLifecycleStatus.VALIDATED
        assert entry.score >= 40.0
        assert entry.validation_ic == report.ic_mean

    def test_process_test_result_rejects_when_score_low(self):
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.start_testing("f1")
        report = _make_bad_report()
        entry = self.pipeline.process_test_result("f1", report)
        assert entry.status == FactorLifecycleStatus.DISCOVERED
        assert entry.score < 40.0

    def test_process_test_result_requires_testing_status(self):
        self.pipeline.register_factor("f1", "rank(close)")
        report = _make_good_report()
        with pytest.raises(ValueError, match="must be in TESTING"):
            self.pipeline.process_test_result("f1", report)

    # -- 激活 --

    def test_activate_factor(self):
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.start_testing("f1")
        self.pipeline.process_test_result("f1", _make_good_report())
        entry = self.pipeline.activate_factor("f1")
        assert entry.status == FactorLifecycleStatus.ACTIVE

    def test_activate_requires_validated_status(self):
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.start_testing("f1")
        self.pipeline.process_test_result("f1", _make_bad_report())
        with pytest.raises(ValueError, match="must be VALIDATED"):
            self.pipeline.activate_factor("f1")

    def test_activate_requires_minimum_score(self):
        # 使用低 activate_score 阈值的 pipeline
        pipeline = FactorPipelineService(activate_score=80.0, validate_score=40.0)
        pipeline.register_factor("f1", "rank(close)")
        pipeline.start_testing("f1")
        pipeline.process_test_result("f1", _make_good_report())
        # 如果评分 < 80，激活应失败
        entry = pipeline.get_entry("f1")
        if entry.score < 80.0:
            with pytest.raises(ValueError, match="score.*threshold"):
                pipeline.activate_factor("f1")

    # -- 衰减监控 --

    def test_check_decay_transitions_to_decayed(self):
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.start_testing("f1")
        self.pipeline.process_test_result("f1", _make_good_report())
        self.pipeline.activate_factor("f1")

        # IC 大幅下降
        entry = self.pipeline.get_entry("f1")
        result = self.pipeline.check_decay("f1", current_ic_mean=entry.validation_ic * 0.3)
        assert result.is_decayed
        assert self.pipeline.get_entry("f1").status == FactorLifecycleStatus.DECAYED

    def test_check_decay_no_decay_when_ic_stable(self):
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.start_testing("f1")
        self.pipeline.process_test_result("f1", _make_good_report())
        self.pipeline.activate_factor("f1")

        entry = self.pipeline.get_entry("f1")
        result = self.pipeline.check_decay("f1", current_ic_mean=entry.validation_ic * 0.8)
        assert not result.is_decayed
        assert self.pipeline.get_entry("f1").status == FactorLifecycleStatus.ACTIVE

    def test_check_decay_auto_retire_after_consecutive(self):
        pipeline = FactorPipelineService(
            activate_score=60.0,
            validate_score=40.0,
        )
        pipeline.register_factor("f1", "rank(close)")
        pipeline.start_testing("f1")
        pipeline.process_test_result("f1", _make_good_report())
        pipeline.activate_factor("f1")

        entry = pipeline.get_entry("f1")
        low_ic = entry.validation_ic * 0.3

        # 连续衰减 3 次（默认 retire_after=3）
        for i in range(3):
            pipeline.check_decay("f1", current_ic_mean=low_ic)
            current_status = pipeline.get_entry("f1").status
            if current_status == FactorLifecycleStatus.RETIRED:
                break

        assert pipeline.get_entry("f1").status == FactorLifecycleStatus.RETIRED

    def test_batch_check_decay(self):
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.start_testing("f1")
        self.pipeline.process_test_result("f1", _make_good_report())
        self.pipeline.activate_factor("f1")

        self.pipeline.register_factor("f2", "rank(earnings)")
        self.pipeline.start_testing("f2")
        self.pipeline.process_test_result("f2", _make_good_report())
        self.pipeline.activate_factor("f2")

        entry1 = self.pipeline.get_entry("f1")
        entry2 = self.pipeline.get_entry("f2")

        results = self.pipeline.batch_check_decay({
            "f1": entry1.validation_ic * 0.3,  # 衰减
            "f2": entry2.validation_ic * 0.8,  # 稳定
        })
        assert len(results) == 2
        decayed_names = [r.factor_name for r in results if r.is_decayed]
        assert "f1" in decayed_names
        assert "f2" not in decayed_names

    # -- 重新验证 --

    def test_revalidate_factor(self):
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.start_testing("f1")
        self.pipeline.process_test_result("f1", _make_good_report())
        self.pipeline.activate_factor("f1")

        entry = self.pipeline.get_entry("f1")
        self.pipeline.check_decay("f1", current_ic_mean=entry.validation_ic * 0.3)
        assert self.pipeline.get_entry("f1").status == FactorLifecycleStatus.DECAYED

        entry = self.pipeline.revalidate_factor("f1")
        assert entry.status == FactorLifecycleStatus.TESTING

    # -- 手动操作 --

    def test_retire_factor(self):
        self.pipeline.register_factor("f1", "rank(close)")
        entry = self.pipeline.retire_factor("f1", reason="manual decision")
        assert entry.status == FactorLifecycleStatus.RETIRED
        assert entry.reason == "manual decision"

    # -- 查询 --

    def test_get_entry_returns_none_for_unknown(self):
        assert self.pipeline.get_entry("nonexistent") is None

    def test_get_entries_by_status(self):
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.register_factor("f2", "rank(earnings)")
        discovered = self.pipeline.get_entries_by_status(FactorLifecycleStatus.DISCOVERED)
        assert len(discovered) == 2

    def test_get_active_factors(self):
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.start_testing("f1")
        self.pipeline.process_test_result("f1", _make_good_report())
        self.pipeline.activate_factor("f1")
        active = self.pipeline.get_active_factors()
        assert len(active) == 1
        assert active[0].factor_name == "f1"

    def test_get_summary(self):
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.register_factor("f2", "rank(earnings)")
        summary = self.pipeline.get_summary()
        assert summary["total"] == 2
        assert summary["by_status"]["DISCOVERED"] == 2

    # -- 完整流水线 --

    def test_full_pipeline_discovered_to_active(self):
        """完整流水线: DISCOVERED → TESTING → VALIDATED → ACTIVE。"""
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.start_testing("f1")
        entry = self.pipeline.process_test_result("f1", _make_good_report())
        assert entry.status == FactorLifecycleStatus.VALIDATED
        entry = self.pipeline.activate_factor("f1")
        assert entry.status == FactorLifecycleStatus.ACTIVE

    def test_full_pipeline_with_decay_and_retire(self):
        """完整流水线含衰减退役。"""
        self.pipeline.register_factor("f1", "rank(close)")
        self.pipeline.start_testing("f1")
        self.pipeline.process_test_result("f1", _make_good_report())
        self.pipeline.activate_factor("f1")

        entry = self.pipeline.get_entry("f1")
        low_ic = entry.validation_ic * 0.3

        for _ in range(3):
            status = self.pipeline.get_entry("f1").status
            if status == FactorLifecycleStatus.RETIRED:
                break
            self.pipeline.check_decay("f1", current_ic_mean=low_ic)

        assert self.pipeline.get_entry("f1").status == FactorLifecycleStatus.RETIRED


# ---------------------------------------------------------------------------
# FactorCombiner 测试
# ---------------------------------------------------------------------------

class TestFactorCombiner:
    def test_orthogonalize_identity_for_single_factor(self):
        matrix = [[1.0], [2.0], [3.0]]
        result = FactorCombiner.orthogonalize(matrix)
        assert len(result) == 3
        assert len(result[0]) == 1
        assert result[0][0] == pytest.approx(1.0)

    def test_orthogonalize_removes_correlation(self):
        # 两个完全相关的因子
        matrix = [
            [1.0, 2.0],
            [2.0, 4.0],
            [3.0, 6.0],
            [4.0, 8.0],
        ]
        result = FactorCombiner.orthogonalize(matrix)
        # 第二个正交化因子应与第一个正交
        col0 = [r[0] for r in result]
        col1 = [r[1] for r in result]
        dot = sum(a * b for a, b in zip(col0, col1))
        assert dot == pytest.approx(0.0, abs=1e-10)

    def test_orthogonalize_empty_matrix(self):
        assert FactorCombiner.orthogonalize([]) == []
        assert FactorCombiner.orthogonalize([[]]) == []

    def test_stepwise_select_picks_best_factor(self):
        # 因子 a 与目标高度相关，因子 b 为噪声
        factor_values = [
            {"a": 1.0, "b": 0.9},
            {"a": 2.0, "b": 0.1},
            {"a": 3.0, "b": 0.8},
            {"a": 4.0, "b": 0.2},
            {"a": 5.0, "b": 0.7},
        ]
        target = [1.0, 2.0, 3.0, 4.0, 5.0]
        selected = FactorCombiner.stepwise_select(
            factor_values, target, ["a", "b"],
        )
        assert "a" in selected

    def test_stepwise_select_respects_max_factors(self):
        factor_values = [
            {"a": float(i), "b": float(i) * 0.5, "c": float(i) * 0.3}
            for i in range(10)
        ]
        target = [float(i) for i in range(10)]
        selected = FactorCombiner.stepwise_select(
            factor_values, target, ["a", "b", "c"], max_factors=2,
        )
        assert len(selected) <= 2

    def test_stepwise_select_empty(self):
        assert FactorCombiner.stepwise_select([], [], []) == []
