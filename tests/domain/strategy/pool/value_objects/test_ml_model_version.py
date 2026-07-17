from datetime import datetime

import pytest

from src.domain.strategy.pool.value_objects.ml_model_version import MLModelVersion
from src.domain.strategy.value_objects.model_deployment_strategy import (
    ModelDeploymentStrategy,
)


class TestMLModelVersion:
    def _make_version(self, **kwargs):
        defaults = dict(
            version_id="v1.0.0",
            model_type="lightgbm",
            trained_at=datetime(2026, 1, 1),
            training_samples=10000,
            feature_count=30,
        )
        defaults.update(kwargs)
        return MLModelVersion(**defaults)

    def test_creation(self):
        v = self._make_version()
        assert v.version_id == "v1.0.0"
        assert v.is_active is False

    def test_immutability(self):
        v = self._make_version()
        with pytest.raises(AttributeError):
            v.is_active = True  # type: ignore[misc]

    def test_default_metrics_empty(self):
        v = self._make_version()
        assert v.metrics == {}
        assert v.notes == ""

    def test_default_deployment_full_rollout(self):
        v = self._make_version()
        assert v.deployment == ModelDeploymentStrategy.FULL_ROLLOUT
        assert v.traffic_percentage == 1.0

    def test_custom_deployment(self):
        v = self._make_version(
            deployment=ModelDeploymentStrategy.SHADOW,
            traffic_percentage=0.0,
        )
        assert v.deployment == ModelDeploymentStrategy.SHADOW
        assert v.traffic_percentage == 0.0

    def test_invalid_traffic_percentage_above_one(self):
        with pytest.raises(ValueError, match="traffic_percentage"):
            self._make_version(traffic_percentage=1.5)

    def test_invalid_traffic_percentage_negative(self):
        with pytest.raises(ValueError, match="traffic_percentage"):
            self._make_version(traffic_percentage=-0.1)

    def test_with_deployment(self):
        v = self._make_version()
        v2 = v.with_deployment(ModelDeploymentStrategy.CANARY, 0.3)
        assert v2.deployment == ModelDeploymentStrategy.CANARY
        assert v2.traffic_percentage == 0.3
        # 原实例不变
        assert v.deployment == ModelDeploymentStrategy.FULL_ROLLOUT
        assert v.traffic_percentage == 1.0

    def test_with_active(self):
        v = self._make_version()
        v2 = v.with_active(True)
        assert v2.is_active is True
        assert v.is_active is False
