from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating


class TestStrategyRating:
    def test_values(self):
        assert StrategyRating.A == "A"
        assert StrategyRating.B == "B"
        assert StrategyRating.C == "C"
        assert StrategyRating.D == "D"

    def test_count(self):
        assert len(StrategyRating) == 4

    def test_from_string(self):
        assert StrategyRating("A") == StrategyRating.A
