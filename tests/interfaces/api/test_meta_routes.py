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

    def test_private_params_filtered(self) -> None:
        body = client.get("/api/meta/strategies").json()
        for s in body["strategies"]:
            assert not any(k.startswith("_") for k in s["default_params"])


class TestFactors:
    def test_catalog_shape(self) -> None:
        body = client.get("/api/meta/factors").json()
        assert len(body["factors"]) >= 11
        f10 = next(f for f in body["factors"] if f["factor_id"] == "F10")
        assert f10["field_ready"] is False  # 基本面管道缺 gross_margin
        assert set(body["groups"]["P0"]) == {"F01", "F02", "F03", "F04", "F05"}
