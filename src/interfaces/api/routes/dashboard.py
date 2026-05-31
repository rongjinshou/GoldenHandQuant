import hmac
import os
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect

from src.application.dashboard_app import DashboardAppService

router = APIRouter()

API_TOKEN = os.environ.get("DASHBOARD_API_TOKEN", "")

# 模块级 DashboardAppService 实例（由 app 启动时注入）
_dashboard_service: DashboardAppService | None = None


def set_dashboard_service(service: DashboardAppService) -> None:
    """注入 Dashboard 应用服务实例。"""
    global _dashboard_service
    _dashboard_service = service


def get_dashboard_service() -> DashboardAppService:
    if _dashboard_service is None:
        raise HTTPException(status_code=503, detail="Dashboard service not initialized")
    return _dashboard_service


def _verify_auth(authorization: str = Header(default="")) -> None:
    """验证 Bearer token。"""
    token = authorization.removeprefix("Bearer ").strip()
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="DASHBOARD_API_TOKEN not configured")
    if not hmac.compare_digest(token, API_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---- REST API 端点 ----


@router.get("/snapshot")
async def get_snapshot(
    _auth: None = Depends(_verify_auth),
    service: DashboardAppService = Depends(get_dashboard_service),
):
    """获取当前 Dashboard 快照。"""
    snapshot = service.collect_snapshot()
    from src.application.dashboard_app import _snapshot_to_dict
    return _snapshot_to_dict(snapshot)


@router.get("/equity-curve")
async def get_equity_curve(
    limit: int = 252,
    _auth: None = Depends(_verify_auth),
    service: DashboardAppService = Depends(get_dashboard_service),
):
    """获取收益曲线数据。"""
    return service.get_equity_curve(limit)


# ---- WebSocket 端点 ----


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str | None = None):
    """WebSocket 实时数据推送端点。

    连接后自动接收定时推送的 Dashboard 快照数据。
    """
    service = get_dashboard_service()
    ws_manager = service._ws_manager

    resolved_id = client_id or str(uuid.uuid4())
    await ws_manager.connect(resolved_id, websocket)

    try:
        while True:
            # 保持连接，接收客户端消息（如 ping）
            data = await websocket.receive_text()
            if data == "ping":
                await ws_manager.send_personal(resolved_id, {"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(resolved_id)
    except Exception:
        ws_manager.disconnect(resolved_id)
