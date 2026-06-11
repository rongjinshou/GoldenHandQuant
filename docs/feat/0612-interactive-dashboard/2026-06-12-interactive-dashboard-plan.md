# 交互式投研驾驶舱 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把只读驾驶舱升级为可交互 GUI——浏览器内触发回测/因子检验/数据刷新/ML 任务（子进程复用 CLI），实时看任务日志，实盘页补齐留痕盲区。

**Architecture:** JobManager（infrastructure/jobs，单 worker 串行队列 + 子进程）执行白名单 argv；job_commands（interfaces/api）把 Pydantic 请求翻译为 CLI argv；新增 jobs/meta 路由 + live 路由只读扩展；前端无构建链 ES modules。设计: `docs/feat/0612-interactive-dashboard/2026-06-12-interactive-dashboard-design.md`。

**Tech Stack:** FastAPI + Pydantic v2、subprocess/threading/queue、SQLite ro / DuckDB ro、原生 JS + ECharts（vendor）。

**环境约定（必读）:**
- 一切 python 命令用 Windows conda python：`WIN_PYTHON="/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe"`
- pytest 一律加 `--basetemp=.pytest_tmp`（在项目内）
- 测试命令模板：`$WIN_PYTHON -m pytest <path> --basetemp=.pytest_tmp -q`
- 提交信息结尾加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`；直接提交 main，**不要 push**（WSL 不能 push）
- 工作树里有 3 个他人未提交改动（.gitignore / verdict.py / test_verdict.py）——**永远不要 `git add -A`**，只 add 自己的文件

---

## File Structure

```
src/infrastructure/jobs/__init__.py            # 新建（空导出）
src/infrastructure/jobs/job_manager.py         # 新建: Job/JobStatus/JobManager
src/interfaces/api/job_commands.py             # 新建: 5 个请求模型 + argv 构建器 + 白名单
src/interfaces/api/routes/jobs.py              # 新建: 任务路由
src/interfaces/api/routes/meta.py              # 新建: 策略/因子元数据
src/interfaces/api/routes/live.py              # 修改: +audit/budget/cycle钻取/mode/config/tickets
src/interfaces/api/app.py                      # 修改: 挂 jobs+meta, 摘 dashboard/account/backtest_routes
src/interfaces/cli/compare_strategies.py       # 修改: --initial-capital + 让 --config 真生效
src/interfaces/api/static/index.html           # 重写: +任务页签/表单容器/模块脚本
src/interfaces/api/static/style.css            # 追加: 表单/任务卡/徽章样式
src/interfaces/api/static/js/{api,charts,jobs,main}.js          # 新建
src/interfaces/api/static/js/pages/{overview,verdicts,explorer,backtests,live}.js  # 新建(承接 app.js)
src/interfaces/api/static/app.js               # 删除（拆入 js/）
删除死代码: routes/dashboard.py, routes/account_routes.py, routes/backtest_routes.py,
  application/dashboard_app.py, infrastructure/web/websocket_manager.py,
  infrastructure/web/dashboard_data_provider.py, domain/backtest/interfaces/dashboard_ports.py,
  domain/backtest/value_objects/dashboard_snapshot.py 及对应 5 个测试文件
tests/infrastructure/jobs/test_job_manager.py  # 新建
tests/interfaces/api/test_job_commands.py      # 新建
tests/interfaces/api/test_jobs_routes.py       # 新建
tests/interfaces/api/test_meta_routes.py       # 新建
tests/interfaces/api/test_live_routes_ext.py   # 新建
tests/application/test_strategy_comparison_app.py  # 追加单策略用例
```

---

### Task 1: JobManager（队列 + 子进程 + 日志环）

**Files:**
- Create: `src/infrastructure/jobs/__init__.py`、`src/infrastructure/jobs/job_manager.py`
- Test: `tests/infrastructure/jobs/__init__.py`、`tests/infrastructure/jobs/test_job_manager.py`

- [ ] **Step 1: 写失败测试**

`tests/infrastructure/jobs/__init__.py` 空文件。`tests/infrastructure/jobs/test_job_manager.py`：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$WIN_PYTHON -m pytest tests/infrastructure/jobs/ --basetemp=.pytest_tmp -q`
Expected: FAIL（ModuleNotFoundError: src.infrastructure.jobs）

- [ ] **Step 3: 实现**

`src/infrastructure/jobs/__init__.py` 空文件。`src/infrastructure/jobs/job_manager.py`：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `$WIN_PYTHON -m pytest tests/infrastructure/jobs/ --basetemp=.pytest_tmp -q`
Expected: 10 passed

- [ ] **Step 5: ruff + 提交**

```bash
ruff check src/infrastructure/jobs/ tests/infrastructure/jobs/
git add src/infrastructure/jobs/ tests/infrastructure/jobs/
git commit -m "feat(jobs): JobManager 子进程任务执行器 — 串行队列+日志环+取消"
```

---

### Task 2: job_commands — 请求模型与 argv 构建器

**Files:**
- Create: `src/interfaces/api/job_commands.py`
- Test: `tests/interfaces/api/test_job_commands.py`

- [ ] **Step 1: 写失败测试**

```python
"""argv 构建器纯函数测试 — 不触网络不起进程。"""

import sys

import pytest
from pydantic import ValidationError

from src.interfaces.api.job_commands import (
    BacktestJobRequest,
    DataRefreshJobRequest,
    FactorTestJobRequest,
    MlEvaluateJobRequest,
    MlTrainJobRequest,
    build_backtest_argv,
    build_data_refresh_argv,
    build_factor_test_argv,
    build_ml_evaluate_argv,
    build_ml_train_argv,
)


class TestBacktest:
    def test_minimal_request_builds_compare_argv(self) -> None:
        req = BacktestJobRequest(
            strategies=["dual_ma"], start_date="2024-01-01", end_date="2024-12-31")
        argv = build_backtest_argv(req)
        assert argv[0] == sys.executable
        assert argv[1:3] == ["-m", "src.interfaces.cli.compare_strategies"]
        assert "--strategies" in argv and "dual_ma" in argv
        assert "--symbols" not in argv and "--params" not in argv

    def test_full_request(self) -> None:
        req = BacktestJobRequest(
            strategies=["dual_ma", "micro_value"],
            start_date="2024-01-01", end_date="2024-12-31",
            symbols=["000021.SZ", "600000.SH"],
            params={"micro_value": {"top_n": 5}},
            config="resources/backtest_multi_factor.yaml",
            initial_capital=200000,
        )
        argv = build_backtest_argv(req)
        i = argv.index("--strategies")
        assert argv[i + 1] == "dual_ma,micro_value"
        assert argv[argv.index("--symbols") + 1] == "000021.SZ,600000.SH"
        assert argv[argv.index("--params") + 1] == "micro_value.top_n=5"
        assert argv[argv.index("--initial-capital") + 1] == "200000.0"

    def test_unknown_strategy_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BacktestJobRequest(strategies=["nope"],
                               start_date="2024-01-01", end_date="2024-12-31")

    def test_config_outside_whitelist_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BacktestJobRequest(strategies=["dual_ma"], start_date="2024-01-01",
                               end_date="2024-12-31", config="/etc/passwd")

    def test_bad_date_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BacktestJobRequest(strategies=["dual_ma"],
                               start_date="2024/01/01", end_date="2024-12-31")


class TestFactorTest:
    def test_defaults(self) -> None:
        req = FactorTestJobRequest(factors="P0")
        argv = build_factor_test_argv(req)
        assert argv[1:4] == ["-m", "src.interfaces.cli.quant", "factor-test"]
        assert argv[argv.index("--factors") + 1] == "P0"
        assert argv[argv.index("--objective") + 1] == "long_short"
        assert "--split-date" not in argv

    def test_split_and_objective(self) -> None:
        req = FactorTestJobRequest(factors="F01,F02", split_date="2024-06-30",
                                   objective="long_only", rebalance_days=5)
        argv = build_factor_test_argv(req)
        assert argv[argv.index("--split-date") + 1] == "2024-06-30"
        assert argv[argv.index("--objective") + 1] == "long_only"
        assert argv[argv.index("--rebalance-days") + 1] == "5"

    def test_unknown_factor_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FactorTestJobRequest(factors="F99,NOPE")


class TestOthers:
    def test_data_refresh(self) -> None:
        argv = build_data_refresh_argv(
            DataRefreshJobRequest(start_date="2025-01-01", end_date="2025-06-01"))
        assert argv[1:5] == ["-m", "src.interfaces.cli.quant", "data", "refresh"]
        assert argv[argv.index("--start-date") + 1] == "2025-01-01"

    def test_ml_train(self) -> None:
        argv = build_ml_train_argv(MlTrainJobRequest(
            start_date="2021-01-01", end_date="2024-12-31", n_trials=10))
        assert argv[3] == "ml-train"
        assert argv[argv.index("--n-trials") + 1] == "10"
        assert argv[argv.index("--model-name") + 1] == "lgbm_return_5d"

    def test_ml_evaluate(self) -> None:
        argv = build_ml_evaluate_argv(MlEvaluateJobRequest(
            model_name="lgbm_return_5d", eval_start="2025-01-01", eval_end="2025-06-01"))
        assert argv[3] == "ml-evaluate"
        assert argv[argv.index("--model-name") + 1] == "lgbm_return_5d"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$WIN_PYTHON -m pytest tests/interfaces/api/test_job_commands.py --basetemp=.pytest_tmp -q`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现 `src/interfaces/api/job_commands.py`**

```python
"""Web 任务请求 → CLI argv 翻译层（白名单, 无 shell）。

每种任务类型 = 一个 Pydantic 请求模型 + 一个纯函数构建器。
校验借 domain 注册表/因子目录把关, 解析失败 → 422。
"""

from __future__ import annotations

import sys
from typing import Literal

from pydantic import BaseModel, Field, field_validator

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
CONFIG_WHITELIST = (
    "resources/backtest.yaml",
    "resources/backtest_multi_factor.yaml",
)
_QUANT = [sys.executable, "-m", "src.interfaces.cli.quant"]


class BacktestJobRequest(BaseModel):
    strategies: list[str] = Field(min_length=1)
    start_date: str = Field(pattern=DATE_PATTERN)
    end_date: str = Field(pattern=DATE_PATTERN)
    symbols: list[str] | None = None
    params: dict[str, dict[str, float | int | str]] | None = None
    config: str | None = None
    initial_capital: float | None = Field(default=None, gt=0)

    @field_validator("strategies")
    @classmethod
    def _known_strategies(cls, v: list[str]) -> list[str]:
        from src.domain.strategy.registry import get_strategy

        for name in v:
            try:
                get_strategy(name)
            except KeyError:
                raise ValueError(f"未知策略: {name}") from None
        return v

    @field_validator("config")
    @classmethod
    def _config_in_whitelist(cls, v: str | None) -> str | None:
        if v is not None and v not in CONFIG_WHITELIST:
            raise ValueError(f"config 仅允许: {CONFIG_WHITELIST}")
        return v


class FactorTestJobRequest(BaseModel):
    factors: str = Field(min_length=1)
    start_date: str = Field(default="2021-01-01", pattern=DATE_PATTERN)
    end_date: str = Field(default="2025-12-31", pattern=DATE_PATTERN)
    split_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    objective: Literal["long_short", "long_only"] = "long_short"
    num_layers: int = Field(default=5, ge=2, le=10)
    rebalance_days: int = Field(default=1, ge=1, le=60)
    cost_rate: float = Field(default=0.003, ge=0, le=0.05)

    @field_validator("factors")
    @classmethod
    def _resolvable(cls, v: str) -> str:
        from src.domain.strategy.factor_test.factor_catalog import resolve_factors

        resolve_factors(v)  # ValueError 自然冒泡 → 422
        return v


class DataRefreshJobRequest(BaseModel):
    start_date: str = Field(pattern=DATE_PATTERN)
    end_date: str = Field(pattern=DATE_PATTERN)


class MlTrainJobRequest(BaseModel):
    start_date: str = Field(pattern=DATE_PATTERN)
    end_date: str = Field(pattern=DATE_PATTERN)
    symbols: str = "000300.SH"
    model_name: str = Field(default="lgbm_return_5d", min_length=1)
    label_horizon: int = Field(default=5, ge=1, le=20)
    n_trials: int = Field(default=50, ge=1, le=200)


class MlEvaluateJobRequest(BaseModel):
    model_name: str = Field(min_length=1)
    eval_start: str = Field(pattern=DATE_PATTERN)
    eval_end: str = Field(pattern=DATE_PATTERN)


def build_backtest_argv(req: BacktestJobRequest) -> list[str]:
    argv = [sys.executable, "-m", "src.interfaces.cli.compare_strategies",
            "--strategies", ",".join(req.strategies),
            "--start-date", req.start_date, "--end-date", req.end_date]
    if req.symbols:
        argv += ["--symbols", ",".join(req.symbols)]
    if req.params:
        pairs = [f"{strat}.{key}={value}"
                 for strat, kv in req.params.items() for key, value in kv.items()]
        argv += ["--params", ",".join(pairs)]
    if req.config:
        argv += ["--config", req.config]
    if req.initial_capital:
        argv += ["--initial-capital", str(float(req.initial_capital))]
    return argv


def build_factor_test_argv(req: FactorTestJobRequest) -> list[str]:
    argv = [*_QUANT, "factor-test",
            "--factors", req.factors,
            "--start-date", req.start_date, "--end-date", req.end_date,
            "--objective", req.objective,
            "--num-layers", str(req.num_layers),
            "--rebalance-days", str(req.rebalance_days),
            "--cost-rate", str(req.cost_rate)]
    if req.split_date:
        argv += ["--split-date", req.split_date]
    return argv


def build_data_refresh_argv(req: DataRefreshJobRequest) -> list[str]:
    return [*_QUANT, "data", "refresh",
            "--start-date", req.start_date, "--end-date", req.end_date]


def build_ml_train_argv(req: MlTrainJobRequest) -> list[str]:
    return [*_QUANT, "ml-train",
            "--symbols", req.symbols,
            "--start-date", req.start_date, "--end-date", req.end_date,
            "--label-horizon", str(req.label_horizon),
            "--model-name", req.model_name,
            "--n-trials", str(req.n_trials)]


def build_ml_evaluate_argv(req: MlEvaluateJobRequest) -> list[str]:
    return [*_QUANT, "ml-evaluate",
            "--model-name", req.model_name,
            "--eval-start", req.eval_start, "--eval-end", req.eval_end]
```

注意：`_QUANT` 是共享列表，构建器内必须用 `[*_QUANT, ...]` 解包复制，禁止 `_QUANT + x` 之外的原地修改。

- [ ] **Step 4: 跑测试确认通过**

Run: `$WIN_PYTHON -m pytest tests/interfaces/api/test_job_commands.py --basetemp=.pytest_tmp -q`
Expected: 11 passed

- [ ] **Step 5: ruff + 提交**

```bash
ruff check src/interfaces/api/job_commands.py tests/interfaces/api/test_job_commands.py
git add src/interfaces/api/job_commands.py tests/interfaces/api/test_job_commands.py
git commit -m "feat(jobs): 任务请求模型与 CLI argv 构建器 — 白名单+域校验"
```

---

### Task 3: jobs 路由

**Files:**
- Create: `src/interfaces/api/routes/jobs.py`
- Test: `tests/interfaces/api/test_jobs_routes.py`

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$WIN_PYTHON -m pytest tests/interfaces/api/test_jobs_routes.py --basetemp=.pytest_tmp -q`
Expected: FAIL（ImportError: routes.jobs）

- [ ] **Step 3: 实现 `src/interfaces/api/routes/jobs.py`**

```python
"""任务路由 — Web 触发研究侧 CLI（回测/因子/数据刷新/ML）。

只读交易红线（设计 DD-4）: 此处永不出现下单/撤单/auto-trade/trading.yaml 写操作。
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from src.infrastructure.jobs.job_manager import JobManager
from src.interfaces.api.job_commands import (
    BacktestJobRequest,
    DataRefreshJobRequest,
    FactorTestJobRequest,
    MlEvaluateJobRequest,
    MlTrainJobRequest,
    build_backtest_argv,
    build_data_refresh_argv,
    build_factor_test_argv,
    build_ml_evaluate_argv,
    build_ml_train_argv,
)

router = APIRouter()

_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        log_dir = Path(os.environ.get("GHQ_JOB_LOG_DIR", "data/job_logs"))
        _manager = JobManager(log_dir=log_dir)
    return _manager


@router.post("/backtest", status_code=202)
def submit_backtest(req: BacktestJobRequest,
                    manager: JobManager = Depends(get_job_manager)) -> dict:
    job = manager.submit(job_type="backtest", params=req.model_dump(),
                         argv=build_backtest_argv(req))
    return job.to_dict()


@router.post("/factor-test", status_code=202)
def submit_factor_test(req: FactorTestJobRequest,
                       manager: JobManager = Depends(get_job_manager)) -> dict:
    job = manager.submit(job_type="factor_test", params=req.model_dump(),
                         argv=build_factor_test_argv(req))
    return job.to_dict()


@router.post("/data-refresh", status_code=202)
def submit_data_refresh(req: DataRefreshJobRequest,
                        manager: JobManager = Depends(get_job_manager)) -> dict:
    job = manager.submit(job_type="data_refresh", params=req.model_dump(),
                         argv=build_data_refresh_argv(req))
    return job.to_dict()


@router.post("/ml-train", status_code=202)
def submit_ml_train(req: MlTrainJobRequest,
                    manager: JobManager = Depends(get_job_manager)) -> dict:
    job = manager.submit(job_type="ml_train", params=req.model_dump(),
                         argv=build_ml_train_argv(req))
    return job.to_dict()


@router.post("/ml-evaluate", status_code=202)
def submit_ml_evaluate(req: MlEvaluateJobRequest,
                       manager: JobManager = Depends(get_job_manager)) -> dict:
    job = manager.submit(job_type="ml_evaluate", params=req.model_dump(),
                         argv=build_ml_evaluate_argv(req))
    return job.to_dict()


@router.get("")
def list_jobs(limit: int = 50,
              manager: JobManager = Depends(get_job_manager)) -> dict:
    jobs = manager.list_jobs()[: min(limit, 200)]
    return {"jobs": [j.to_dict() for j in jobs], "active": manager.has_active()}


@router.get("/{job_id}")
def job_detail(job_id: str, tail: int = 200,
               manager: JobManager = Depends(get_job_manager)) -> dict:
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
    return job.to_dict(tail=min(tail, 400))


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str,
               manager: JobManager = Depends(get_job_manager)) -> dict:
    try:
        job = manager.cancel(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}") from None
    except ValueError:
        raise HTTPException(status_code=409, detail="job already finished") from None
    return job.to_dict()
```

并在 `src/interfaces/api/app.py` 加挂载（先最小改动，死代码清理在 Task 8）：

```python
from src.interfaces.api.routes import jobs  # 加入现有 import 行
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
```

- [ ] **Step 4: 跑测试确认通过**

Run: `$WIN_PYTHON -m pytest tests/interfaces/api/test_jobs_routes.py --basetemp=.pytest_tmp -q`
Expected: 6 passed

- [ ] **Step 5: ruff + 提交**

```bash
ruff check src/interfaces/api/ tests/interfaces/api/test_jobs_routes.py
git add src/interfaces/api/routes/jobs.py src/interfaces/api/app.py tests/interfaces/api/test_jobs_routes.py
git commit -m "feat(api): /api/jobs 任务路由 — 五种研究任务提交/查询/取消"
```

---

### Task 4: meta 路由（策略/因子元数据）

**Files:**
- Create: `src/interfaces/api/routes/meta.py`
- Test: `tests/interfaces/api/test_meta_routes.py`

- [ ] **Step 1: 先核对领域对象字段**

打开 `src/domain/strategy/factor_test/factor_catalog.py` 看 `FactorHypothesis` dataclass 实际字段名（预期: factor_id/name/category/expression/direction_note/evidence_strength/field_ready/priority），与 `src/domain/strategy/registry.py` 的 `StrategyConfig`（预期: name/strategy_type/description/default_params）。若字段名有出入，按实际调整下面代码与测试。

- [ ] **Step 2: 写失败测试**

```python
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
```

- [ ] **Step 3: 跑测试确认失败**

Run: `$WIN_PYTHON -m pytest tests/interfaces/api/test_meta_routes.py --basetemp=.pytest_tmp -q`
Expected: FAIL（404）

- [ ] **Step 4: 实现 `src/interfaces/api/routes/meta.py` + 挂载**

```python
"""元数据只读端点 — 驱动前端表单（策略选择/因子勾选）。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/strategies")
def strategies() -> dict:
    from src.domain.strategy.registry import list_strategies

    return {"strategies": [
        {
            "name": cfg.name,
            "strategy_type": cfg.strategy_type,
            "description": cfg.description,
            "default_params": {k: v for k, v in (cfg.default_params or {}).items()
                               if not k.startswith("_")},
        }
        for cfg in list_strategies()
    ]}


@router.get("/factors")
def factors() -> dict:
    from src.domain.strategy.factor_test.factor_catalog import ALL_FACTORS

    items = [
        {
            "factor_id": f.factor_id,
            "name": f.name,
            "category": f.category,
            "expression": f.expression,
            "direction_note": f.direction_note,
            "evidence_strength": f.evidence_strength,
            "field_ready": f.field_ready,
            "priority": f.priority,
        }
        for f in ALL_FACTORS
    ]
    groups: dict[str, list[str]] = {}
    for item in items:
        groups.setdefault(item["priority"], []).append(item["factor_id"])
    return {"factors": items, "groups": groups}
```

app.py 加：`app.include_router(meta.router, prefix="/api/meta", tags=["meta"])`（import 行同步加 `meta`）。

- [ ] **Step 5: 跑测试 + ruff + 提交**

Run: `$WIN_PYTHON -m pytest tests/interfaces/api/test_meta_routes.py --basetemp=.pytest_tmp -q` → 3 passed

```bash
ruff check src/interfaces/api/routes/meta.py tests/interfaces/api/test_meta_routes.py
git add src/interfaces/api/routes/meta.py src/interfaces/api/app.py tests/interfaces/api/test_meta_routes.py
git commit -m "feat(api): /api/meta 策略与因子元数据端点"
```

---

### Task 5: live 路由扩展 ①（audit + budget + config 依赖）

**Files:**
- Modify: `src/interfaces/api/routes/live.py`
- Test: `tests/interfaces/api/test_live_routes_ext.py`（新文件，独立 fixture）

- [ ] **Step 1: 写失败测试**

```python
"""live 路由扩展测试 — tmp sqlite + tmp yaml, 全部依赖可覆写。"""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.interfaces.api.app import app
from src.interfaces.api.routes.live import (
    get_trade_logs_dir,
    get_trading_config_path,
    get_trading_db_path,
)

_DDL = """
CREATE TABLE trading_cycles (cycle_id TEXT PRIMARY KEY, cycle_time TEXT, mode TEXT,
  strategy TEXT, signals_generated INTEGER, orders_submitted INTEGER,
  orders_rejected INTEGER, orders_failed INTEGER, notional_submitted REAL, note TEXT);
CREATE TABLE execution_records (order_id TEXT PRIMARY KEY, cycle_id TEXT, mode TEXT,
  symbol TEXT, direction TEXT, exec_price REAL, volume INTEGER, notional REAL,
  status TEXT, reject_reason TEXT, confidence REAL, submitted_at TEXT);
CREATE TABLE position_snapshots (snapshot_time TEXT, mode TEXT, symbol TEXT,
  total_volume INTEGER, available_volume INTEGER, average_cost REAL, last_price REAL);
CREATE TABLE account_snapshots (snapshot_time TEXT, mode TEXT, total_asset REAL,
  available_cash REAL, frozen_cash REAL, market_value REAL);
CREATE TABLE audit_logs (log_id TEXT PRIMARY KEY, user_id TEXT, action TEXT,
  resource_type TEXT, resource_id TEXT, timestamp TEXT, details TEXT, ip_address TEXT);
"""


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "trading.db"
    conn = sqlite3.connect(path)
    conn.executescript(_DDL)
    today = __import__("datetime").date.today().isoformat()
    conn.executemany(
        "INSERT INTO execution_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("o1", "c1", "dry_run", "600000.SH", "BUY", 10.0, 100, 1000.0,
             "DRY_RUN", None, 0.8, f"{today} 09:35:01"),
            ("o2", "c1", "dry_run", "000021.SZ", "BUY", 5.0, 100, 500.0,
             "REJECTED", "notional_cap", 0.7, f"{today} 09:35:02"),
            ("o3", "c2", "live", "600000.SH", "BUY", 10.0, 100, 1000.0,
             "FILLED", None, 0.9, f"{today} 14:50:01"),
        ])
    conn.executemany(
        "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?)",
        [
            ("a1", "auto-trade", "cycle_start", "cycle", "c1",
             f"{today} 09:35:00", "{}", None),
            ("a2", "auto-trade", "place_order", "order", "o1",
             f"{today} 09:35:01", json.dumps({"symbol": "600000.SH"}), None),
        ])
    conn.executemany(
        "INSERT INTO trading_cycles VALUES (?,?,?,?,?,?,?,?,?,?)",
        [("c1", f"{today} 09:35:00", "dry_run", "dual_ma", 3, 1, 1, 0, 1000.0, "")])
    conn.executemany(
        "INSERT INTO position_snapshots VALUES (?,?,?,?,?,?,?)",
        [
            (f"{today} 09:36:00", "dry_run", "600000.SH", 100, 0, 10.0, 10.1),
            (f"{today} 14:51:00", "live", "000021.SZ", 200, 200, 5.0, 5.2),
        ])
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture()
def cfg_path(tmp_path: Path) -> str:
    path = tmp_path / "trading.yaml"
    path.write_text(
        "auto_trade:\n"
        "  enabled: false\n"
        "  mode: dry_run\n"
        "  strategy: dual_ma\n"
        "  symbols: [\"600000.SH\"]\n"
        "  execution_times: [\"09:35\", \"14:50\"]\n"
        "  per_order_notional_cap: 1500.0\n"
        "  daily_notional_cap: 3000.0\n",
        encoding="utf-8")
    return str(path)


@pytest.fixture()
def client(db_path: str, cfg_path: str, tmp_path: Path):
    tickets = tmp_path / "trade_logs"
    tickets.mkdir()
    (tickets / "20260611-130232-601006.SH.json").write_text(
        json.dumps({"symbol": "601006.SH", "status": "FILLED"}), encoding="utf-8")
    app.dependency_overrides[get_trading_db_path] = lambda: db_path
    app.dependency_overrides[get_trading_config_path] = lambda: cfg_path
    app.dependency_overrides[get_trade_logs_dir] = lambda: str(tickets)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class TestAudit:
    def test_lists_logs_desc(self, client) -> None:
        logs = client.get("/api/live/audit").json()["logs"]
        assert [r["log_id"] for r in logs] == ["a2", "a1"]

    def test_action_filter(self, client) -> None:
        logs = client.get("/api/live/audit?action=cycle_start").json()["logs"]
        assert len(logs) == 1 and logs[0]["action"] == "cycle_start"

    def test_missing_db_empty(self, client, db_path) -> None:
        app.dependency_overrides[get_trading_db_path] = lambda: "/nope/x.db"
        assert client.get("/api/live/audit").json() == {"logs": []}


class TestBudget:
    def test_mirrors_trading_store_semantics(self, client) -> None:
        body = client.get("/api/live/budget").json()
        # o1(DRY_RUN)+o3(FILLED) 计入, o2(REJECTED) 不计 — 镜像 _BUDGET_STATUSES
        assert body["submitted_notional"] == 2000.0
        assert body["daily_notional_cap"] == 3000.0
        assert body["remaining"] == 1000.0
        assert body["per_order_notional_cap"] == 1500.0


class TestConfig:
    def test_config_and_slots(self, client) -> None:
        body = client.get("/api/live/config").json()
        assert body["auto_trade"]["mode"] == "dry_run"
        assert body["auto_trade"]["enabled"] is False
        assert body["today"]["expected_slots"] == ["09:35", "14:50"]
        assert body["today"]["cycles_today"] == 1

    def test_missing_yaml_graceful(self, client) -> None:
        app.dependency_overrides[get_trading_config_path] = lambda: "/nope/y.yaml"
        body = client.get("/api/live/config").json()
        assert body["config_exists"] is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$WIN_PYTHON -m pytest tests/interfaces/api/test_live_routes_ext.py --basetemp=.pytest_tmp -q`
Expected: FAIL（ImportError: get_trading_config_path）

- [ ] **Step 3: 实现（live.py 追加）**

文件头 import 增加 `import json`、`from datetime import date`（已有）、`import yaml`。追加：

```python
# ---- 交互驾驶舱扩展: 审计/预算/配置只读视角（设计 0612 §3.4）----

# 镜像 src/infrastructure/persistence/trading_store.py::_BUDGET_STATUSES —
# 预算口径跨 mode 统计(dry/live 同一真实账户), REJECTED/FAILED 不计
_BUDGET_STATUSES = ("DRY_RUN", "SUBMITTED", "FILLED", "PARTIAL", "CANCELED",
                    "TIMEOUT_CANCELED", "TIMEOUT_UNCANCELED", "ALIVE")


def get_trading_config_path() -> str:
    return os.environ.get("GHQ_TRADING_CONFIG", "resources/trading.yaml")


def get_trade_logs_dir() -> str:
    return os.environ.get("GHQ_TRADE_LOGS_DIR", "data/trade_logs")


def _load_auto_trade_section(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    section = data.get("auto_trade") or {}
    keys = ("enabled", "mode", "strategy", "symbols", "execution_times",
            "min_confidence", "max_orders_per_cycle", "per_order_notional_cap",
            "daily_notional_cap", "daily_loss_limit_ratio")
    return {k: section[k] for k in keys if k in section}


@router.get("/audit")
def audit(limit: int = 100, action: str = "",
          db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"logs": []}
    try:
        sql = "SELECT * FROM audit_logs"
        params: tuple = ()
        if action:
            sql += " WHERE action=?"
            params = (action,)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        try:
            return {"logs": _rows(conn, sql, (*params, min(limit, 500)))}
        except sqlite3.OperationalError:  # 旧库无 audit_logs 表
            return {"logs": []}
    finally:
        conn.close()


@router.get("/budget")
def budget(db_path: str = Depends(get_trading_db_path),
           cfg_path: str = Depends(get_trading_config_path)) -> dict:
    cfg = _load_auto_trade_section(cfg_path)
    today = date.today().isoformat()
    submitted = 0.0
    conn = _connect_ro(db_path)
    if conn is not None:
        try:
            placeholders = ", ".join("?" for _ in _BUDGET_STATUSES)
            try:
                cur = conn.execute(
                    f"SELECT COALESCE(SUM(notional), 0) FROM execution_records "
                    f"WHERE date(submitted_at)=? AND status IN ({placeholders})",
                    (today, *_BUDGET_STATUSES))
                submitted = float(cur.fetchone()[0])
            except sqlite3.OperationalError:
                pass
        finally:
            conn.close()
    daily_cap = cfg.get("daily_notional_cap")
    remaining = (float(daily_cap) - submitted
                 if isinstance(daily_cap, (int, float)) else None)
    return {"date": today, "submitted_notional": submitted,
            "daily_notional_cap": daily_cap,
            "per_order_notional_cap": cfg.get("per_order_notional_cap"),
            "remaining": remaining}


@router.get("/config")
def config(db_path: str = Depends(get_trading_db_path),
           cfg_path: str = Depends(get_trading_config_path)) -> dict:
    cfg = _load_auto_trade_section(cfg_path)
    cycles_today = 0
    conn = _connect_ro(db_path)
    if conn is not None:
        try:
            try:
                cycles_today = conn.execute(
                    "SELECT COUNT(*) FROM trading_cycles WHERE date(cycle_time)=?",
                    (date.today().isoformat(),)).fetchone()[0]
            except sqlite3.OperationalError:
                pass
        finally:
            conn.close()
    return {"config_exists": bool(cfg), "auto_trade": cfg,
            "today": {"expected_slots": cfg.get("execution_times") or [],
                      "cycles_today": cycles_today}}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `$WIN_PYTHON -m pytest tests/interfaces/api/test_live_routes_ext.py --basetemp=.pytest_tmp -q`
Expected: TestAudit/TestBudget/TestConfig 7 passed（tickets 测试在 Task 6 加）

同时回归旧用例: `$WIN_PYTHON -m pytest tests/interfaces/api/test_live_routes.py --basetemp=.pytest_tmp -q`

- [ ] **Step 5: ruff + 提交**

```bash
ruff check src/interfaces/api/routes/live.py tests/interfaces/api/test_live_routes_ext.py
git add src/interfaces/api/routes/live.py tests/interfaces/api/test_live_routes_ext.py
git commit -m "feat(api): live 路由扩展① — 审计日志/预算消耗/配置只读视角"
```

---

### Task 6: live 路由扩展 ②（循环钻取 + mode 过滤 + tickets）

**Files:**
- Modify: `src/interfaces/api/routes/live.py`
- Test: `tests/interfaces/api/test_live_routes_ext.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
class TestCycleDrilldown:
    def test_executions_of_cycle(self, client) -> None:
        body = client.get("/api/live/cycles/c1/executions").json()
        assert [e["order_id"] for e in body["executions"]] == ["o1", "o2"]

    def test_unknown_cycle_empty(self, client) -> None:
        assert client.get("/api/live/cycles/nope/executions").json() == {"executions": []}


class TestModeFilter:
    def test_positions_mode_filter(self, client) -> None:
        all_rows = client.get("/api/live/positions").json()["positions"]
        live_rows = client.get("/api/live/positions?mode=live").json()["positions"]
        # 无 mode: 取全局最新快照(live 14:51); 有 mode: 取该 mode 最新快照
        assert {r["symbol"] for r in all_rows} == {"000021.SZ"}
        assert {r["symbol"] for r in live_rows} == {"000021.SZ"}
        dry_rows = client.get("/api/live/positions?mode=dry_run").json()["positions"]
        assert {r["symbol"] for r in dry_rows} == {"600000.SH"}

    def test_equity_mode_filter(self, client, db_path) -> None:
        conn = sqlite3.connect(db_path)
        conn.executemany(
            "INSERT INTO account_snapshots VALUES (?,?,?,?,?,?)",
            [("2026-06-12 09:36:00", "dry_run", 100000, 90000, 0, 10000),
             ("2026-06-12 14:51:00", "live", 146000, 100000, 0, 46000)])
        conn.commit()
        conn.close()
        series = client.get("/api/live/equity?mode=live").json()["series"]
        assert len(series) == 1 and series[0]["mode"] == "live"


class TestTickets:
    def test_lists_ticket_json(self, client) -> None:
        body = client.get("/api/live/tickets").json()
        assert body["tickets"][0]["file"] == "20260611-130232-601006.SH.json"
        assert body["tickets"][0]["content"]["symbol"] == "601006.SH"

    def test_missing_dir_empty(self, client) -> None:
        app.dependency_overrides[get_trade_logs_dir] = lambda: "/nope/dir"
        assert client.get("/api/live/tickets").json() == {"tickets": []}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$WIN_PYTHON -m pytest tests/interfaces/api/test_live_routes_ext.py --basetemp=.pytest_tmp -q`
Expected: 新增 6 个 FAIL

- [ ] **Step 3: 实现**

live.py 追加端点 + 改两个现有端点签名（向后兼容: 不带 mode 行为不变）：

```python
@router.get("/cycles/{cycle_id}/executions")
def cycle_executions(cycle_id: str,
                     db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"executions": []}
    try:
        return {"executions": _rows(
            conn, "SELECT * FROM execution_records WHERE cycle_id=? "
                  "ORDER BY submitted_at", (cycle_id,))}
    finally:
        conn.close()


@router.get("/tickets")
def tickets(limit: int = 50,
            logs_dir: str = Depends(get_trade_logs_dir)) -> dict:
    root = Path(logs_dir)
    if not root.is_dir():
        return {"tickets": []}
    out = []
    for fp in sorted(root.glob("*.json"), reverse=True)[: min(limit, 200)]:
        try:
            content = json.loads(fp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            content = None
        out.append({"file": fp.name, "content": content})
    return {"tickets": out}
```

修改现有 `positions`/`equity`（保持无参行为不变）：

```python
@router.get("/positions")
def positions(mode: str = "", db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"positions": [], "snapshot_time": None}
    try:
        if mode:
            rows = _rows(conn, """SELECT * FROM position_snapshots
                                  WHERE mode=? AND snapshot_time=(
                                    SELECT MAX(snapshot_time) FROM position_snapshots
                                    WHERE mode=?)
                                  ORDER BY symbol""", (mode, mode))
        else:
            rows = _rows(conn, """SELECT * FROM position_snapshots WHERE snapshot_time=(
                                    SELECT MAX(snapshot_time) FROM position_snapshots)
                                  ORDER BY symbol""")
        return {"positions": rows,
                "snapshot_time": rows[0]["snapshot_time"] if rows else None}
    finally:
        conn.close()


@router.get("/equity")
def equity(limit: int = 500, mode: str = "",
           db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"series": []}
    try:
        if mode:
            rows = _rows(conn, """SELECT * FROM (
                                    SELECT * FROM account_snapshots WHERE mode=?
                                    ORDER BY snapshot_time DESC LIMIT ?
                                  ) ORDER BY snapshot_time ASC""",
                         (mode, min(limit, 2000)))
        else:
            rows = _rows(conn, """SELECT * FROM (
                                    SELECT * FROM account_snapshots
                                    ORDER BY snapshot_time DESC LIMIT ?
                                  ) ORDER BY snapshot_time ASC""", (min(limit, 2000),))
        return {"series": rows}
    finally:
        conn.close()
```

- [ ] **Step 4: 跑测试确认通过 + 回归**

Run: `$WIN_PYTHON -m pytest tests/interfaces/api/test_live_routes_ext.py tests/interfaces/api/test_live_routes.py --basetemp=.pytest_tmp -q`
Expected: 全部 passed

- [ ] **Step 5: ruff + 提交**

```bash
ruff check src/interfaces/api/routes/live.py tests/interfaces/api/test_live_routes_ext.py
git add src/interfaces/api/routes/live.py tests/interfaces/api/test_live_routes_ext.py
git commit -m "feat(api): live 路由扩展② — 循环钻取/mode过滤/order ticket"
```

---

### Task 7: compare_strategies CLI 增强（--initial-capital + --config 生效 + 单策略）

**Files:**
- Modify: `src/interfaces/cli/compare_strategies.py`
- Test: `tests/application/test_strategy_comparison_app.py`（追加）、`tests/interfaces/cli/test_compare_strategies_args.py`（新建）

- [ ] **Step 1: 写失败测试**

`tests/interfaces/cli/__init__.py` 若不存在则建空文件。`tests/interfaces/cli/test_compare_strategies_args.py`：

```python
"""compare_strategies 参数解析测试（不跑回测）。"""

from src.interfaces.cli.compare_strategies import parse_args


class TestParseArgs:
    def test_initial_capital_flag(self) -> None:
        args = parse_args(["--strategies", "dual_ma", "--initial-capital", "200000"])
        assert args.initial_capital == 200000.0

    def test_initial_capital_default_none(self) -> None:
        args = parse_args(["--strategies", "dual_ma"])
        assert args.initial_capital is None

    def test_single_strategy_accepted(self) -> None:
        args = parse_args(["--strategies", "dual_ma"])
        assert args.strategies == "dual_ma"
```

`tests/application/test_strategy_comparison_app.py` 追加（沿用该文件现有 `_make_report`/fake 基建——先读该文件，复用其已有构造方式）：

```python
def test_single_strategy_comparison_does_not_crash(self) -> None:
    """单策略也能出对比报告（Web 回测统一走 compare 入口的前提）。"""
    # 按本文件 test_compare_two_strategies_returns_report 的既有 fake/构造方式,
    # 只传一个策略名, 断言 report.metric_table 长度为 1 且不抛异常。
```

注意：追加用例必须复用文件内既有 fixture/fake 写法（读完再写），断言: `len(report.metric_table) == 1`、`report.reports[0].strategy_name` 正确、`build_comparison` 不抛。

- [ ] **Step 2: 跑测试确认失败**

Run: `$WIN_PYTHON -m pytest tests/interfaces/cli/test_compare_strategies_args.py tests/application/test_strategy_comparison_app.py --basetemp=.pytest_tmp -q`
Expected: parse_args 不接受 argv 参数 → TypeError FAIL；单策略用例视实现而定（若 PASS 说明单策略本就可用，保留作回归契约）

- [ ] **Step 3: 实现**

`compare_strategies.py` 三处改动：

```python
# 1) parse_args 可注入 argv（测试用）+ 新 flag
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ...
    parser.add_argument("--initial-capital", type=float, default=None,
                        help="初始资金覆盖（默认用配置文件值）")
    return parser.parse_args(argv)

# 2) main() 里让 --config 真生效（原 bug: load_backtest_config() 忽略 args.config）
    try:
        settings = (load_backtest_config(args.config) if args.config
                    else load_backtest_config())
        ...

# 3) 初始资金覆盖（在 initial_capital 赋值之后）
    if args.initial_capital:
        initial_capital = args.initial_capital
```

若 Step 2 中单策略用例失败，修 `ComparisonReportService.build_comparison` 的单策略路径（最小改动，如相关性矩阵对单策略返回 `[[1.0]]`）。

- [ ] **Step 4: 跑测试确认通过**

Run: `$WIN_PYTHON -m pytest tests/interfaces/cli/test_compare_strategies_args.py tests/application/test_strategy_comparison_app.py tests/domain/backtest/ --basetemp=.pytest_tmp -q`
Expected: 全部 passed

- [ ] **Step 5: ruff + 提交**

```bash
ruff check src/interfaces/cli/compare_strategies.py tests/interfaces/cli/
git add src/interfaces/cli/compare_strategies.py tests/interfaces/cli/ tests/application/test_strategy_comparison_app.py
git commit -m "feat(cli): compare_strategies 支持 --initial-capital 并修复 --config 失效"
```

---

### Task 8: app.py 接线收口 + 死代码清理

**Files:**
- Modify: `src/interfaces/api/app.py`
- Delete: 见清单

- [ ] **Step 1: 删除前确认引用面**

```bash
grep -rn "account_routes\|backtest_routes\|routes import dashboard\|routes.dashboard\|dashboard_app\|websocket_manager\|dashboard_data_provider\|dashboard_ports\|dashboard_snapshot" src/ tests/ --include="*.py" | grep -v "_test\|test_"
```
预期只剩本任务要删/要改的文件互相引用。若出现计划外引用者，停下来评估（不要硬删）。

- [ ] **Step 2: 删除死代码（git rm）**

```bash
git rm src/interfaces/api/routes/dashboard.py \
       src/interfaces/api/routes/account_routes.py \
       src/interfaces/api/routes/backtest_routes.py \
       src/application/dashboard_app.py \
       src/infrastructure/web/websocket_manager.py \
       src/infrastructure/web/dashboard_data_provider.py \
       src/domain/backtest/interfaces/dashboard_ports.py \
       src/domain/backtest/value_objects/dashboard_snapshot.py \
       tests/interfaces/api/routes/test_dashboard.py \
       tests/interfaces/api/test_backtest_routes.py \
       tests/application/test_dashboard_app.py \
       tests/infrastructure/web/test_websocket_manager.py \
       tests/infrastructure/web/test_dashboard_data_provider.py \
       tests/domain/backtest/value_objects/test_dashboard_snapshot.py
```
若 `tests/interfaces/api/routes/` 只剩 `__init__.py` 一并删；`src/infrastructure/web/`、`tests/infrastructure/web/` 同理。`src/domain/backtest/interfaces/__init__.py` 与 `value_objects/__init__.py` 若 re-export 被删对象，同步清掉对应行。

- [ ] **Step 3: 重写 app.py**

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.interfaces.api.routes import jobs, live, meta, research

app = FastAPI(title="GoldenHandQuant API", version="0.2.0")
app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(live.router, prefix="/api/live", tags=["live"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(meta.router, prefix="/api/meta", tags=["meta"])

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/ui", StaticFiles(directory=str(_STATIC_DIR), html=True), name="ui")


@app.get("/", include_in_schema=False)
async def index_redirect():
    return RedirectResponse(url="/ui/", status_code=302)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.2.0"}
```

- [ ] **Step 4: 全量回归**

Run: `$WIN_PYTHON -m pytest tests/ --ignore=tests/infrastructure/gateway/ --basetemp=.pytest_tmp -q`
Expected: 全部 passed（删掉的测试不再被收集）

Run: `ruff check src/`

- [ ] **Step 5: 提交**

```bash
git add src/interfaces/api/app.py
git commit -m "refactor(api): 挂载 jobs/meta 路由; 清理 dashboard/account/backtest 三族死代码"
```
（git rm 的文件已在暂存区，一并入此提交。）

---

### Task 9: 前端骨架 — index.html 重构 + app.js 拆 ES modules（行为不变）

**Files:**
- Rewrite: `src/interfaces/api/static/index.html`
- Create: `static/js/api.js`、`static/js/charts.js`、`static/js/main.js`、`static/js/pages/{overview,verdicts,explorer,backtests,live}.js`
- Delete: `static/app.js`
- Modify: `static/style.css`（追加）

本任务**只搬家不加功能**——新表单容器留空 div，Task 10-13 填。

- [ ] **Step 1: 新 index.html**

整体结构沿用现状，差异点：
1. `<nav>` 加 `<button class="tab" data-tab="jobs">任务</button>`；
2. header 的 meta 旁加任务指示灯：`<span id="job-indicator" class="job-indicator hidden"><span class="pulse"></span><span id="job-count">0</span></span>`；
3. 每个面板顶部加表单容器占位：
   - `#tab-overview` 开头: `<div id="refresh-form-slot"></div>`
   - `#tab-verdicts` 开头: `<div id="factor-form-slot"></div>`
   - `#tab-backtests` 开头: `<div id="bt-form-slot"></div>`
   - `#tab-live` 的 `#live-cards` 之后: `<div id="live-ops-cards" class="cards" style="margin-bottom:14px"></div>`，页面底部追加审计/ticket 区块（Task 12 填充结构，先放 `<div id="live-ext-slot"></div>`）
4. 新面板：
```html
<section id="tab-jobs" class="panel">
  <div id="ml-forms-slot"></div>
  <h3 class="section-title">任务列表</h3>
  <table id="jobs-table" class="verdict-table">
    <thead><tr><th>ID</th><th>类型</th><th>参数</th><th>状态</th>
               <th>创建</th><th>耗时</th><th>操作</th></tr></thead>
    <tbody></tbody>
  </table>
  <p id="jobs-empty" class="empty hidden">暂无任务 — 在各页签提交回测/因子检验/数据刷新。</p>
  <h3 class="section-title">任务日志 <span id="job-log-title" class="run-params"></span></h3>
  <pre id="job-log" class="job-log">选择任务查看日志</pre>
</section>
```
5. 脚本改为：`<script src="vendor/echarts.min.js"></script>` + `<script type="module" src="js/main.js"></script>`（删除 app.js 引用）。

- [ ] **Step 2: js/api.js（基础设施层）**

```javascript
/* 基础 fetch / 错误条 / 数字格式化 — 全页共用 */
"use strict";

export const $ = (sel) => document.querySelector(sel);
export const API = "/api/research";

export async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) {
    const body = await resp.text();
    if (resp.status === 503 && (window.__activeJobs || 0) > 0) {
      throw new Error("后台任务运行中，数据库写锁占用，稍后自动恢复");
    }
    throw new Error(`${resp.status} ${url}: ${body.slice(0, 200)}`);
  }
  return resp.json();
}

export async function postJSON(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const detail = typeof body.detail === "string"
      ? body.detail : JSON.stringify(body.detail ?? body).slice(0, 300);
    throw new Error(`${resp.status}: ${detail}`);
  }
  return body;
}

export function showError(msg) {
  const el = $("#error-banner");
  el.textContent = `⚠ ${msg}`;
  el.classList.remove("hidden");
}

export function clearError() {
  $("#error-banner").classList.add("hidden");
}

export const f4 = (v) => v.toFixed(4);
export const f3 = (v) => v.toFixed(3);
export const f2 = (v) => v.toFixed(2);
export const pct = (v) => `${(v * 100).toFixed(2)}%`;
export const num = (v) => (v === null || v === undefined ? "-" : Number(v).toLocaleString());
```

- [ ] **Step 3: js/charts.js**

```javascript
/* ECharts 实例注册表 — 统一暗色主题与 resize */
"use strict";

const registry = [];

export function makeChart(el) {
  const chart = echarts.init(el, "dark");
  registry.push(chart);
  return chart;
}

export function resizeCharts() {
  setTimeout(() => registry.forEach((c) => c.resize()), 0);
}

window.addEventListener("resize", resizeCharts);
```

- [ ] **Step 4: 五个 page 模块（搬运 app.js 既有代码）**

精确搬运映射（函数体逐字保留，只改三类东西：① 顶部加 import；② `echarts.init(el,"dark")`+null 检查 → `makeChart`；③ 模块局部状态保持模块内）：

| 新文件 | 从 app.js 搬入 | export |
|---|---|---|
| `js/pages/overview.js` | TABLE_LABELS、loadOverview | `loadOverview` |
| `js/pages/verdicts.js` | GATES、gateCell、verdictRuns、loadVerdicts、renderRun | `loadVerdicts` |
| `js/pages/explorer.js` | FEATURE_CHOICES、DEFAULT_FEATURES、initFeaturePicker、pickedSymbol、rangeParams、loadKline、loadFeatures、symbol 联想监听、`#load-symbol` 点击监听 | `initExplorer`（包住 initFeaturePicker+两个监听注册） |
| `js/pages/backtests.js` | btRuns、loadBacktests、renderBtRun | `loadBacktests` |
| `js/pages/live.js` | STATUS_BADGE、liveTimer、loadLive、setLivePolling | `setLivePolling` |

格式化函数（f2/f3/f4/pct/num）改从 `../api.js` import；图表对象一律 `let chart = null; if (!chart) chart = makeChart($(...))` 形式保留惰性创建。

- [ ] **Step 5: js/main.js（启动与路由）**

```javascript
/* 启动: 页签路由 + 各页装配 + 全局任务指示灯 */
"use strict";

import { $, fetchJSON, showError } from "./api.js";
import { resizeCharts } from "./charts.js";
import { loadOverview } from "./pages/overview.js";
import { loadVerdicts } from "./pages/verdicts.js";
import { initExplorer } from "./pages/explorer.js";
import { loadBacktests } from "./pages/backtests.js";
import { setLivePolling } from "./pages/live.js";

const TABS = ["overview", "verdicts", "explorer", "backtests", "live", "jobs"];

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
    location.hash = btn.dataset.tab;
    if (btn.dataset.tab === "explorer") resizeCharts();
    if (btn.dataset.tab === "backtests") loadBacktests().catch((e) => showError(e.message));
    setLivePolling(btn.dataset.tab === "live");
  });
});

// 全局任务指示灯（Task 13 完整接管; 先保底显示活跃数）
async function pollIndicator() {
  try {
    const data = await fetchJSON("/api/jobs?limit=20");
    const active = data.jobs.filter(
      (j) => j.status === "queued" || j.status === "running").length;
    window.__activeJobs = active;
    $("#job-indicator").classList.toggle("hidden", active === 0);
    $("#job-count").textContent = String(active);
  } catch { /* 指示灯失败静默 */ }
}
setInterval(pollIndicator, 5000);

(async function init() {
  initExplorer();
  const tab = location.hash.replace("#", "");
  if (tab && TABS.includes(tab)) {
    document.querySelector(`.tab[data-tab="${tab}"]`).click();
  }
  pollIndicator();
  try {
    await Promise.all([loadOverview(), loadVerdicts()]);
  } catch (err) {
    showError(err.message);
  }
})();
```

- [ ] **Step 6: style.css 追加**

```css
/* ---- 交互化追加 ---- */
.job-indicator { display: inline-flex; align-items: center; gap: 6px;
  color: var(--accent); font-size: 12px; margin-right: 14px; }
.pulse { width: 8px; height: 8px; border-radius: 50%; background: var(--accent);
  animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 0%,100% { opacity: .3 } 50% { opacity: 1 } }

.form-card { background: var(--panel); border: 1px solid var(--border);
  border-radius: 8px; margin-bottom: 14px; }
.form-card > summary { cursor: pointer; padding: 10px 16px; color: var(--accent);
  font-weight: 600; list-style: none; }
.form-card > summary::before { content: "▸ "; }
.form-card[open] > summary::before { content: "▾ "; }
.form-card .form-body { padding: 0 16px 14px; display: flex; flex-direction: column; gap: 10px; }
.form-row { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; }
.form-row label { color: var(--text-dim); display: flex; align-items: center; gap: 6px; font-size: 13px; }
.form-row input, .form-row select { background: var(--bg); color: var(--text);
  border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; font-size: 13px; }
.form-hint { color: #d29922; font-size: 12px; }
.check-group { display: flex; gap: 12px; flex-wrap: wrap; }
.check-group label { font-size: 13px; color: var(--text); display: flex; gap: 4px; align-items: center; }
.check-group label.disabled { color: var(--na); text-decoration: line-through; }
.group-title { color: var(--text-dim); font-size: 12px; margin-right: 4px; }
.btn-primary { background: var(--accent); color: #fff; border: none; border-radius: 6px;
  padding: 7px 18px; cursor: pointer; font-size: 13px; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-danger { background: none; border: 1px solid var(--bad); color: var(--bad);
  border-radius: 6px; padding: 3px 10px; cursor: pointer; font-size: 12px; }

.job-card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  padding: 12px 16px; margin-bottom: 14px; }
.job-card .head { display: flex; gap: 12px; align-items: center; margin-bottom: 8px; }
.job-log { background: #0a0e13; border: 1px solid var(--border); border-radius: 6px;
  padding: 10px 12px; font-size: 12px; line-height: 1.5; max-height: 260px;
  overflow: auto; white-space: pre-wrap; color: var(--text-dim); }
.badge.queued { background: rgba(110,118,129,.2); color: var(--na); }
.badge.running { background: rgba(77,159,255,.15); color: var(--accent); }
.badge.succeeded { background: rgba(63,185,80,.15); color: var(--good); }
.badge.failed { background: rgba(248,81,73,.15); color: var(--bad); }
.badge.canceled { background: rgba(210,153,34,.18); color: #d29922; }

.clickable { cursor: pointer; }
.row-detail td { background: #11151b; padding: 8px 14px; }
.row-detail table { width: 100%; font-size: 12px; }
.ticket-item summary { cursor: pointer; color: var(--accent); font-size: 13px; padding: 4px 0; }
.ticket-pre { background: #0a0e13; padding: 8px 12px; border-radius: 6px;
  font-size: 12px; overflow auto; }
```

注意最后一行笔误风险：`overflow: auto;`（写代码时带冒号）。

- [ ] **Step 7: 删除 app.js + 冒烟验证**

```bash
git rm src/interfaces/api/static/app.js
```

冒烟（TestClient 直验静态与路由，跨环境稳定）：

```bash
$WIN_PYTHON -c "
from fastapi.testclient import TestClient
from src.interfaces.api.app import app
c = TestClient(app)
html = c.get('/ui/').text
assert 'js/main.js' in html and 'data-tab=\"jobs\"' in html, 'index.html 装配缺失'
for path in ['js/main.js','js/api.js','js/charts.js','js/jobs.js' if False else 'js/main.js',
             'js/pages/overview.js','js/pages/verdicts.js','js/pages/explorer.js',
             'js/pages/backtests.js','js/pages/live.js']:
    r = c.get(f'/ui/{path}')
    assert r.status_code == 200, path
print('static smoke OK')
"
```

浏览器人工冒烟（实施者在 Windows 侧）：`$WIN_PYTHON -m src.interfaces.cli.quant dashboard` → 五个旧页签行为与改前一致、无 console 报错。

- [ ] **Step 8: 提交**

```bash
git add src/interfaces/api/static/
git commit -m "refactor(ui): app.js 拆 ES modules + 任务页签骨架（行为不变）"
```

---

### Task 10: 前端 — 任务卡组件 + 回测表单

**Files:**
- Create: `static/js/jobs.js`
- Modify: `static/js/pages/backtests.js`、`static/js/main.js`、`static/index.html`

- [ ] **Step 1: js/jobs.js（任务提交/轮询/卡片渲染，全站复用）**

```javascript
/* 任务提交与状态卡片 — 各页表单复用 */
"use strict";

import { $, fetchJSON, postJSON, num } from "./api.js";

export async function submitJob(type, payload) {
  return postJSON(`/api/jobs/${type}`, payload);
}

const STATUS_LABEL = {
  queued: "排队中", running: "运行中", succeeded: "已完成",
  failed: "失败", canceled: "已取消",
};

function durationOf(job) {
  if (!job.started_at) return "-";
  const end = job.finished_at ? new Date(job.finished_at) : new Date();
  const sec = Math.max(0, (end - new Date(job.started_at)) / 1000);
  return sec < 90 ? `${sec.toFixed(0)}s` : `${(sec / 60).toFixed(1)}min`;
}

export function paramsSummary(job) {
  const p = job.params || {};
  const parts = [];
  if (p.strategies) parts.push(p.strategies.join(","));
  if (p.factors) parts.push(p.factors);
  if (p.model_name) parts.push(p.model_name);
  if (p.start_date) parts.push(`${p.start_date}~${p.end_date || ""}`);
  if (p.objective) parts.push(p.objective);
  return parts.join(" · ").slice(0, 80);
}

/* 在 container 内渲染一张实时刷新的任务卡; 终态后停轮询并回调 onDone(job) */
export function attachJobCard(container, jobId, { onDone } = {}) {
  const card = document.createElement("div");
  card.className = "job-card";
  card.innerHTML = `
    <div class="head">
      <span class="badge queued">排队中</span>
      <span class="dim job-meta"></span>
      <button class="btn-danger job-cancel">取消</button>
    </div>
    <pre class="job-log">等待日志…</pre>`;
  container.prepend(card);

  const badge = card.querySelector(".badge");
  const meta = card.querySelector(".job-meta");
  const logEl = card.querySelector(".job-log");
  const cancelBtn = card.querySelector(".job-cancel");
  let timer = null;
  let done = false;

  cancelBtn.addEventListener("click", async () => {
    try { await postJSON(`/api/jobs/${jobId}/cancel`); } catch { /* 已结束 */ }
  });

  async function tick() {
    let job;
    try {
      job = await fetchJSON(`/api/jobs/${jobId}?tail=120`);
    } catch { return; }
    badge.className = `badge ${job.status}`;
    badge.textContent = STATUS_LABEL[job.status] || job.status;
    meta.textContent = `${job.job_type} · ${paramsSummary(job)} · 耗时 ${durationOf(job)}`;
    if (job.log_tail && job.log_tail.length) {
      logEl.textContent = job.log_tail.join("\n");
      logEl.scrollTop = logEl.scrollHeight;
    }
    const terminal = ["succeeded", "failed", "canceled"].includes(job.status);
    if (terminal && !done) {
      done = true;
      clearInterval(timer);
      cancelBtn.remove();
      if (job.status === "succeeded" && onDone) onDone(job);
    }
  }
  tick();
  timer = setInterval(tick, 2000);
  return card;
}
```

- [ ] **Step 2: index.html 回测表单结构（填入 `#bt-form-slot`）**

```html
<details class="form-card" id="bt-form">
  <summary>新建回测 / 多策略对比</summary>
  <div class="form-body">
    <div class="form-row">
      <span class="group-title">策略</span>
      <span class="check-group" id="bt-strategies"></span>
    </div>
    <div class="form-row" id="bt-params"></div>
    <div class="form-row">
      <label>起 <input type="date" id="bt-start" value="2024-01-01"></label>
      <label>止 <input type="date" id="bt-end" value="2025-12-31"></label>
      <label>初始资金 <input type="number" id="bt-capital" placeholder="配置默认" step="10000"></label>
      <label>配置 <select id="bt-config">
        <option value="">resources/backtest.yaml（默认）</option>
        <option value="resources/backtest_multi_factor.yaml">backtest_multi_factor.yaml</option>
      </select></label>
    </div>
    <div class="form-row">
      <label style="flex:1">标的（逗号分隔，留空=配置默认）
        <input id="bt-symbols" style="flex:1" placeholder="000021.SZ,600000.SH"></label>
      <button class="btn-primary" id="bt-submit">提交回测</button>
    </div>
    <div class="form-hint hidden" id="bt-hint"></div>
  </div>
</details>
<div id="bt-job-area"></div>
```

- [ ] **Step 3: backtests.js 追加表单逻辑**

```javascript
import { submitJob, attachJobCard } from "../jobs.js";
// 既有 import 保持

let strategyMeta = [];

export async function initBacktestForm() {
  const data = await fetchJSON("/api/meta/strategies");
  strategyMeta = data.strategies;
  const box = $("#bt-strategies");
  box.innerHTML = strategyMeta.map((s) => `
    <label title="${s.description}">
      <input type="checkbox" value="${s.name}" ${s.name === "dual_ma" ? "checked" : ""}>
      ${s.name}<span class="group-title">[${s.strategy_type === "cross_section" ? "截面" : "时序"}]</span>
    </label>`).join("");
  box.querySelectorAll("input").forEach((cb) =>
    cb.addEventListener("change", renderParamInputs));
  renderParamInputs();
  $("#bt-submit").addEventListener("click", submitBacktest);
}

function selectedStrategies() {
  return [...document.querySelectorAll("#bt-strategies input:checked")].map((c) => c.value);
}

function renderParamInputs() {
  const names = selectedStrategies();
  const rows = [];
  for (const name of names) {
    const meta = strategyMeta.find((s) => s.name === name);
    for (const [key, val] of Object.entries(meta.default_params || {})) {
      if (typeof val === "object") continue; // 字典参数(权重)走配置文件, 设计 DD-8
      rows.push(`<label>${name}.${key}
        <input data-strat="${name}" data-key="${key}" value="${val}" size="8"></label>`);
    }
  }
  $("#bt-params").innerHTML = rows.join("");
  const hasCross = names.some((n) =>
    strategyMeta.find((s) => s.name === n)?.strategy_type === "cross_section");
  $("#bt-hint").classList.toggle("hidden", !hasCross);
  $("#bt-hint").textContent =
    "截面策略需基本面通道（QMT 客户端在线，或配置 Tushare），且全市场回测耗时数分钟。";
}

async function submitBacktest() {
  clearError();
  const strategies = selectedStrategies();
  if (!strategies.length) { showError("至少选择一个策略"); return; }
  const payload = {
    strategies,
    start_date: $("#bt-start").value,
    end_date: $("#bt-end").value,
  };
  const symbols = $("#bt-symbols").value.trim();
  if (symbols) payload.symbols = symbols.split(",").map((s) => s.trim()).filter(Boolean);
  const capital = Number($("#bt-capital").value);
  if (capital > 0) payload.initial_capital = capital;
  if ($("#bt-config").value) payload.config = $("#bt-config").value;
  const params = {};
  document.querySelectorAll("#bt-params input").forEach((inp) => {
    const meta = strategyMeta.find((s) => s.name === inp.dataset.strat);
    const dflt = String((meta.default_params || {})[inp.dataset.key]);
    if (inp.value !== dflt) {
      (params[inp.dataset.strat] ??= {})[inp.dataset.key] = inp.value;
    }
  });
  if (Object.keys(params).length) payload.params = params;
  try {
    const job = await submitJob("backtest", payload);
    attachJobCard($("#bt-job-area"), job.job_id, {
      onDone: () => loadBacktests().catch((e) => showError(e.message)),
    });
  } catch (err) {
    showError(err.message);
  }
}
```

main.js 的 init 里追加：`initBacktestForm().catch(() => {})`（import 同步加）。

- [ ] **Step 4: 冒烟 + 提交**

TestClient 冒烟同 Task 9 模式（断言 `/ui/js/jobs.js` 200、index.html 含 `bt-form`）。浏览器人工验证：勾 dual_ma 提交 → 任务卡出现、日志滚动、完成后回测列表自动刷新出新 run。

```bash
git add src/interfaces/api/static/
git commit -m "feat(ui): 回测页交互表单 + 通用任务卡组件（提交/日志/取消/完成刷新）"
```

---

### Task 11: 前端 — 因子检验表单 + 数据刷新表单

**Files:**
- Modify: `static/index.html`、`static/js/pages/verdicts.js`、`static/js/pages/overview.js`、`static/js/main.js`

- [ ] **Step 1: index.html 表单结构**

`#factor-form-slot`：

```html
<details class="form-card" id="ft-form">
  <summary>新建因子检验</summary>
  <div class="form-body">
    <div class="form-row"><span class="group-title">因子</span>
      <span class="check-group" id="ft-factors"></span></div>
    <div class="form-row">
      <label>起 <input type="date" id="ft-start" value="2021-01-01"></label>
      <label>止 <input type="date" id="ft-end" value="2025-12-31"></label>
      <label>IS/OOS 切分 <input type="date" id="ft-split" value="2024-06-30"></label>
      <label>记分牌 <select id="ft-objective">
        <option value="long_short">多空价差</option>
        <option value="long_only">Top层纯多头超额</option>
      </select></label>
    </div>
    <div class="form-row">
      <label>分层 <input type="number" id="ft-layers" value="5" min="2" max="10" size="4"></label>
      <label>调仓间隔(日) <input type="number" id="ft-rebalance" value="1" min="1" max="60" size="4"></label>
      <label>成本率 <input type="number" id="ft-cost" value="0.003" step="0.001" min="0" size="6"></label>
      <button class="btn-primary" id="ft-submit">提交检验</button>
    </div>
    <div class="form-hint hidden" id="ft-hint"></div>
  </div>
</details>
<div id="ft-job-area"></div>
```

`#refresh-form-slot`：

```html
<details class="form-card" id="dr-form">
  <summary>刷新市场数据（需 QMT 客户端在线）</summary>
  <div class="form-body">
    <div class="form-row">
      <label>起 <input type="date" id="dr-start" value="2021-01-01"></label>
      <label>止 <input type="date" id="dr-end" value="2025-12-31"></label>
      <button class="btn-primary" id="dr-submit">开始刷新</button>
      <span class="form-hint">只补缺口；刷新期间持 DuckDB 写锁，查询暂不可用。</span>
    </div>
  </div>
</details>
<div id="dr-job-area"></div>
```

- [ ] **Step 2: verdicts.js 追加**

```javascript
import { submitJob, attachJobCard } from "../jobs.js";

export async function initFactorForm() {
  const data = await fetchJSON("/api/meta/factors");
  const byId = Object.fromEntries(data.factors.map((f) => [f.factor_id, f]));
  const html = [];
  for (const [group, ids] of Object.entries(data.groups)) {
    html.push(`<span class="group-title">${group}</span>`);
    for (const id of ids) {
      const f = byId[id];
      const dis = f.field_ready === false;
      html.push(`<label class="${dis ? "disabled" : ""}"
        title="${f.expression}${dis ? "（数据管道缺字段，禁用）" : ""}">
        <input type="checkbox" value="${id}" ${dis ? "disabled" : ""}
               ${group === "P0" && !dis ? "checked" : ""}>${id} ${f.name}</label>`);
    }
  }
  $("#ft-factors").innerHTML = html.join("");
  $("#ft-factors").addEventListener("change", updateFtHint);
  $("#ft-split").addEventListener("change", updateFtHint);
  $("#ft-submit").addEventListener("click", submitFactorTest);
  updateFtHint();
}

function ftSelected() {
  return [...document.querySelectorAll("#ft-factors input:checked")].map((c) => c.value);
}

function updateFtHint() {
  const many = ftSelected().length > 1;
  const noSplit = !$("#ft-split").value;
  const show = many && noSplit;
  $("#ft-hint").classList.toggle("hidden", !show);
  if (show) $("#ft-hint").textContent =
    "多因子批量检验未设 IS/OOS 切分——存在多重检验风险，建议保留切分日期。";
}

async function submitFactorTest() {
  clearError();
  const ids = ftSelected();
  if (!ids.length) { showError("至少勾选一个因子"); return; }
  const payload = {
    factors: ids.join(","),
    start_date: $("#ft-start").value,
    end_date: $("#ft-end").value,
    objective: $("#ft-objective").value,
    num_layers: Number($("#ft-layers").value),
    rebalance_days: Number($("#ft-rebalance").value),
    cost_rate: Number($("#ft-cost").value),
  };
  if ($("#ft-split").value) payload.split_date = $("#ft-split").value;
  try {
    const job = await submitJob("factor-test", payload);
    attachJobCard($("#ft-job-area"), job.job_id, {
      onDone: () => loadVerdicts().catch((e) => showError(e.message)),
    });
  } catch (err) {
    showError(err.message);
  }
}
```

- [ ] **Step 3: overview.js 追加**

```javascript
import { submitJob, attachJobCard } from "../jobs.js";

export function initRefreshForm() {
  $("#dr-submit").addEventListener("click", async () => {
    clearError();
    try {
      const job = await submitJob("data-refresh", {
        start_date: $("#dr-start").value, end_date: $("#dr-end").value });
      attachJobCard($("#dr-job-area"), job.job_id, {
        onDone: () => loadOverview().catch((e) => showError(e.message)),
      });
    } catch (err) {
      showError(err.message);
    }
  });
}
```

main.js init 追加 `initFactorForm().catch(() => {})` 与 `initRefreshForm()`。

- [ ] **Step 4: 冒烟 + 提交**

TestClient 断言 index.html 含 `ft-form`/`dr-form`。浏览器验证：F10 置灰、多因子+清空切分日出现提示、提交后任务卡滚动日志。

```bash
git add src/interfaces/api/static/
git commit -m "feat(ui): 因子检验与数据刷新表单 — 目录驱动勾选/多重检验提示/QMT标注"
```

---

### Task 12: 前端 — 实盘页扩展

**Files:**
- Modify: `static/index.html`、`static/js/pages/live.js`

- [ ] **Step 1: index.html 实盘页扩展结构**

`#live-ext-slot` 替换为：

```html
<h3 class="section-title">审计日志
  <select id="audit-action" style="margin-left:8px">
    <option value="">全部动作</option>
    <option>cycle_start</option><option>cycle_end</option>
    <option>place_order</option><option>reject_order</option>
    <option>place_order_failed</option><option>execute_failed</option>
    <option>cancel_order</option>
  </select>
</h3>
<table id="live-audit" class="verdict-table">
  <thead><tr><th>时间</th><th>动作</th><th>资源</th><th>明细</th></tr></thead>
  <tbody></tbody>
</table>
<h3 class="section-title">单笔下单 Ticket（data/trade_logs）</h3>
<div id="live-tickets"></div>
```

`#live-cards` 后已有 `#live-ops-cards`；持仓标题行加 mode 筛选：

```html
<h3 class="section-title">当前持仓 <span id="live-pos-time" class="run-params"></span>
  <select id="live-mode" style="margin-left:8px">
    <option value="">全部模式</option>
    <option value="dry_run">纸面 dry_run</option>
    <option value="live">实盘 live</option>
  </select>
</h3>
```

- [ ] **Step 2: live.js 扩展**

```javascript
// loadLive() 的 Promise.all 增加三路, 并把 mode 传给 positions/equity:
const mode = $("#live-mode")?.value || "";
const modeQ = mode ? `?mode=${mode}` : "";
const [ov, cyc, exe, pos, eq, budget, cfg, audit, tickets] = await Promise.all([
  fetchJSON("/api/live/overview"),
  fetchJSON("/api/live/cycles"),
  fetchJSON("/api/live/executions"),
  fetchJSON(`/api/live/positions${modeQ}`),
  fetchJSON(`/api/live/equity${modeQ}`),
  fetchJSON("/api/live/budget"),
  fetchJSON("/api/live/config"),
  fetchJSON(`/api/live/audit?limit=50${$("#audit-action").value ? `&action=${$("#audit-action").value}` : ""}`),
  fetchJSON("/api/live/tickets"),
]);

// 运维卡: 预算 + 守护活性 + 配置
function daemonBadge(cfg) {
  const slots = cfg.today.expected_slots || [];
  const now = new Date().toTimeString().slice(0, 5);
  const due = slots.filter((s) => s <= now).length;
  const n = cfg.today.cycles_today;
  if (!slots.length) return `<span class="badge info">未配置槽位</span>`;
  if (n >= due && due > 0) return `<span class="badge pass">槽位已覆盖 ${n}/${due}</span>`;
  if (due === 0) return `<span class="badge info">今日未到执行时刻</span>`;
  return `<span class="badge warn">槽位缺口 ${n}/${due} — 守护可能未运行</span>`;
}

$("#live-ops-cards").innerHTML = `
  <div class="card"><h3>今日预算</h3>
    <div class="big">${num(budget.submitted_notional)}</div>
    <div class="dim">上限 ${num(budget.daily_notional_cap)} · 余 ${num(budget.remaining)}
      · 单笔顶 ${num(budget.per_order_notional_cap)}</div></div>
  <div class="card"><h3>守护状态</h3>
    <div class="big" style="font-size:18px">${daemonBadge(cfg)}</div>
    <div class="dim">执行槽位 ${(cfg.today.expected_slots || []).join(" / ") || "-"}</div></div>
  <div class="card"><h3>auto-trade 配置（只读）</h3>
    <div class="big" style="font-size:16px">
      <span class="badge ${cfg.auto_trade.mode === "live" ? "fail" : "info"}">${cfg.auto_trade.mode || "?"}</span>
      <span class="badge ${cfg.auto_trade.enabled ? "warn" : "info"}">${cfg.auto_trade.enabled ? "enabled" : "disabled"}</span>
    </div>
    <div class="dim">${cfg.auto_trade.strategy || ""} · ${(cfg.auto_trade.symbols || []).length} 标的
      · 置信≥${cfg.auto_trade.min_confidence ?? "?"}</div></div>`;

// 审计表
$("#live-audit tbody").innerHTML = audit.logs.map((r) => `
  <tr><td>${(r.timestamp || "").slice(0, 19)}</td><td>${r.action}</td>
      <td>${r.resource_type || ""}:${r.resource_id || ""}</td>
      <td style="text-align:left"><code>${(r.details || "").slice(0, 120)}</code></td></tr>`
).join("") || `<tr><td colspan="4" class="gate-na">暂无审计记录</td></tr>`;

// 循环行点击钻取（替换原 live-cycles 渲染, 行加 class clickable + data-cycle）
// 行模板增加: <tr class="clickable" data-cycle="${c.cycle_id}">…
$("#live-cycles tbody").querySelectorAll("tr.clickable").forEach((tr) => {
  tr.addEventListener("click", async () => {
    const next = tr.nextElementSibling;
    if (next && next.classList.contains("row-detail")) { next.remove(); return; }
    const d = await fetchJSON(`/api/live/cycles/${tr.dataset.cycle}/executions`);
    const rows = d.executions.map((e) =>
      `<tr><td>${e.symbol}</td><td>${e.direction}</td><td>${e.status}</td>
           <td>${num(e.notional)}</td><td>${e.reject_reason || ""}</td></tr>`).join("")
      || `<tr><td colspan="5">该循环无执行记录</td></tr>`;
    tr.insertAdjacentHTML("afterend",
      `<tr class="row-detail"><td colspan="9"><table>${rows}</table></td></tr>`);
  });
});

// tickets
$("#live-tickets").innerHTML = tickets.tickets.map((t) => `
  <details class="ticket-item"><summary>${t.file}</summary>
    <pre class="ticket-pre">${JSON.stringify(t.content, null, 2)}</pre></details>`
).join("") || `<p class="empty">暂无 ticket</p>`;

// 监听（initLive 注册一次）: #live-mode 与 #audit-action change → loadLive()
```

实现要点：把上述逻辑融进现有 `loadLive()`（一次 Promise.all 全取），监听注册放新导出 `initLive()`（main.js init 调用，注意防重复注册——监听挂在 select 上仅一次）。

- [ ] **Step 3: 冒烟 + 提交**

TestClient 断言 index.html 含 `live-audit`/`live-mode`。浏览器验证空库显式空态不报错（trading.db 5 表 0 行是当前现实）。

```bash
git add src/interfaces/api/static/
git commit -m "feat(ui): 实盘页扩展 — 预算/守护活性/配置卡+审计日志+循环钻取+mode筛选+ticket"
```

---

### Task 13: 前端 — 任务页 + ML 表单 + 全局收尾

**Files:**
- Modify: `static/index.html`、`static/js/jobs.js`、`static/js/main.js`

- [ ] **Step 1: ML 表单（`#ml-forms-slot`）**

```html
<details class="form-card">
  <summary>ML 模型训练 / 评估（高级）</summary>
  <div class="form-body">
    <div class="form-row">
      <label>训练起 <input type="date" id="ml-start" value="2021-01-01"></label>
      <label>训练止 <input type="date" id="ml-end" value="2024-12-31"></label>
      <label>标的 <input id="ml-symbols" value="000300.SH" size="12"></label>
      <label>模型名 <input id="ml-model" value="lgbm_return_5d" size="14"></label>
      <label>n-trials <input type="number" id="ml-trials" value="50" min="1" max="200" size="5"></label>
      <button class="btn-primary" id="ml-train-submit">训练</button>
    </div>
    <div class="form-row">
      <label>评估起 <input type="date" id="mle-start" value="2025-01-01"></label>
      <label>评估止 <input type="date" id="mle-end" value="2025-12-31"></label>
      <button class="btn-primary" id="ml-eval-submit">评估</button>
    </div>
  </div>
</details>
<div id="ml-job-area"></div>
```

- [ ] **Step 2: jobs.js 追加任务页渲染**

```javascript
export async function loadJobsPage() {
  const data = await fetchJSON("/api/jobs?limit=100");
  $("#jobs-empty").classList.toggle("hidden", data.jobs.length > 0);
  $("#jobs-table tbody").innerHTML = data.jobs.map((j) => `
    <tr class="clickable" data-job="${j.job_id}">
      <td><code>${j.job_id}</code></td><td>${j.job_type}</td>
      <td style="text-align:left">${paramsSummary(j)}</td>
      <td><span class="badge ${j.status}">${STATUS_LABEL[j.status] || j.status}</span></td>
      <td>${(j.created_at || "").slice(5, 19)}</td>
      <td>${durationOf(j)}</td>
      <td>${["queued", "running"].includes(j.status)
            ? `<button class="btn-danger" data-cancel="${j.job_id}">取消</button>` : ""}</td>
    </tr>`).join("");
  $("#jobs-table tbody").querySelectorAll("[data-cancel]").forEach((btn) =>
    btn.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      try { await postJSON(`/api/jobs/${btn.dataset.cancel}/cancel`); } catch { }
      loadJobsPage();
    }));
  $("#jobs-table tbody").querySelectorAll("tr.clickable").forEach((tr) =>
    tr.addEventListener("click", () => showJobLog(tr.dataset.job)));
}

let logTimer = null;

async function showJobLog(jobId) {
  clearInterval(logTimer);
  async function tick() {
    const job = await fetchJSON(`/api/jobs/${jobId}?tail=300`);
    $("#job-log-title").textContent = `${jobId} · ${job.status}`;
    $("#job-log").textContent = (job.log_tail || []).join("\n") || "（无输出）";
    $("#job-log").scrollTop = $("#job-log").scrollHeight;
    if (["succeeded", "failed", "canceled"].includes(job.status)) clearInterval(logTimer);
  }
  await tick();
  logTimer = setInterval(tick, 2000);
}

export function initMlForms() {
  $("#ml-train-submit").addEventListener("click", async () => {
    try {
      const job = await submitJob("ml-train", {
        start_date: $("#ml-start").value, end_date: $("#ml-end").value,
        symbols: $("#ml-symbols").value.trim(),
        model_name: $("#ml-model").value.trim(),
        n_trials: Number($("#ml-trials").value),
      });
      attachJobCard($("#ml-job-area"), job.job_id, { onDone: loadJobsPage });
    } catch (err) { showError(err.message); }
  });
  $("#ml-eval-submit").addEventListener("click", async () => {
    try {
      const job = await submitJob("ml-evaluate", {
        model_name: $("#ml-model").value.trim(),
        eval_start: $("#mle-start").value, eval_end: $("#mle-end").value,
      });
      attachJobCard($("#ml-job-area"), job.job_id, { onDone: loadJobsPage });
    } catch (err) { showError(err.message); }
  });
}
```

（`showError` 需在 jobs.js 顶部 import；`STATUS_LABEL`/`durationOf` 已在本文件。）

- [ ] **Step 3: main.js 接线**

- import `{ loadJobsPage, initMlForms }`；
- 页签 click 处理加：`if (btn.dataset.tab === "jobs") loadJobsPage().catch((e) => showError(e.message));`
- init 里调 `initMlForms()`；
- `pollIndicator` 保留（已是全局 5s）。

- [ ] **Step 4: 全站冒烟 + 提交**

```bash
$WIN_PYTHON -c "
from fastapi.testclient import TestClient
from src.interfaces.api.app import app
c = TestClient(app)
assert c.get('/health').json()['status'] == 'ok'
html = c.get('/ui/').text
for marker in ['bt-form','ft-form','dr-form','jobs-table','ml-train-submit','job-indicator']:
    assert marker in html, marker
for js in ['main','api','charts','jobs','pages/overview','pages/verdicts',
           'pages/explorer','pages/backtests','pages/live']:
    assert c.get(f'/ui/js/{js}.js').status_code == 200, js
assert c.get('/api/meta/strategies').status_code == 200
assert c.get('/api/jobs').status_code == 200
print('full static smoke OK')
"
git add src/interfaces/api/static/
git commit -m "feat(ui): 任务中心页 — 列表/日志查看/取消 + ML 训练评估表单"
```

---

### Task 14: 端到端验证 + 文档收尾

- [ ] **Step 1: 真任务端到端（一次最小回测走通全链路）**

```bash
$WIN_PYTHON -c "
import time
from fastapi.testclient import TestClient
from src.interfaces.api.app import app
c = TestClient(app)
resp = c.post('/api/jobs/backtest', json={
    'strategies': ['dual_ma'], 'symbols': ['000021.SZ'],
    'start_date': '2024-01-01', 'end_date': '2024-03-31'})
assert resp.status_code == 202, resp.text
jid = resp.json()['job_id']
for _ in range(120):
    d = c.get(f'/api/jobs/{jid}?tail=50').json()
    if d['status'] in ('succeeded', 'failed', 'canceled'):
        break
    time.sleep(2)
print(d['status'], chr(10).join(d.get('log_tail', [])[-15:]))
assert d['status'] == 'succeeded', '子进程回测失败, 看上方日志'
runs = c.get('/api/research/backtests').json()['runs']
assert runs and any(s['strategy'] == 'dual_ma' for s in runs[0]['strategies'])
print('E2E OK — 新 run:', runs[0]['run_id'])
"
```
注意：此步会真实写 market.duckdb 的 backtest_runs（这正是验证目标）；若当时 DuckDB 被其它进程写锁占用会失败，重跑即可。

- [ ] **Step 2: 全量测试 + lint**

```bash
$WIN_PYTHON -m pytest tests/ --ignore=tests/infrastructure/gateway/ --basetemp=.pytest_tmp -q
ruff check src/
```
Expected: 全 passed / All checks passed

- [ ] **Step 3: 文档更新**

- `CLAUDE.md` dashboard 一行说明改为：`# 投研驾驶舱（http://127.0.0.1:8501/ui/, 可交互: 网页内直接跑回测/因子检验/数据刷新/ML, 任务页看日志）`
- `.gitignore` 确认 `data/` 已覆盖 `data/job_logs/`（若 data/ 未整体忽略则补一行 `data/job_logs/`）。**注意 .gitignore 有他人未提交改动，只追加不重排。**
- 设计文档底部追加一行实施完成记录（日期 + 提交范围）。

- [ ] **Step 4: 浏览器人工冒烟清单（Windows 侧执行后勾选）**

```
$WIN_PYTHON -m src.interfaces.cli.quant dashboard
```
- [ ] 五个旧页签数据与改前一致
- [ ] 回测表单提交 dual_ma 小区间 → 任务卡日志滚动 → 完成自动刷新列表
- [ ] 因子表单 F10 置灰; 多选+无切分出现黄色提示
- [ ] 任务页能看历史任务日志、取消排队任务
- [ ] 实盘页空库显式空态、预算/守护/配置卡正常渲染
- [ ] header 任务指示灯随活跃任务出现/消失

- [ ] **Step 5: 收尾提交**

```bash
git add CLAUDE.md .gitignore docs/feat/0612-interactive-dashboard/
git commit -m "docs: 交互式驾驶舱收尾 — CLAUDE.md/设计文档实施记录"
```

---

## Self-Review 结论

- 设计 §3.1-3.5 每节均有对应 Task（3.1→T1, 3.2→T2/T3, 3.3→T4, 3.4→T5/T6, 3.5→T9-T13, DD-5→T8, DD-7→T7）；
- 类型/命名跨任务一致：`JobStatus.value` 小写串 ↔ 前端 badge class ↔ 测试断言；`get_trading_config_path`/`get_trade_logs_dir` 在 T5 定义、T5/T6 测试 override；
- 无 TBD/占位；前端搬运步骤给出函数级映射表，新增代码全量给出。
