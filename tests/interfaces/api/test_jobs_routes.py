"""jobs 路由契约测试 — dependency_overrides 注入假管理器, 不起真子进程。"""

from collections import deque
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.jobs.job_manager import Job, JobStatus
from src.interfaces.api.app import app
from src.interfaces.api.routes.jobs import get_job_manager


class FakeJobManager:
    def __init__(self) -> None:
        self.submitted: list[tuple[str, dict, list[str]]] = []
        self.jobs: dict[str, Job] = {}
        self._n = 0

    def submit(self, *, job_type: str, params: dict, argv: list[str]) -> Job:
        self._n += 1
        job = Job(job_id=f"job{self._n}", job_type=job_type, params=params,
                  argv=argv, log_path=f"/tmp/job{self._n}.log")
        self.submitted.append((job_type, params, argv))
        self.jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        return list(reversed(self.jobs.values()))

    def has_active(self) -> bool:
        return any(j.status in (JobStatus.QUEUED, JobStatus.RUNNING)
                   for j in self.jobs.values())

    def cancel(self, job_id: str) -> Job:
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
            raise ValueError(job_id)
        job.status = JobStatus.CANCELED
        job.finished_at = datetime.now()
        return job


@pytest.fixture()
def fake() -> FakeJobManager:
    return FakeJobManager()


@pytest.fixture()
def client(fake: FakeJobManager):
    app.dependency_overrides[get_job_manager] = lambda: fake
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class TestSubmit:
    def test_backtest_returns_202_with_job(self, client, fake) -> None:
        resp = client.post("/api/jobs/backtest", json={
            "strategies": ["dual_ma"],
            "start_date": "2024-01-01", "end_date": "2024-12-31"})
        assert resp.status_code == 202
        body = resp.json()
        assert body["job_type"] == "backtest"
        assert body["status"] == "queued"
        assert fake.submitted[0][0] == "backtest"
        assert "--strategies" in fake.submitted[0][2]

    def test_factor_test_unknown_factor_422(self, client) -> None:
        resp = client.post("/api/jobs/factor-test", json={"factors": "NOPE99"})
        assert resp.status_code == 422

    def test_data_refresh_and_ml_endpoints(self, client, fake) -> None:
        assert client.post("/api/jobs/data-refresh", json={
            "start_date": "2025-01-01", "end_date": "2025-06-01"}).status_code == 202
        assert client.post("/api/jobs/ml-train", json={
            "start_date": "2021-01-01", "end_date": "2024-12-31"}).status_code == 202
        assert client.post("/api/jobs/ml-evaluate", json={
            "model_name": "m", "eval_start": "2025-01-01",
            "eval_end": "2025-06-01"}).status_code == 202
        assert [s[0] for s in fake.submitted] == ["data_refresh", "ml_train", "ml_evaluate"]


class TestQueryAndCancel:
    def test_list_and_detail_with_tail(self, client, fake) -> None:
        job = fake.submit(job_type="t", params={}, argv=["x"])
        job.log_tail = deque(["l1", "l2", "l3"])
        listing = client.get("/api/jobs").json()
        assert listing["jobs"][0]["job_id"] == job.job_id
        assert "log_tail" not in listing["jobs"][0]
        detail = client.get(f"/api/jobs/{job.job_id}?tail=2").json()
        assert detail["log_tail"] == ["l2", "l3"]

    def test_detail_404(self, client) -> None:
        assert client.get("/api/jobs/nope").status_code == 404

    def test_cancel_ok_404_409(self, client, fake) -> None:
        job = fake.submit(job_type="t", params={}, argv=["x"])
        assert client.post(f"/api/jobs/{job.job_id}/cancel").json()["status"] == "canceled"
        assert client.post("/api/jobs/nope/cancel").status_code == 404
        assert client.post(f"/api/jobs/{job.job_id}/cancel").status_code == 409


class TestFakeFidelity:
    def test_fake_signatures_match_real_job_manager(self) -> None:
        """FakeJobManager 与真 JobManager 的共享方法签名对账, 防鸭子型漂移。"""
        import inspect

        from src.infrastructure.jobs.job_manager import JobManager

        for name in ("submit", "get", "list_jobs", "has_active", "cancel"):
            real = inspect.signature(getattr(JobManager, name))
            fake = inspect.signature(getattr(FakeJobManager, name))
            assert real.parameters.keys() == fake.parameters.keys(), name
            assert all(
                real.parameters[p].kind == fake.parameters[p].kind
                for p in real.parameters
            ), name
