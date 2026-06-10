from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.interfaces.api.routes import account_routes, backtest_routes, dashboard, research

app = FastAPI(title="GoldenHandQuant API", version="0.1.0")
app.include_router(backtest_routes.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(account_routes.router, prefix="/api/account", tags=["account"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(research.router, prefix="/api/research", tags=["research"])

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/ui", StaticFiles(directory=str(_STATIC_DIR), html=True), name="ui")


@app.get("/", include_in_schema=False)
async def index_redirect():
    return RedirectResponse(url="/ui/", status_code=302)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
