"""测试影子模式服务。"""

from datetime import datetime

import pytest

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


class TestShadowModeService:
    def test_construction(self) -> None:
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        service = ShadowModeService(active, shadow, repo)
        assert service.active_model.version_id == "v1"
        assert service.shadow_model.version_id == "v2"

    def test_rejects_shadow_as_active(self) -> None:
        active = _make_model("v1", ModelDeploymentStrategy.SHADOW, 0.0)
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        with pytest.raises(ValueError, match="active_model must not be SHADOW"):
            ShadowModeService(active, shadow, repo)

    def test_rejects_non_shadow_as_shadow(self) -> None:
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.FULL_ROLLOUT, 1.0)
        repo = FakeShadowLogRepository()
        with pytest.raises(ValueError, match="shadow_model must be SHADOW"):
            ShadowModeService(active, shadow, repo)

    def test_record_shadow_signals_basic(self) -> None:
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        service = ShadowModeService(active, shadow, repo)

        active_signals = {"600000.SH": ("BUY", 0.8), "000001.SZ": ("SELL", 0.6)}
        shadow_signals = {"600000.SH": ("BUY", 0.75), "000001.SZ": ("SELL", 0.55)}

        logs = service.record_shadow_signals(active_signals, shadow_signals)

        assert len(logs) == 2
        assert len(repo.saved) == 2
        assert all(isinstance(log, ShadowComparisonLog) for log in logs)

    def test_record_shadow_signals_matching_directions(self) -> None:
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        service = ShadowModeService(active, shadow, repo)

        active_signals = {"600000.SH": ("BUY", 0.8)}
        shadow_signals = {"600000.SH": ("BUY", 0.7)}

        logs = service.record_shadow_signals(active_signals, shadow_signals)
        log = logs[0]

        assert log.match is True
        assert log.active_direction == "BUY"
        assert log.shadow_direction == "BUY"
        assert abs(log.divergence - 0.1) < 1e-6

    def test_record_shadow_signals_mismatching_directions(self) -> None:
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        service = ShadowModeService(active, shadow, repo)

        active_signals = {"600000.SH": ("BUY", 0.8)}
        shadow_signals = {"600000.SH": ("SELL", 0.6)}

        logs = service.record_shadow_signals(active_signals, shadow_signals)
        log = logs[0]

        assert log.match is False
        assert log.active_direction == "BUY"
        assert log.shadow_direction == "SELL"

    def test_record_shadow_signals_only_active(self) -> None:
        """Shadow 模型未产出信号时，shadow_direction=HOLD。"""
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        service = ShadowModeService(active, shadow, repo)

        active_signals = {"600000.SH": ("BUY", 0.8)}
        shadow_signals: dict[str, tuple[str, float]] = {}

        logs = service.record_shadow_signals(active_signals, shadow_signals)
        log = logs[0]

        assert log.shadow_direction == "HOLD"
        assert log.shadow_confidence == 0.0

    def test_record_shadow_signals_only_shadow(self) -> None:
        """活跃模型未产出信号时，active_direction=HOLD。"""
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        service = ShadowModeService(active, shadow, repo)

        active_signals: dict[str, tuple[str, float]] = {}
        shadow_signals = {"600000.SH": ("BUY", 0.7)}

        logs = service.record_shadow_signals(active_signals, shadow_signals)
        log = logs[0]

        assert log.active_direction == "HOLD"
        assert log.active_confidence == 0.0

    def test_validate_shadow_empty_logs(self) -> None:
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        service = ShadowModeService(active, shadow, repo)

        result = service.validate_shadow()
        assert result.passed is False
        assert result.total_signals == 0

    def test_validate_shadow_passes_high_agreement(self) -> None:
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        service = ShadowModeService(active, shadow, repo, min_agreement_rate=0.6)

        # 80% agreement: 4/5 match
        active_signals = {
            "A": ("BUY", 0.8), "B": ("BUY", 0.7), "C": ("SELL", 0.6),
            "D": ("BUY", 0.9), "E": ("SELL", 0.5),
        }
        shadow_signals = {
            "A": ("BUY", 0.75), "B": ("SELL", 0.7), "C": ("SELL", 0.65),
            "D": ("BUY", 0.85), "E": ("SELL", 0.55),
        }
        service.record_shadow_signals(active_signals, shadow_signals)

        result = service.validate_shadow()
        assert result.passed is True
        assert result.total_signals == 5
        assert result.agreement_rate == 0.8

    def test_validate_shadow_fails_low_agreement(self) -> None:
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        service = ShadowModeService(active, shadow, repo, min_agreement_rate=0.8)

        # 50% agreement: 1/2 match
        active_signals = {"A": ("BUY", 0.8), "B": ("BUY", 0.7)}
        shadow_signals = {"A": ("BUY", 0.75), "B": ("SELL", 0.6)}
        service.record_shadow_signals(active_signals, shadow_signals)

        result = service.validate_shadow()
        assert result.passed is False
        assert result.agreement_rate == 0.5

    def test_validate_shadow_fails_high_confidence_diff(self) -> None:
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        service = ShadowModeService(
            active, shadow, repo,
            min_agreement_rate=0.5,
            max_confidence_diff=0.05,  # 很严格的阈值
        )

        # 100% agreement but high divergence (0.3 confidence diff)
        active_signals = {"A": ("BUY", 0.8)}
        shadow_signals = {"A": ("BUY", 0.5)}
        service.record_shadow_signals(active_signals, shadow_signals)

        result = service.validate_shadow()
        assert result.passed is False
        assert result.agreement_rate == 1.0  # 方向一致率很高

    def test_validate_shadow_result_is_frozen(self) -> None:
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        service = ShadowModeService(active, shadow, repo)

        result = service.validate_shadow()
        assert isinstance(result, ShadowValidationResult)

    def test_multiple_record_calls_accumulate(self) -> None:
        active = _make_model("v1")
        shadow = _make_model("v2", ModelDeploymentStrategy.SHADOW, 0.0)
        repo = FakeShadowLogRepository()
        service = ShadowModeService(active, shadow, repo)

        service.record_shadow_signals({"A": ("BUY", 0.8)}, {"A": ("BUY", 0.75)})
        service.record_shadow_signals({"B": ("SELL", 0.6)}, {"B": ("SELL", 0.55)})

        result = service.validate_shadow()
        assert result.total_signals == 2
