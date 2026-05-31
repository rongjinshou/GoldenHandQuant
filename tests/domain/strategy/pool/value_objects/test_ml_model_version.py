import pytest
from datetime import datetime

from src.domain.strategy.pool.value_objects.ml_model_version import MLModelVersion


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
