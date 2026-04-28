from fastapi.testclient import TestClient

from src.interfaces.api.app import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_trigger_backtest_with_defaults():
    response = client.post("/api/backtest/run", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "run_id" in data


def test_get_backtest_status_not_found():
    response = client.get("/api/backtest/status/nonexistent")
    assert response.status_code == 404
