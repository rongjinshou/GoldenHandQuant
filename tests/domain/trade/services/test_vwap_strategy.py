from datetime import datetime

from src.domain.trade.services.algo_strategies.vwap_strategy import VwapStrategy
from src.domain.trade.value_objects.algo_order_config import AlgoOrderConfig
from src.domain.trade.value_objects.order_direction import OrderDirection


class TestVwapStrategy:
    def _make_config(
        self,
        total_volume: int = 1000,
        num_slices: int = 5,
        duration_minutes: int = 30,
        direction: OrderDirection = OrderDirection.BUY,
        price_limit: float = 10.0,
    ) -> AlgoOrderConfig:
        return AlgoOrderConfig(
            symbol="600000.SH",
            direction=direction,
            total_volume=total_volume,
            price_limit=price_limit,
            algo_type="vwap",
            duration_minutes=duration_minutes,
            num_slices=num_slices,
        )

    def test_generate_slices_creates_correct_number(self):
        # Arrange
        strategy = VwapStrategy()
        config = self._make_config(num_slices=4)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        assert len(slices) == 4

    def test_generate_slices_total_volume_matches(self):
        # Arrange
        strategy = VwapStrategy()
        config = self._make_config(total_volume=1000, num_slices=5)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        total = sum(s.volume for s in slices)
        assert total == 1000

    def test_generate_slices_without_volume_profile_is_uniform(self):
        # Arrange
        strategy = VwapStrategy()
        # 使用 SELL 方向避免 100 取整干扰
        config = self._make_config(total_volume=1000, num_slices=4, direction=OrderDirection.SELL)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        # 均匀分配：1000 / 4 = 250
        for s in slices[:-1]:
            assert s.volume == 250

    def test_generate_slices_with_skewed_volume_profile(self):
        # Arrange
        strategy = VwapStrategy()
        config = self._make_config(total_volume=1000, num_slices=4)
        # 前两个时段成交量高
        volume_profile = [0.4, 0.3, 0.2, 0.1]

        # Act
        slices = strategy.generate_slices(config, "algo-1", volume_profile=volume_profile)

        # Assert
        # 高成交量时段应该分配更多
        assert slices[0].volume >= slices[-1].volume
        total = sum(s.volume for s in slices)
        assert total == 1000

    def test_generate_slices_with_invalid_volume_profile_falls_back(self):
        # Arrange
        strategy = VwapStrategy()
        config = self._make_config(total_volume=1000, num_slices=4)
        # 全零的成交量分布
        volume_profile = [0.0, 0.0, 0.0, 0.0]

        # Act
        slices = strategy.generate_slices(config, "algo-1", volume_profile=volume_profile)

        # Assert
        total = sum(s.volume for s in slices)
        assert total == 1000

    def test_generate_slices_scheduled_at_intervals(self):
        # Arrange
        strategy = VwapStrategy()
        start = datetime(2026, 1, 1, 9, 30)
        config = self._make_config(duration_minutes=60, num_slices=6)

        # Act
        slices = strategy.generate_slices(config, "algo-1", start_time=start)

        # Assert
        for i in range(len(slices) - 1):
            diff = (slices[i + 1].scheduled_at - slices[i].scheduled_at).total_seconds()
            assert diff == 600  # 60 min / 6 = 10 min = 600s

    def test_generate_slices_sell_direction_volume_is_not_rounded_to_100(self):
        # Arrange
        strategy = VwapStrategy()
        config = self._make_config(total_volume=37, num_slices=3, direction=OrderDirection.SELL)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        total = sum(s.volume for s in slices)
        assert total == 37
