"""JobManager 生命周期测试 — 用 sys.executable -c 微脚本, 不依赖任何 CLI。"""

import sys
import time
from pathlib import Path

from src.infrastructure.jobs.job_manager import JobManager, JobStatus


def _wait(predicate, timeout: float = 20.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


class TestJobLifecycle:
    def test_success_job_captures_log_and_status(self, tmp_path: Path) -> None:
        mgr = JobManager(log_dir=tmp_path)
        job = mgr.submit(job_type="demo", params={"x": 1},
                         argv=_py("print('hello'); print('world')"))
        assert job.status is JobStatus.QUEUED

        assert _wait(lambda: job.status is JobStatus.SUCCEEDED)
        assert job.return_code == 0
        assert job.started_at is not None and job.finished_at is not None
        assert "hello" in list(job.log_tail)
        assert "world" in Path(job.log_path).read_text(encoding="utf-8")

    def test_failure_job_keeps_return_code(self, tmp_path: Path) -> None:
        mgr = JobManager(log_dir=tmp_path)
        job = mgr.submit(job_type="demo", params={},
                         argv=_py("import sys; print('boom'); sys.exit(3)"))
        assert _wait(lambda: job.status is JobStatus.FAILED)
        assert job.return_code == 3
        assert "boom" in list(job.log_tail)

    def test_jobs_run_serially_in_submit_order(self, tmp_path: Path) -> None:
        mgr = JobManager(log_dir=tmp_path)
        j1 = mgr.submit(job_type="demo", params={},
                        argv=_py("import time; time.sleep(0.4)"))
        j2 = mgr.submit(job_type="demo", params={}, argv=_py("pass"))
        assert _wait(lambda: j2.status is JobStatus.SUCCEEDED)
        assert j1.status is JobStatus.SUCCEEDED
        assert j2.started_at >= j1.finished_at

    def test_to_dict_shape(self, tmp_path: Path) -> None:
        mgr = JobManager(log_dir=tmp_path)
        job = mgr.submit(job_type="demo", params={"a": 1}, argv=_py("print('x')"))
        assert _wait(lambda: job.status is JobStatus.SUCCEEDED)
        d = job.to_dict(tail=10)
        assert d["job_id"] == job.job_id
        assert d["job_type"] == "demo"
        assert d["params"] == {"a": 1}
        assert d["status"] == "succeeded"
        assert d["log_tail"] == ["x"]
        assert "log_tail" not in job.to_dict()


class TestCancel:
    def test_cancel_queued_job(self, tmp_path: Path) -> None:
        mgr = JobManager(log_dir=tmp_path)
        blocker = mgr.submit(job_type="demo", params={},
                             argv=_py("import time; time.sleep(30)"))
        queued = mgr.submit(job_type="demo", params={}, argv=_py("pass"))
        canceled = mgr.cancel(queued.job_id)
        assert canceled.status is JobStatus.CANCELED
        mgr.cancel(blocker.job_id)
        assert _wait(lambda: blocker.status is JobStatus.CANCELED)
        # 被取消的排队任务永远不会启动
        assert queued.started_at is None

    def test_cancel_running_job_terminates_process(self, tmp_path: Path) -> None:
        mgr = JobManager(log_dir=tmp_path)
        job = mgr.submit(job_type="demo", params={},
                         argv=_py("import time; print('started', flush=True); time.sleep(30)"))
        assert _wait(lambda: job.status is JobStatus.RUNNING and "started" in list(job.log_tail))
        mgr.cancel(job.job_id)
        assert _wait(lambda: job.status is JobStatus.CANCELED)
        assert job.finished_at is not None

    def test_cancel_finished_job_raises(self, tmp_path: Path) -> None:
        import pytest

        mgr = JobManager(log_dir=tmp_path)
        job = mgr.submit(job_type="demo", params={}, argv=_py("pass"))
        assert _wait(lambda: job.status is JobStatus.SUCCEEDED)
        with pytest.raises(ValueError):
            mgr.cancel(job.job_id)

    def test_cancel_unknown_job_raises(self, tmp_path: Path) -> None:
        import pytest

        mgr = JobManager(log_dir=tmp_path)
        with pytest.raises(KeyError):
            mgr.cancel("nope")


class TestRegistry:
    def test_list_jobs_newest_first_and_has_active(self, tmp_path: Path) -> None:
        mgr = JobManager(log_dir=tmp_path)
        assert mgr.has_active() is False
        j1 = mgr.submit(job_type="a", params={}, argv=_py("pass"))
        j2 = mgr.submit(job_type="b", params={}, argv=_py("pass"))
        assert [j.job_id for j in mgr.list_jobs()] == [j2.job_id, j1.job_id]
        assert _wait(lambda: not mgr.has_active())

    def test_bad_executable_marks_failed(self, tmp_path: Path) -> None:
        mgr = JobManager(log_dir=tmp_path)
        job = mgr.submit(job_type="demo", params={},
                         argv=["definitely-not-a-real-binary-xyz"])
        assert _wait(lambda: job.status is JobStatus.FAILED)
        assert any("启动失败" in line for line in job.log_tail)
