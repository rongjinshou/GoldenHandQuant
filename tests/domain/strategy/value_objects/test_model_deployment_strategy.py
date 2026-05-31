"""测试模型部署策略枚举。"""

from src.domain.strategy.value_objects.model_deployment_strategy import (
    ModelDeploymentStrategy,
)


class TestModelDeploymentStrategy:
    def test_has_shadow(self) -> None:
        assert ModelDeploymentStrategy.SHADOW == "SHADOW"

    def test_has_canary(self) -> None:
        assert ModelDeploymentStrategy.CANARY == "CANARY"

    def test_has_full_rollout(self) -> None:
        assert ModelDeploymentStrategy.FULL_ROLLOUT == "FULL_ROLLOUT"

    def test_str_values(self) -> None:
        assert str(ModelDeploymentStrategy.SHADOW) == "SHADOW"
        assert str(ModelDeploymentStrategy.CANARY) == "CANARY"
        assert str(ModelDeploymentStrategy.FULL_ROLLOUT) == "FULL_ROLLOUT"

    def test_from_value(self) -> None:
        assert ModelDeploymentStrategy("SHADOW") is ModelDeploymentStrategy.SHADOW
        assert ModelDeploymentStrategy("CANARY") is ModelDeploymentStrategy.CANARY
        assert ModelDeploymentStrategy("FULL_ROLLOUT") is ModelDeploymentStrategy.FULL_ROLLOUT

    def test_all_members(self) -> None:
        members = list(ModelDeploymentStrategy)
        assert len(members) == 3
