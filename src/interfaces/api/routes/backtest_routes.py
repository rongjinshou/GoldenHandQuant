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
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _run_status[run_id] = {"status": "pending", "progress": 0}
    try:
        _run_status[run_id] = {"status": "running", "progress": 0}
        _run_status[run_id] = {"status": "completed", "progress": 100}
        return BacktestRunResponse(run_id=run_id, status="completed", message="Backtest finished")
    except Exception as e:
        _run_status[run_id] = {"status": "failed", "error": str(e)}
        raise HTTPException(status_code=500, detail=str(e))


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
