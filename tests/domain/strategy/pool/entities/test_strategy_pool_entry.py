import pytest
from datetime import datetime

from src.domain.strategy.pool.entities.strategy_pool_entry import StrategyPoolEntry
from src.domain.strategy.pool.value_objects.ml_model_version import MLModelVersion
from src.domain.strategy.pool.value_objects.performance_snapshot import PerformanceSnapshot
from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating
from src.domain.strategy.pool.value_objects.strategy_status import StrategyStatus


def _make_entry(**kwargs):
    defaults = dict(
        strategy_name="test_strategy",
        strategy_type="bar",
        description="test",
        registered_at=datetime(2026, 1, 1),
    )
    defaults.update(kwargs)
    return StrategyPoolEntry(**defaults)


def _make_snapshot(**kwargs):
    defaults = dict(
        evaluated_at=datetime(2026, 1, 1),
        period_start=datetime(2025, 12, 1),
        period_end=datetime(2025, 12, 31),
        total_return=0.10,
        annualized_return=0.15,
        sharpe_ratio=1.5,
        max_drawdown=0.10,
        win_rate=0.60,
        trade_count=50,
        composite_score=75.0,
        rating=StrategyRating.B,
    )
    defaults.update(kwargs)
    return PerformanceSnapshot(**defaults)


class TestStrategyPoolEntryInit:
    def test_valid_strategy_types(self):
        for st in ("bar", "cross_section", "ml"):
            entry = _make_entry(strategy_type=st)
            assert entry.strategy_type == st

    def test_invalid_strategy_type_raises(self):
        with pytest.raises(ValueError, match="Invalid strategy_type"):
            _make_entry(strategy_type="invalid")

    def test_default_status_is_candidate(self):
        entry = _make_entry()
        assert entry.status == StrategyStatus.CANDIDATE


class TestStatusTransitions:
    def test_candidate_to_active(self):
        entry = _make_entry()
        entry.activate()
        assert entry.status == StrategyStatus.ACTIVE

    def test_candidate_to_retired(self):
        entry = _make_entry()
        entry.retire()
        assert entry.status == StrategyStatus.RETIRED

    def test_candidate_cannot_pause(self):
        entry = _make_entry()
        with pytest.raises(ValueError, match="Invalid status transition"):
            entry.pause()

    def test_candidate_cannot_suspend(self):
        entry = _make_entry()
        with pytest.raises(ValueError, match="Invalid status transition"):
            entry.suspend()

    def test_active_to_paused(self):
        entry = _make_entry(status=StrategyStatus.ACTIVE)
        entry.pause()
        assert entry.status == StrategyStatus.PAUSED

    def test_active_to_suspended(self):
        entry = _make_entry(status=StrategyStatus.ACTIVE)
        entry.suspend()
        assert entry.status == StrategyStatus.SUSPENDED

    def test_active_to_retired(self):
        entry = _make_entry(status=StrategyStatus.ACTIVE)
        entry.retire()
        assert entry.status == StrategyStatus.RETIRED

    def test_paused_to_active(self):
        entry = _make_entry(status=StrategyStatus.PAUSED)
        entry.activate()
        assert entry.status == StrategyStatus.ACTIVE

    def test_paused_to_retired(self):
        entry = _make_entry(status=StrategyStatus.PAUSED)
        entry.retire()
        assert entry.status == StrategyStatus.RETIRED

    def test_suspended_to_active(self):
        entry = _make_entry(status=StrategyStatus.SUSPENDED)
        entry.activate()
        assert entry.status == StrategyStatus.ACTIVE

    def test_suspended_to_retired(self):
        entry = _make_entry(status=StrategyStatus.SUSPENDED)
        entry.retire()
        assert entry.status == StrategyStatus.RETIRED

    def test_retired_is_terminal(self):
        entry = _make_entry(status=StrategyStatus.RETIRED)
        with pytest.raises(ValueError, match="Invalid status transition"):
            entry.activate()
        with pytest.raises(ValueError, match="Invalid status transition"):
            entry.pause()
        with pytest.raises(ValueError, match="Invalid status transition"):
            entry.suspend()
        with pytest.raises(ValueError, match="Invalid status transition"):
            entry.retire()

    def test_pause_stores_reason(self):
        entry = _make_entry(status=StrategyStatus.ACTIVE)
        entry.pause(reason="market mismatch")
        assert entry.notes == "market mismatch"

    def test_suspend_stores_reason(self):
        entry = _make_entry(status=StrategyStatus.ACTIVE)
        entry.suspend(reason="drawdown exceeded")
        assert entry.notes == "drawdown exceeded"


class TestSnapshotAndRating:
    def test_add_snapshot(self):
        entry = _make_entry()
        snap = _make_snapshot()
        entry.add_snapshot(snap)
        assert len(entry.snapshots) == 1
        assert entry.latest_snapshot is snap

    def test_latest_snapshot_none_when_empty(self):
        entry = _make_entry()
        assert entry.latest_snapshot is None

    def test_update_rating(self):
        entry = _make_entry()
        entry.update_rating(StrategyRating.A)
        assert entry.rating == StrategyRating.A


class TestIsTradeable:
    def test_active_is_tradeable(self):
        entry = _make_entry(status=StrategyStatus.ACTIVE)
        assert entry.is_tradeable is True

    def test_candidate_not_tradeable(self):
        entry = _make_entry()
        assert entry.is_tradeable is False

    def test_paused_not_tradeable(self):
        entry = _make_entry(status=StrategyStatus.PAUSED)
        assert entry.is_tradeable is False


class TestShouldAutoRetire:
    def test_few_snapshots_returns_false(self):
        entry = _make_entry(status=StrategyStatus.ACTIVE)
        for i in range(3):
            entry.add_snapshot(_make_snapshot(underperform_weeks=i + 1))
        assert entry.should_auto_retire is False

    def test_four_consecutive_underperform_weeks(self):
        entry = _make_entry(status=StrategyStatus.ACTIVE)
        for i in range(4):
            entry.add_snapshot(_make_snapshot(underperform_weeks=i + 1))
        assert entry.should_auto_retire is True

    def test_four_consecutive_d_ratings(self):
        entry = _make_entry(status=StrategyStatus.ACTIVE)
        for _ in range(4):
            entry.add_snapshot(_make_snapshot(rating=StrategyRating.D, composite_score=20.0))
        assert entry.should_auto_retire is True

    def test_mixed_ratings_no_retire(self):
        entry = _make_entry(status=StrategyStatus.ACTIVE)
        ratings = [StrategyRating.A, StrategyRating.B, StrategyRating.C, StrategyRating.D]
        for r in ratings:
            entry.add_snapshot(_make_snapshot(rating=r))
        assert entry.should_auto_retire is False


class TestMLModelVersion:
    def _make_version(self, vid, active=False):
        return MLModelVersion(
            version_id=vid,
            model_type="lightgbm",
            trained_at=datetime(2026, 1, 1),
            training_samples=10000,
            feature_count=30,
            is_active=active,
        )

    def test_add_model_version(self):
        entry = _make_entry(strategy_type="ml")
        v = self._make_version("v1")
        entry.add_model_version(v)
        assert len(entry.ml_versions) == 1

    def test_activate_model_version(self):
        entry = _make_entry(strategy_type="ml")
        entry.add_model_version(self._make_version("v1", active=True))
        entry.add_model_version(self._make_version("v2"))
        entry.activate_model_version("v2")
        assert entry.active_model_version.version_id == "v2"
        assert not entry.ml_versions[0].is_active

    def test_activate_nonexistent_version_raises(self):
        entry = _make_entry(strategy_type="ml")
        entry.add_model_version(self._make_version("v1"))
        with pytest.raises(ValueError, match="Model version not found"):
            entry.activate_model_version("v99")

    def test_rollback_model_version(self):
        entry = _make_entry(strategy_type="ml")
        entry.add_model_version(self._make_version("v1"))
        entry.add_model_version(self._make_version("v2", active=True))
        result = entry.rollback_model_version()
        assert result == "v1"
        assert entry.active_model_version.version_id == "v1"

    def test_rollback_at_first_version_returns_none(self):
        entry = _make_entry(strategy_type="ml")
        entry.add_model_version(self._make_version("v1", active=True))
        result = entry.rollback_model_version()
        assert result is None

    def test_rollback_no_active_returns_none(self):
        entry = _make_entry(strategy_type="ml")
        entry.add_model_version(self._make_version("v1"))
        entry.add_model_version(self._make_version("v2"))
        result = entry.rollback_model_version()
        assert result is None

    def test_active_model_version_none_when_empty(self):
        entry = _make_entry(strategy_type="ml")
        assert entry.active_model_version is None
