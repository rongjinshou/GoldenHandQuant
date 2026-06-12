"""meta 路由 — 前端表单的单一数据源。"""

from fastapi.testclient import TestClient

from src.interfaces.api.app import app

client = TestClient(app)


class TestStrategies:
    def test_lists_registry_strategies(self) -> None:
        body = client.get("/api/meta/strategies").json()
        names = [s["name"] for s in body["strategies"]]
        assert "dual_ma" in names and "micro_value" in names
        mv = next(s for s in body["strategies"] if s["name"] == "micro_value")
        assert mv["strategy_type"] == "cross_section"
        assert isinstance(mv["default_params"], dict)

    def test_private_params_filtered(self, monkeypatch) -> None:
        """用假策略钉住 `_` 前缀过滤行为（registry 现状 defaults 无私参, 直跑是空洞断言）。"""
        from src.domain.strategy import registry

        fake = registry.StrategyConfig(
            name="fake", factory=lambda p: None, strategy_type="bar",
            description="t", default_params={"top_n": 1, "_secret": "x"})
        monkeypatch.setattr(registry, "list_strategies", lambda: [fake])
        body = client.get("/api/meta/strategies").json()
        assert body["strategies"][0]["default_params"] == {"top_n": 1}


class TestFactors:
    def test_catalog_shape(self) -> None:
        from src.domain.strategy.factor_test.factor_catalog import (
            FACTOR_BY_ID,
            P0_FACTORS,
        )

        body = client.get("/api/meta/factors").json()
        assert len(body["factors"]) >= 11
        # 序列化保真: 以 catalog 为预期源, 不硬编码会演化的领域数据
        f10 = next(f for f in body["factors"] if f["factor_id"] == "F10")
        assert f10["field_ready"] == FACTOR_BY_ID["F10"].field_ready
        assert set(body["groups"]["P0"]) == {f.factor_id for f in P0_FACTORS}
