"""Web 触发的后台任务执行器 — 子进程复用 CLI（设计 DD-1/DD-2）。

单 worker 线程串行消费队列: 对齐 DuckDB 单写者约束（任何任务都可能写 market.duckdb）。
任务状态只存内存（重启即空）, 完整日志落 log_dir, 结果以 DuckDB 留痕为准。
"""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

_LOG_TAIL_LINES = 400
_TERMINATE_GRACE_SECONDS = 5.0


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(slots=True, kw_only=True)
class Job:
    job_id: str
    job_type: str
    params: dict
    argv: list[str]
    log_path: str
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    return_code: int | None = None
    log_tail: deque[str] = field(default_factory=lambda: deque(maxlen=_LOG_TAIL_LINES))
    cancel_requested: bool = False
    proc: subprocess.Popen | None = None

    def to_dict(self, *, tail: int = 0) -> dict:
        d: dict = {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "params": self.params,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(timespec="seconds"),
            "started_at": self.started_at.isoformat(timespec="seconds") if self.started_at else None,
            "finished_at": self.finished_at.isoformat(timespec="seconds") if self.finished_at else None,
            "return_code": self.return_code,
            "log_path": self.log_path,
        }
        if tail:
            d["log_tail"] = list(self.log_tail)[-tail:]
        return d


class JobManager:
    """白名单 argv 子进程执行器。线程安全; worker 为 daemon 线程。"""

    def __init__(self, *, log_dir: Path | str) -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._worker = threading.Thread(
            target=self._run_loop, name="job-manager-worker", daemon=True)
        self._worker.start()

    # ---- 对外接口 ----

    def submit(self, *, job_type: str, params: dict, argv: list[str]) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id=job_id, job_type=job_type, params=params, argv=list(argv),
                  log_path=str(self._log_dir / f"{job_id}.log"))
        with self._lock:
            self._jobs[job_id] = job
            self._order.append(job_id)
        self._queue.put(job_id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return [self._jobs[jid] for jid in reversed(self._order)]

    def has_active(self) -> bool:
        with self._lock:
            return any(j.status in (JobStatus.QUEUED, JobStatus.RUNNING)
                       for j in self._jobs.values())

    def cancel(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(f"unknown job: {job_id}")
            match job.status:
                case JobStatus.QUEUED:
                    job.cancel_requested = True
                    job.status = JobStatus.CANCELED
                    job.finished_at = datetime.now()
                    return job
                case JobStatus.RUNNING:
                    job.cancel_requested = True
                    proc = job.proc
                case _:
                    raise ValueError(f"job already finished: {job_id}")
        if proc is not None:
            proc.terminate()  # 收尾由 _execute 的 wait/kill 兜底完成
        return job

    # ---- worker ----

    def _run_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            job = self.get(job_id)
            if job is None or job.status is not JobStatus.QUEUED:
                continue  # 排队期被取消
            self._execute(job)

    def _execute(self, job: Job) -> None:
        with self._lock:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        rc: int
        try:
            with open(job.log_path, "w", encoding="utf-8") as logf:
                logf.write("$ " + " ".join(job.argv) + "\n")
                job.proc = subprocess.Popen(
                    job.argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", env=env,
                )
                assert job.proc.stdout is not None
                for raw in job.proc.stdout:
                    line = raw.rstrip("\n")
                    job.log_tail.append(line)
                    logf.write(line + "\n")
                    logf.flush()
                try:
                    rc = job.proc.wait(timeout=_TERMINATE_GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    job.proc.kill()
                    rc = job.proc.wait()
        except OSError as exc:  # 可执行文件不存在等启动失败
            job.log_tail.append(f"[job] 启动失败: {exc}")
            rc = -1
        with self._lock:
            job.return_code = rc
            job.finished_at = datetime.now()
            job.proc = None
            if job.cancel_requested:
                job.status = JobStatus.CANCELED
            elif rc == 0:
                job.status = JobStatus.SUCCEEDED
            else:
                job.status = JobStatus.FAILED
