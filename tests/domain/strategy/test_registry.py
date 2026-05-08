from src.domain.strategy.registry import create_strategy, get_strategy, list_strategies


class TestStrategyRegistry:
    def test_list_strategies_should_return_all_registered(self):
        strategies = list_strategies()
        names = [s.name for s in strategies]
        assert "dual_ma" in names
        assert "micro_value" in names

    def test_get_strategy_dual_ma_should_return_config(self):
        config = get_strategy("dual_ma")
        assert config.name == "dual_ma"
        assert config.strategy_type == "bar"
        assert "DualMa" in config.description

    def test_get_strategy_unknown_should_raise(self):
        import pytest
        with pytest.raises(KeyError, match="unknown_strategy"):
            get_strategy("unknown_strategy")

    def test_create_strategy_dual_ma_should_return_instance(self):
        from src.domain.strategy.services.strategies.dual_ma_strategy import DualMaStrategy
        strategy = create_strategy("dual_ma")
        assert isinstance(strategy, DualMaStrategy)

    def test_create_strategy_micro_value_should_pass_params(self):
        from src.domain.strategy.services.strategies.micro_value_strategy import MicroValueStrategy
        strategy = create_strategy("micro_value", {"top_n": 5})
        assert isinstance(strategy, MicroValueStrategy)
        assert strategy._top_n == 5

    def test_create_strategy_micro_value_default_params(self):
        from src.domain.strategy.services.strategies.micro_value_strategy import MicroValueStrategy
        strategy = create_strategy("micro_value")
        assert isinstance(strategy, MicroValueStrategy)
        assert strategy._top_n == 9
