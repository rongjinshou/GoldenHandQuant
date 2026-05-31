"""测试 ML 模型灰度发布应用服务。"""

from datetime import datetime

import pytest

from src.application.ml_deployment_app import (
    MLDeploymentAppService,
    ModelDeploymentState,
)
from src.domain.strategy.pool.value_objects.ml_model_version import MLModelVersion
from src.domain.strategy.services.shadow_mode_service import (
    ShadowModeService,
    ShadowValidationResult,
)
from src.domain.strategy.value_objects.model_deployment_strategy import (
    ModelDeploymentStrategy,
)
from src.domain.strategy.value_objects.shadow_comparison_log import ShadowComparisonLog


class FakeShadowLogRepository:
    """Fake 影子日志仓储。"""

    def __init__(self) -> None:
        self.saved: list[ShadowComparisonLog] = []

    def save(self, log: ShadowComparisonLog) -> None:
        self.saved.append(log)

    def find_by_model_pair(
        self,
        active_version_id: str,
        shadow_version_id: str,
    ) -> list[ShadowComparisonLog]:
        return [
            log for log in self.saved
            if log.active_version_id == active_version_id
            and log.shadow_version_id == shadow_version_id
        ]


class FakeDriftDetector:
    """Fake 漂移检测器。"""

    def __init__(self, has_drift: bool = False) -> None:
        self._has_drift = has_drift
        self.check_count = 0

    def check_drift(self) -> bool:
        self.check_count += 1
        return self._has_drift


class FakeRetrainCallback:
    """Fake 重训练回调。"""

    def __init__(self) -> None:
        self.call_count = 0

    def retrain(self) -> MLModelVersion:
        self.call_count += 1
        return MLModelVersion(
            version_id=f"retrained_{self.call_count}",
            model_type="lightgbm",
            trained_at=datetime.now(),
            training_samples=10000,
            feature_count=30,
        )


def _make_model(
    version_id: str = "v1",
    deployment: ModelDeploymentStrategy = ModelDeploymentStrategy.FULL_ROLLOUT,
    traffic: float = 1.0,
) -> MLModelVersion:
    return MLModelVersion(
        version_id=version_id,
        model_type="lightgbm",
        trained_at=datetime(2026, 1, 1),
        training_samples=10000,
        feature_count=30,
        deployment=deployment,
        traffic_percentage=traffic,
    )


class TestMLDeploymentAppService:
    def test_deploy_shadow(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        svc = MLDeploymentAppService(drift, retrain)

        model = _make_model("v1")
        result = svc.deploy_shadow(model)

        assert result.deployment == ModelDeploymentStrategy.SHADOW
        assert result.traffic_percentage == 0.0
        assert result.version_id == "v1"

    def test_deploy_shadow_tracks_state(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        svc = MLDeploymentAppService(drift, retrain)

        model = _make_model("v1")
        svc.deploy_shadow(model)

        state = svc.get_deployment_state("v1")
        assert state is not None
        assert state.model.deployment == ModelDeploymentStrategy.SHADOW
        assert state.validated is False

    def test_setup_shadow_comparison(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        shadow_repo = FakeShadowLogRepository()
        svc = MLDeploymentAppService(drift, retrain, shadow_log_repository=shadow_repo)

        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        service = svc.setup_shadow_comparison(active, shadow)

        assert isinstance(service, ShadowModeService)
        assert service.active_model.version_id == "v1"
        assert service.shadow_model.version_id == "v2"

    def test_validate_shadow_without_setup_raises(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        svc = MLDeploymentAppService(drift, retrain)

        with pytest.raises(ValueError, match="Shadow comparison not set up"):
            svc.validate_shadow("v2")

    def test_validate_shadow_wrong_version_raises(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        shadow_repo = FakeShadowLogRepository()
        svc = MLDeploymentAppService(drift, retrain, shadow_log_repository=shadow_repo)

        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        svc.setup_shadow_comparison(active, shadow)

        with pytest.raises(ValueError, match="Shadow version mismatch"):
            svc.validate_shadow("wrong_version")

    def test_validate_shadow_passes(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        shadow_repo = FakeShadowLogRepository()
        svc = MLDeploymentAppService(
            drift, retrain,
            shadow_log_repository=shadow_repo,
            min_agreement_rate=0.5,
        )

        active = _make_model("v1")
        new_model = _make_model("v2")
        shadow = svc.deploy_shadow(new_model)
        shadow_svc = svc.setup_shadow_comparison(active, shadow)

        # Record some matching signals
        shadow_svc.record_shadow_signals(
            {"A": ("BUY", 0.8), "B": ("SELL", 0.6)},
            {"A": ("BUY", 0.75), "B": ("SELL", 0.55)},
        )

        result = svc.validate_shadow("v2")
        assert result.passed is True

        state = svc.get_deployment_state("v2")
        assert state is not None
        assert state.validated is True

    def test_validate_shadow_fails(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        shadow_repo = FakeShadowLogRepository()
        svc = MLDeploymentAppService(
            drift, retrain,
            shadow_log_repository=shadow_repo,
            min_agreement_rate=0.9,  # 高阈值
        )

        active = _make_model("v1")
        new_model = _make_model("v2")
        shadow = svc.deploy_shadow(new_model)
        shadow_svc = svc.setup_shadow_comparison(active, shadow)

        # 50% agreement
        shadow_svc.record_shadow_signals(
            {"A": ("BUY", 0.8), "B": ("BUY", 0.6)},
            {"A": ("BUY", 0.75), "B": ("SELL", 0.55)},
        )

        result = svc.validate_shadow("v2")
        assert result.passed is False

    def test_promote_to_canary_after_validation(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        shadow_repo = FakeShadowLogRepository()
        svc = MLDeploymentAppService(
            drift, retrain,
            shadow_log_repository=shadow_repo,
            min_agreement_rate=0.5,
            canary_traffic_percentage=0.3,
        )

        active = _make_model("v1")
        new_model = _make_model("v2")
        shadow = svc.deploy_shadow(new_model)
        shadow_svc = svc.setup_shadow_comparison(active, shadow)

        shadow_svc.record_shadow_signals(
            {"A": ("BUY", 0.8)},
            {"A": ("BUY", 0.75)},
        )
        svc.validate_shadow("v2")

        canary = svc.promote_to_canary("v2")
        assert canary.deployment == ModelDeploymentStrategy.CANARY
        assert canary.traffic_percentage == 0.3

    def test_promote_to_canary_without_validation_raises(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        svc = MLDeploymentAppService(drift, retrain)

        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        svc.deploy_shadow(shadow)

        with pytest.raises(ValueError, match="has not passed shadow validation"):
            svc.promote_to_canary("v2")

    def test_promote_to_canary_unknown_model_raises(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        svc = MLDeploymentAppService(drift, retrain)

        with pytest.raises(ValueError, match="not found in deployments"):
            svc.promote_to_canary("unknown")

    def test_promote_to_full_rollout(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        shadow_repo = FakeShadowLogRepository()
        svc = MLDeploymentAppService(
            drift, retrain,
            shadow_log_repository=shadow_repo,
            min_agreement_rate=0.5,
        )

        active = _make_model("v1")
        new_model = _make_model("v2")
        shadow = svc.deploy_shadow(new_model)
        shadow_svc = svc.setup_shadow_comparison(active, shadow)

        shadow_svc.record_shadow_signals(
            {"A": ("BUY", 0.8)},
            {"A": ("BUY", 0.75)},
        )
        svc.validate_shadow("v2")
        svc.promote_to_canary("v2")

        full = svc.promote_to_full_rollout("v2")
        assert full.deployment == ModelDeploymentStrategy.FULL_ROLLOUT
        assert full.traffic_percentage == 1.0

    def test_promote_to_full_rollout_not_canary_raises(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        svc = MLDeploymentAppService(drift, retrain)

        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        svc.deploy_shadow(shadow)

        with pytest.raises(ValueError, match="is not in CANARY state"):
            svc.promote_to_full_rollout("v2")

    def test_health_check_no_drift(self) -> None:
        drift = FakeDriftDetector(has_drift=False)
        retrain = FakeRetrainCallback()
        svc = MLDeploymentAppService(drift, retrain)

        result = svc.run_health_check()
        assert result is None
        assert drift.check_count == 1
        assert retrain.call_count == 0

    def test_health_check_with_drift_triggers_retrain(self) -> None:
        drift = FakeDriftDetector(has_drift=True)
        retrain = FakeRetrainCallback()
        svc = MLDeploymentAppService(drift, retrain)

        result = svc.run_health_check()
        assert result is not None
        assert result.deployment == ModelDeploymentStrategy.SHADOW
        assert drift.check_count == 1
        assert retrain.call_count == 1

    def test_get_all_deployments(self) -> None:
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        svc = MLDeploymentAppService(drift, retrain)

        svc.deploy_shadow(_make_model("v1"))
        svc.deploy_shadow(_make_model("v2"))

        all_deps = svc.get_all_deployments()
        assert len(all_deps) == 2
        assert "v1" in all_deps
        assert "v2" in all_deps

    def test_full_deployment_lifecycle(self) -> None:
        """端到端测试: SHADOW → 验证 → CANARY → FULL_ROLLOUT。"""
        drift = FakeDriftDetector()
        retrain = FakeRetrainCallback()
        shadow_repo = FakeShadowLogRepository()
        svc = MLDeploymentAppService(
            drift, retrain,
            shadow_log_repository=shadow_repo,
            min_agreement_rate=0.5,
            canary_traffic_percentage=0.2,
        )

        active = _make_model("v1")
        new_model = _make_model("v2")

        # 1. Deploy as shadow
        shadow = svc.deploy_shadow(new_model)
        assert shadow.deployment == ModelDeploymentStrategy.SHADOW

        # 2. Setup and record shadow signals
        shadow_svc = svc.setup_shadow_comparison(active, shadow)
        shadow_svc.record_shadow_signals(
            {"600000.SH": ("BUY", 0.8), "000001.SZ": ("SELL", 0.6)},
            {"600000.SH": ("BUY", 0.75), "000001.SZ": ("SELL", 0.55)},
        )

        # 3. Validate
        result = svc.validate_shadow("v2")
        assert result.passed is True

        # 4. Promote to canary
        canary = svc.promote_to_canary("v2")
        assert canary.deployment == ModelDeploymentStrategy.CANARY
        assert canary.traffic_percentage == 0.2

        # 5. Promote to full rollout
        full = svc.promote_to_full_rollout("v2")
        assert full.deployment == ModelDeploymentStrategy.FULL_ROLLOUT
        assert full.traffic_percentage == 1.0
