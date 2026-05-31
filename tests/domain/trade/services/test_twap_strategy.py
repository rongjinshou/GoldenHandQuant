from datetime import datetime

from src.domain.trade.services.algo_strategies.twap_strategy import TwapStrategy
from src.domain.trade.value_objects.algo_order_config import AlgoOrderConfig
from src.domain.trade.value_objects.order_direction import OrderDirection


class TestTwapStrategy:
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
            algo_type="twap",
            duration_minutes=duration_minutes,
            num_slices=num_slices,
        )

    def test_generate_slices_creates_correct_number(self):
        # Arrange
        strategy = TwapStrategy()
        config = self._make_config(num_slices=5)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        assert len(slices) == 5

    def test_generate_slices_total_volume_matches(self):
        # Arrange
        strategy = TwapStrategy()
        config = self._make_config(total_volume=1000, num_slices=5)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        total = sum(s.volume for s in slices)
        assert total == 1000

    def test_generate_slices_rounds_buy_to_100(self):
        # Arrange
        strategy = TwapStrategy()
        config = self._make_config(total_volume=500, num_slices=3, direction=OrderDirection.BUY)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        for s in slices:
            assert s.volume % 100 == 0
        total = sum(s.volume for s in slices)
        assert total == 500

    def test_generate_slices_sell_does_not_require_100_multiple(self):
        # Arrange
        strategy = TwapStrategy()
        config = self._make_config(total_volume=33, num_slices=3, direction=OrderDirection.SELL)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        total = sum(s.volume for s in slices)
        assert total == 33

    def test_generate_slices_last_slice_gets_remainder(self):
        # Arrange
        strategy = TwapStrategy()
        config = self._make_config(total_volume=1000, num_slices=3)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        base = 1000 // 3
        # 前面的子单应该 <= 最后一个
        assert slices[-1].volume >= slices[0].volume

    def test_generate_slices_scheduled_at_intervals(self):
        # Arrange
        strategy = TwapStrategy()
        start = datetime(2026, 1, 1, 9, 30)
        config = self._make_config(duration_minutes=30, num_slices=3)

        # Act
        slices = strategy.generate_slices(config, "algo-1", start_time=start)

        # Assert
        for i in range(len(slices) - 1):
            diff = (slices[i + 1].scheduled_at - slices[i].scheduled_at).total_seconds()
            assert diff == 600  # 30 min / 3 = 10 min = 600s

    def test_generate_slices_all_share_parent_algo_id(self):
        # Arrange
        strategy = TwapStrategy()
        config = self._make_config(num_slices=4)

        # Act
        slices = strategy.generate_slices(config, "parent-algo-123")

        # Assert
        for s in slices:
            assert s.parent_algo_id == "parent-algo-123"

    def test_generate_slices_all_share_symbol_and_direction(self):
        # Arrange
        strategy = TwapStrategy()
        config = self._make_config(num_slices=3)

        # Act
        slices = strategy.generate_slices(config, "algo-1")

        # Assert
        for s in slices:
            assert s.symbol == "600000.SH"
            assert s.direction == OrderDirection.BUY
