from fastapi import APIRouter, Depends

from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway

router = APIRouter()


def get_account_gateway() -> IAccountGateway:
    from src.infrastructure.mock.mock_market import MockMarketGateway
    from src.infrastructure.mock.mock_trade import MockTradeGateway

    return MockTradeGateway(MockMarketGateway())


@router.get("/asset")
async def get_asset(gateway: IAccountGateway = Depends(get_account_gateway)):
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
async def get_positions(gateway: IAccountGateway = Depends(get_account_gateway)):
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
