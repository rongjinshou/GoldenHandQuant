import pytest
from fastapi.testclient import TestClient

from src.interfaces.api.app import app


class TestDashboardRoutesExist:
    """验证 Dashboard 路由已注册到 FastAPI app。"""

    def test_routes_registered(self):
        route_paths = [r.path for r in app.routes]
        assert "/api/dashboard/snapshot" in route_paths or any(
            "snapshot" in p for p in route_paths
        )
