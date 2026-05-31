from datetime import datetime

from src.domain.trade.services.algo_strategies.iceberg_strategy import IcebergStrategy
from src.domain.trade.value_objects.algo_order_config import AlgoOrderConfig
from src.domain.trade.value_objects.order_direction import OrderDirection


class TestIcebergStrategy:
    def _make_config(
        self,
        total_volume: int = 1000,
        display_volume: int = 200,
        direction: OrderDirection = OrderDirection.BUY,
        price_limit: float = 10.0,
    ) -> AlgoOrderConfig:
        return AlgoOrderConfig(
            symbol="600000.SH",
            direction=direction,
            total_volume=total_volume,
            price_limit=price_limit,
            algo_type="iceberg",
            display_volume=display_volume,
        )

    def test_generate_slices_creates_correct_number(self):
        # Arrange
        strategy = IcebergStrategy()
        config = self._make_config(total_volume=1000, display_volume=200)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        assert len(slices) == 5  # 1000 / 200 = 5

    def test_generate_slices_total_volume_matches(self):
        # Arrange
        strategy = IcebergStrategy()
        config = self._make_config(total_volume=1000, display_volume=300)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        total = sum(s.volume for s in slices)
        assert total == 1000

    def test_generate_slices_last_slice_gets_remainder(self):
        # Arrange
        strategy = IcebergStrategy()
        config = self._make_config(total_volume=1000, display_volume=300)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        # 1000 / 300 = 3 余 100
        assert len(slices) == 4  # 300 + 300 + 300 + 100
        assert slices[-1].volume == 100

    def test_generate_slices_all_share_parent_algo_id(self):
        # Arrange
        strategy = IcebergStrategy()
        config = self._make_config(total_volume=500, display_volume=100)

        # Act
        slices = strategy.generate_slices(config, "parent-123")

        # Assert
        for s in slices:
            assert s.parent_algo_id == "parent-123"

    def test_generate_slices_buy_volume_rounded_to_100(self):
        # Arrange
        strategy = IcebergStrategy()
        config = self._make_config(
            total_volume=500, display_volume=150, direction=OrderDirection.BUY,
        )

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        for s in slices:
            assert s.volume % 100 == 0 or s == slices[-1]

    def test_generate_slices_sell_volume_not_rounded_to_100(self):
        # Arrange
        strategy = IcebergStrategy()
        config = self._make_config(
            total_volume=50, display_volume=20, direction=OrderDirection.SELL,
        )

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        total = sum(s.volume for s in slices)
        assert total == 50

    def test_generate_slices_sequential_schedule(self):
        # Arrange
        strategy = IcebergStrategy()
        start = datetime(2026, 1, 1, 9, 30)
        config = self._make_config(total_volume=400, display_volume=100)

        # Act
        slices = strategy.generate_slices(config, "algo-1", start_time=start)

        # Assert
        for i in range(len(slices) - 1):
            assert slices[i + 1].scheduled_at >= slices[i].scheduled_at

    def test_generate_slices_exact_multiple_no_remainder(self):
        # Arrange
        strategy = IcebergStrategy()
        config = self._make_config(total_volume=500, display_volume=100)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        assert len(slices) == 5
        for s in slices:
            assert s.volume == 100
