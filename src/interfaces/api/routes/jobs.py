"""任务路由 — Web 触发研究侧 CLI（回测/因子/数据刷新/ML）。

只读交易红线（设计 DD-4）: 此处永不出现下单/撤单/auto-trade/trading.yaml 写操作。
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

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

# 单进程假设: dashboard 以 uvicorn 单 worker 绑 127.0.0.1 运行;
# workers>1 会出现每进程独立注册表 + 多个 DuckDB 写者, 违反设计 DD-1。
_manager: JobManager | None = None
_manager_lock = threading.Lock()


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        with _manager_lock:  # 首请求并发进线程池时防双重构造
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
def list_jobs(limit: int = Query(default=50, ge=1, le=200),
              manager: JobManager = Depends(get_job_manager)) -> dict:
    jobs = manager.list_jobs()[:limit]
    return {"jobs": [j.to_dict() for j in jobs], "active": manager.has_active()}


@router.get("/{job_id}")
def job_detail(job_id: str, tail: int = Query(default=200, ge=0, le=400),
               manager: JobManager = Depends(get_job_manager)) -> dict:
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
    return job.to_dict(tail=tail)


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
