from fastapi.testclient import TestClient

from src.interfaces.api.app import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_trigger_backtest_returns_not_implemented():
    response = client.post("/api/backtest/run", json={})
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


def test_get_backtest_status_not_found():
    response = client.get("/api/backtest/status/nonexistent")
    assert response.status_code == 404
