from src.domain.strategy.pool.value_objects.strategy_status import StrategyStatus


class TestStrategyStatus:
    def test_values(self):
        assert StrategyStatus.CANDIDATE == "CANDIDATE"
        assert StrategyStatus.ACTIVE == "ACTIVE"
        assert StrategyStatus.PAUSED == "PAUSED"
        assert StrategyStatus.SUSPENDED == "SUSPENDED"
        assert StrategyStatus.RETIRED == "RETIRED"

    def test_count(self):
        assert len(StrategyStatus) == 5

    def test_from_string(self):
        assert StrategyStatus("ACTIVE") == StrategyStatus.ACTIVE
