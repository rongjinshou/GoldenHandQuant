from fastapi import FastAPI

from src.interfaces.api.routes import account_routes, backtest_routes

app = FastAPI(title="QuantFlow API", version="0.1.0")
app.include_router(backtest_routes.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(account_routes.router, prefix="/api/account", tags=["account"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
