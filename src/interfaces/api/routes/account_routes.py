import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException

from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway

router = APIRouter()

API_TOKEN = os.environ.get("DASHBOARD_API_TOKEN", "")


def _verify_auth(authorization: str = Header(default="")) -> None:
    """验证 Bearer token。"""
    token = authorization.removeprefix("Bearer ").strip()
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="DASHBOARD_API_TOKEN not configured")
    if not hmac.compare_digest(token, API_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_account_gateway() -> IAccountGateway:
    from src.infrastructure.mock.mock_market import MockMarketGateway
    from src.infrastructure.mock.mock_trade import MockTradeGateway

    return MockTradeGateway(MockMarketGateway())


@router.get("/asset")
async def get_asset(
    _auth: None = Depends(_verify_auth),
    gateway: IAccountGateway = Depends(get_account_gateway),
):
    asset = gateway.get_asset()
    if asset is None:
        return {"error": "Asset not found"}
    return {
        "account_id": asset.account_id,
        "total_asset": asset.total_asset,
        "available_cash": asset.available_cash,
        "frozen_cash": asset.frozen_cash,
    }


@router.get("/positions")
async def get_positions(
    _auth: None = Depends(_verify_auth),
    gateway: IAccountGateway = Depends(get_account_gateway),
):
    positions = gateway.get_positions()
    return [
        {
            "ticker": p.ticker,
            "total_volume": p.total_volume,
            "available_volume": p.available_volume,
            "average_cost": p.average_cost,
            "cost_basis": p.average_cost * p.total_volume,
        }
        for p in positions
    ]
