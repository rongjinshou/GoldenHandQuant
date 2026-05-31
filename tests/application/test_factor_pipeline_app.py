"""因子研发流水线应用服务测试。"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.application.factor_pipeline_app import FactorPipelineAppService
from src.domain.strategy.factor_test.report import FactorTestReport
from src.domain.strategy.services.factor_pipeline import FactorPipelineService
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
    """高分报告（评分 >= 60）。"""
    return _make_report(
        ic_mean=0.06,
        ir=0.6,
        long_short_return=0.18,
        monotonicity_score=0.9,
    )


def _make_bad_report() -> FactorTestReport:
    """低分报告（评分 < 40）。"""
    return _make_report(
        ic_mean=0.005,
        ir=0.05,
        long_short_return=0.01,
        monotonicity_score=0.1,
    )


# ---------------------------------------------------------------------------
# FactorPipelineAppService 测试
# ---------------------------------------------------------------------------

class TestFactorPipelineAppService:
    def setup_method(self):
        self.pipeline = FactorPipelineService(
            activate_score=60.0,
            validate_score=40.0,
        )
        self.app = FactorPipelineAppService(pipeline=self.pipeline)

    # -- submit_factor --

    def test_submit_factor_enters_testing(self):
        result = self.app.submit_factor("f1", "rank(close)")
        assert result["status"] == FactorLifecycleStatus.TESTING
        assert result["factor_name"] == "f1"

    # -- process_test_result --

    def test_process_test_result_validates(self):
        self.app.submit_factor("f1", "rank(close)")
        result = self.app.process_test_result("f1", _make_good_report())
        assert result["status"] == FactorLifecycleStatus.VALIDATED
        assert result["score"] >= 40.0

    def test_process_test_result_rejects(self):
        self.app.submit_factor("f1", "rank(close)")
        result = self.app.process_test_result("f1", _make_bad_report())
        assert result["status"] == FactorLifecycleStatus.DISCOVERED
        assert result["score"] < 40.0

    # -- activate_factor --

    def test_activate_factor(self):
        self.app.submit_factor("f1", "rank(close)")
        self.app.process_test_result("f1", _make_good_report())
        result = self.app.activate_factor("f1")
        assert result["status"] == FactorLifecycleStatus.ACTIVE

    def test_activate_factor_fails_when_not_validated(self):
        self.app.submit_factor("f1", "rank(close)")
        self.app.process_test_result("f1", _make_bad_report())
        with pytest.raises(ValueError, match="must be VALIDATED"):
            self.app.activate_factor("f1")

    # -- run_full_pipeline --

    def test_run_full_pipeline_validates_and_activates(self):
        result = self.app.run_full_pipeline(
            "f1", "rank(close)", _make_good_report(), auto_activate=True,
        )
        assert result["status"] == FactorLifecycleStatus.ACTIVE

    def test_run_full_pipeline_no_auto_activate(self):
        result = self.app.run_full_pipeline(
            "f1", "rank(close)", _make_good_report(), auto_activate=False,
        )
        assert result["status"] == FactorLifecycleStatus.VALIDATED

    def test_run_full_pipeline_rejects_bad_factor(self):
        result = self.app.run_full_pipeline(
            "f1", "rank(close)", _make_bad_report(), auto_activate=True,
        )
        assert result["status"] == FactorLifecycleStatus.DISCOVERED

    # -- 衰减监控 --

    def test_check_decay(self):
        self.app.submit_factor("f1", "rank(close)")
        self.app.process_test_result("f1", _make_good_report())
        self.app.activate_factor("f1")

        entry = self.pipeline.get_entry("f1")
        result = self.app.check_decay("f1", current_ic_mean=entry.validation_ic * 0.3)
        assert result["is_decayed"] is True
        assert result["ic_ratio"] == pytest.approx(0.3)

    def test_check_decay_no_decay(self):
        self.app.submit_factor("f1", "rank(close)")
        self.app.process_test_result("f1", _make_good_report())
        self.app.activate_factor("f1")

        entry = self.pipeline.get_entry("f1")
        result = self.app.check_decay("f1", current_ic_mean=entry.validation_ic * 0.8)
        assert result["is_decayed"] is False

    def test_batch_check_decay(self):
        self.app.submit_factor("f1", "rank(close)")
        self.app.process_test_result("f1", _make_good_report())
        self.app.activate_factor("f1")

        self.app.submit_factor("f2", "rank(earnings)")
        self.app.process_test_result("f2", _make_good_report())
        self.app.activate_factor("f2")

        entry1 = self.pipeline.get_entry("f1")
        entry2 = self.pipeline.get_entry("f2")

        results = self.app.batch_check_decay({
            "f1": entry1.validation_ic * 0.3,
            "f2": entry2.validation_ic * 0.8,
        })
        assert len(results) == 2
        decayed = [r for r in results if r["is_decayed"]]
        assert len(decayed) == 1
        assert decayed[0]["factor_name"] == "f1"

    # -- 因子组合优化 --

    def test_orthogonalize_factors(self):
        matrix = [
            [1.0, 2.0],
            [2.0, 4.0],
            [3.0, 6.0],
        ]
        result = self.app.orthogonalize_factors(matrix)
        assert len(result) == 3
        assert len(result[0]) == 2

    def test_select_factors(self):
        # 因子 a 与目标高度相关，因子 b 为噪声
        factor_values = [
            {"a": float(i), "b": float((i * 7 + 3) % 10)}
            for i in range(10)
        ]
        target = [float(i) for i in range(10)]
        selected = self.app.select_factors(
            factor_values, target, ["a", "b"],
        )
        assert len(selected) >= 1
        assert "a" in selected

    # -- 查询 --

    def test_get_factor_status(self):
        assert self.app.get_factor_status("nonexistent") is None
        self.app.submit_factor("f1", "rank(close)")
        assert self.app.get_factor_status("f1") == FactorLifecycleStatus.TESTING

    def test_get_active_factors(self):
        self.app.submit_factor("f1", "rank(close)")
        self.app.process_test_result("f1", _make_good_report())
        self.app.activate_factor("f1")
        active = self.app.get_active_factors()
        assert len(active) == 1
        assert active[0]["factor_name"] == "f1"

    def test_get_summary(self):
        self.app.submit_factor("f1", "rank(close)")
        self.app.submit_factor("f2", "rank(earnings)")
        summary = self.app.get_summary()
        assert summary["total"] == 2

    def test_retire_factor(self):
        self.app.submit_factor("f1", "rank(close)")
        result = self.app.retire_factor("f1", reason="manual retire")
        assert result["status"] == FactorLifecycleStatus.RETIRED
        assert result["reason"] == "manual retire"

    # -- 完整流水线集成 --

    def test_full_pipeline_submit_to_active(self):
        """完整流水线: 提交 → 检验 → 入库 → 激活。"""
        # 提交
        result = self.app.submit_factor("momentum_20d", "rank(return_20d)")
        assert result["status"] == FactorLifecycleStatus.TESTING

        # 检验通过
        result = self.app.process_test_result("momentum_20d", _make_good_report())
        assert result["status"] == FactorLifecycleStatus.VALIDATED

        # 激活
        result = self.app.activate_factor("momentum_20d")
        assert result["status"] == FactorLifecycleStatus.ACTIVE

        # 验证活跃
        active = self.app.get_active_factors()
        assert len(active) == 1

    def test_full_pipeline_with_decay_cycle(self):
        """完整流水线含衰减和重新验证循环。"""
        # 上线
        self.app.submit_factor("f1", "rank(close)")
        self.app.process_test_result("f1", _make_good_report())
        self.app.activate_factor("f1")

        # 衰减
        entry = self.pipeline.get_entry("f1")
        self.app.check_decay("f1", current_ic_mean=entry.validation_ic * 0.3)
        assert self.app.get_factor_status("f1") == FactorLifecycleStatus.DECAYED

        # 重新验证
        self.pipeline.revalidate_factor("f1")
        assert self.app.get_factor_status("f1") == FactorLifecycleStatus.TESTING

        # 再次通过检验
        self.app.process_test_result("f1", _make_good_report())
        assert self.app.get_factor_status("f1") == FactorLifecycleStatus.VALIDATED
