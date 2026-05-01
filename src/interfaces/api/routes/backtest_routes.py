from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class BacktestRunRequest(BaseModel):
    symbols: list[str] = ["000021.SZ"]
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"
    strategy_names: list[str] = ["DualMaStrategy"]


class BacktestRunResponse(BaseModel):
    run_id: str
    status: str
    message: str


_run_status: dict[str, dict] = {}


@router.post("/run", response_model=BacktestRunResponse)
async def trigger_backtest(request: BacktestRunRequest):
    """触发回测运行（暂未实现，请使用 CLI: python -m src.interfaces.cli.run_backtest）。"""
    raise HTTPException(
        status_code=501,
        detail="Backtest execution not yet implemented. Use CLI: python -m src.interfaces.cli.run_backtest",
    )


@router.get("/status/{run_id}")
async def get_backtest_status(run_id: str):
    if run_id not in _run_status:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return _run_status[run_id]


@router.get("/report/{run_id}")
async def get_backtest_report(run_id: str):
    if run_id not in _run_status:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    if _run_status[run_id]["status"] != "completed":
        raise HTTPException(status_code=400, detail="Backtest not yet completed")
    return {"run_id": run_id, "report": {"message": "Report placeholder"}}
