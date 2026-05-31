"""测试影子模式对比日志值对象。"""

from datetime import datetime

import pytest

from src.domain.strategy.value_objects.shadow_comparison_log import ShadowComparisonLog


class TestShadowComparisonLog:
    def _make_log(self, **kwargs):
        defaults = dict(
            active_version_id="v1",
            shadow_version_id="v2",
            symbol="600000.SH",
            active_direction="BUY",
            shadow_direction="BUY",
            active_confidence=0.8,
            shadow_confidence=0.75,
            match=True,
            divergence=0.05,
            recorded_at=datetime(2026, 6, 1),
        )
        defaults.update(kwargs)
        return ShadowComparisonLog(**defaults)

    def test_creation(self) -> None:
        log = self._make_log()
        assert log.active_version_id == "v1"
        assert log.shadow_version_id == "v2"
        assert log.symbol == "600000.SH"
        assert log.active_direction == "BUY"
        assert log.shadow_direction == "BUY"
        assert log.match is True
        assert log.divergence == 0.05

    def test_immutability(self) -> None:
        log = self._make_log()
        with pytest.raises(AttributeError):
            log.match = False  # type: ignore[misc]

    def test_invalid_active_confidence(self) -> None:
        with pytest.raises(ValueError, match="active_confidence"):
            self._make_log(active_confidence=1.5)

    def test_invalid_shadow_confidence(self) -> None:
        with pytest.raises(ValueError, match="shadow_confidence"):
            self._make_log(shadow_confidence=-0.1)

    def test_invalid_divergence(self) -> None:
        with pytest.raises(ValueError, match="divergence"):
            self._make_log(divergence=1.5)

    def test_compute_divergence_matching_directions(self) -> None:
        # 方向一致: 差异 = |confidence_a - confidence_s|
        div = ShadowComparisonLog.compute_divergence(
            active_confidence=0.8,
            shadow_confidence=0.7,
            directions_match=True,
        )
        assert abs(div - 0.1) < 1e-6

    def test_compute_divergence_matching_same_confidence(self) -> None:
        div = ShadowComparisonLog.compute_divergence(
            active_confidence=0.8,
            shadow_confidence=0.8,
            directions_match=True,
        )
        assert div == 0.0

    def test_compute_divergence_mismatching_directions(self) -> None:
        # 方向不一致: 差异 = 1.0 - |confidence_a - confidence_s| * 0.5
        div = ShadowComparisonLog.compute_divergence(
            active_confidence=0.8,
            shadow_confidence=0.6,
            directions_match=False,
        )
        expected = 1.0 - abs(0.8 - 0.6) * 0.5
        assert abs(div - expected) < 1e-6

    def test_compute_divergence_mismatching_same_confidence(self) -> None:
        div = ShadowComparisonLog.compute_divergence(
            active_confidence=0.5,
            shadow_confidence=0.5,
            directions_match=False,
        )
        assert div == 1.0
