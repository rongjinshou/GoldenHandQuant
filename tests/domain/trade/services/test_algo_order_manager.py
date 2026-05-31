import pytest

from src.domain.trade.services.algo_order_manager import AlgoOrderManager
from src.domain.trade.value_objects.algo_order_config import AlgoOrderConfig
from src.domain.trade.value_objects.algo_order_status import AlgoOrderStatus
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_status import OrderStatus


class TestAlgoOrderManager:
    def _make_config(
        self,
        algo_type: str = "twap",
        total_volume: int = 1000,
        num_slices: int = 5,
        display_volume: int = 200,
    ) -> AlgoOrderConfig:
        return AlgoOrderConfig(
            symbol="600000.SH",
            direction=OrderDirection.BUY,
            total_volume=total_volume,
            price_limit=10.0,
            algo_type=algo_type,
            num_slices=num_slices,
            display_volume=display_volume,
        )

    def test_create_twap_algo_order(self):
        # Arrange
        manager = AlgoOrderManager()
        config = self._make_config(algo_type="twap", num_slices=5)

        # Act
        algo_id, slices = manager.create_algo_order(config)

        # Assert
        assert algo_id
        assert len(slices) == 5
        progress = manager.get_progress(algo_id)
        assert progress.status == AlgoOrderStatus.PENDING
        assert progress.total_volume == 1000

    def test_create_vwap_algo_order(self):
        # Arrange
        manager = AlgoOrderManager()
        config = self._make_config(algo_type="vwap", num_slices=4)

        # Act
        algo_id, slices = manager.create_algo_order(config)

        # Assert
        assert len(slices) == 4
        total = sum(s.volume for s in slices)
        assert total == 1000

    def test_create_iceberg_algo_order(self):
        # Arrange
        manager = AlgoOrderManager()
        config = self._make_config(algo_type="iceberg", total_volume=1000, display_volume=200)

        # Act
        algo_id, slices = manager.create_algo_order(config)

        # Assert
        assert len(slices) == 5

    def test_create_unsupported_algo_type_raises(self):
        # Arrange
        manager = AlgoOrderManager()
        config = self._make_config(algo_type="unsupported")

        # Act & Assert
        with pytest.raises(ValueError, match="不支持的算法类型"):
            manager.create_algo_order(config)

    def test_start_changes_status_to_running(self):
        # Arrange
        manager = AlgoOrderManager()
        config = self._make_config()
        algo_id, _ = manager.create_algo_order(config)

        # Act
        manager.start(algo_id)

        # Assert
        progress = manager.get_progress(algo_id)
        assert progress.status == AlgoOrderStatus.RUNNING
        assert progress.started_at is not None

    def test_update_slice_status_tracks_progress(self):
        # Arrange
        manager = AlgoOrderManager()
        config = self._make_config(algo_type="twap", total_volume=500, num_slices=5)
        algo_id, slices = manager.create_algo_order(config)
        manager.start(algo_id)

        # Act
        manager.update_slice_status(algo_id, slices[0].slice_id, "order-1", OrderStatus.FILLED)

        # Assert
        progress = manager.get_progress(algo_id)
        assert progress.filled_volume == slices[0].volume
        assert progress.num_slices_filled == 1

    def test_all_slices_filled_marks_completed(self):
        # Arrange
        manager = AlgoOrderManager()
        config = self._make_config(algo_type="twap", total_volume=500, num_slices=5)
        algo_id, slices = manager.create_algo_order(config)
        manager.start(algo_id)

        # Act
        for i, s in enumerate(slices):
            manager.update_slice_status(algo_id, s.slice_id, f"order-{i}", OrderStatus.FILLED)

        # Assert
        progress = manager.get_progress(algo_id)
        assert progress.status == AlgoOrderStatus.COMPLETED
        assert progress.filled_volume == 500
        assert progress.remaining_volume == 0

    def test_cancel_algo_order(self):
        # Arrange
        manager = AlgoOrderManager()
        config = self._make_config()
        algo_id, _ = manager.create_algo_order(config)
        manager.start(algo_id)

        # Act
        progress = manager.cancel(algo_id)

        # Assert
        assert progress.status == AlgoOrderStatus.CANCELED

    def test_get_nonexistent_algo_raises(self):
        # Arrange
        manager = AlgoOrderManager()

        # Act & Assert
        with pytest.raises(KeyError, match="算法订单不存在"):
            manager.get_progress("nonexistent")

    def test_get_pending_slices(self):
        # Arrange
        manager = AlgoOrderManager()
        config = self._make_config(num_slices=5)
        algo_id, slices = manager.create_algo_order(config)

        # Act
        pending = manager.get_pending_slices(algo_id)

        # Assert
        assert len(pending) == 5

    def test_fill_ratio_property(self):
        # Arrange
        manager = AlgoOrderManager()
        config = self._make_config(algo_type="twap", total_volume=1000, num_slices=4)
        algo_id, slices = manager.create_algo_order(config)
        manager.start(algo_id)

        # Act
        manager.update_slice_status(algo_id, slices[0].slice_id, "o-1", OrderStatus.FILLED)

        # Assert
        progress = manager.get_progress(algo_id)
        assert progress.fill_ratio == pytest.approx(slices[0].volume / 1000)
