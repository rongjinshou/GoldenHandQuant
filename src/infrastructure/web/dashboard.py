import json
import logging
import queue
from dataclasses import asdict
from datetime import datetime

from src.application.anomaly_detector import AnomalyDetector
from src.application.auto_pause_manager import AutoPauseManager
from src.domain.trade.services.execution_monitor import ExecutionMonitor
from src.infrastructure.web.auth import TokenAuth

logger = logging.getLogger(__name__)


class WebDashboard:
    """Web Dashboard 应用。

    基于 FastAPI 的轻量 Web Dashboard，提供状态查询、控制操作和 SSE 实时事件。
    """

    def __init__(
        self,
        execution_monitor: ExecutionMonitor | None = None,
        anomaly_detector: AnomalyDetector | None = None,
        pause_manager: AutoPauseManager | None = None,
        auth: TokenAuth | None = None,
    ) -> None:
        self._execution_monitor = execution_monitor
        self._anomaly_detector = anomaly_detector
        self._pause_manager = pause_manager
        self._auth = auth
        self._event_queues: list[queue.Queue] = []

    def get_status(self) -> dict:
        """获取系统状态。"""
        # AutoTradingEngine 已归档(0628 R3a), 自动交易状态改由 TradingStore/auto_trade 守护体现
        engine_running = False
        all_paused = self._pause_manager.is_all_paused if self._pause_manager else False

        return {
            "status": "paused" if all_paused else ("running" if engine_running else "stopped"),
            "engine_running": engine_running,
            "all_paused": all_paused,
            "timestamp": datetime.now().isoformat(),
        }

    def get_stats(self) -> dict:
        """获取执行统计。"""
        if not self._execution_monitor:
            return {"error": "ExecutionMonitor not available"}
        stats = self._execution_monitor.get_stats()
        return asdict(stats)

    def get_health(self) -> dict:
        """获取健康状态。"""
        if not self._execution_monitor:
            return {"health": "unknown"}
        health = self._execution_monitor.check_health()
        return {"health": health.value}

    def pause(self, token: str) -> dict:
        """暂停交易。"""
        if self._auth and not self._auth.verify(token):
            return {"error": "Unauthorized"}
        if not self._pause_manager:
            return {"error": "PauseManager not available"}
        from src.domain.risk.value_objects.anomaly_event import (
            AnomalyEvent,
            AnomalySeverity,
            AnomalyType,
            AutoAction,
        )
        event = AnomalyEvent(
            anomaly_type=AnomalyType.STRATEGY,
            severity=AnomalySeverity.CRITICAL,
            source="manual",
            message="手动暂停交易",
            metric_value=0.0,
            threshold=0.0,
            auto_action=AutoAction.PAUSE_ALL,
        )
        self._pause_manager.pause_all(event)
        self._push_event("pause", {"reason": "手动暂停"})
        return {"status": "paused"}

    def resume(self, token: str) -> dict:
        """恢复交易。"""
        if self._auth and not self._auth.verify(token):
            return {"error": "Unauthorized"}
        if not self._pause_manager:
            return {"error": "PauseManager not available"}
        self._pause_manager.resume_all(operator="web")
        self._push_event("resume", {"operator": "web"})
        return {"status": "resumed"}

    def add_event_queue(self, maxsize: int = 256) -> queue.Queue:
        """添加 SSE 事件队列。"""
        q: queue.Queue = queue.Queue(maxsize=maxsize)
        self._event_queues.append(q)
        return q

    def remove_event_queue(self, q: queue.Queue) -> None:
        """移除 SSE 事件队列。"""
        if q in self._event_queues:
            self._event_queues.remove(q)

    def _push_event(self, event_type: str, data: dict) -> None:
        """推送事件到所有 SSE 客户端。"""
        event_data = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
        for q in self._event_queues:
            try:
                q.put_nowait(event_data)
            except queue.Full:
                pass


def create_app(dashboard: WebDashboard) -> object:
    """创建 FastAPI 应用。

    需要安装 fastapi 和 uvicorn。
    """
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException, Request
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import StreamingResponse
    except ImportError:
        raise ImportError(
            "FastAPI is required for Web Dashboard. "
            "Install with: pip install fastapi uvicorn"
        )

    app = FastAPI(title="GoldenHandQuant Dashboard")

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # 安全头中间件
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    def _verify_auth(authorization: str = Header(default="")) -> str:
        """验证 Bearer token，返回有效 token 或抛出 401。"""
        token = authorization.removeprefix("Bearer ").strip()
        if not dashboard._auth:
            raise HTTPException(status_code=503, detail="Auth not configured")
        if not dashboard._auth.verify(token):
            raise HTTPException(status_code=401, detail="Unauthorized")
        return token

    @app.get("/api/status")
    async def api_status(_token: str = Depends(_verify_auth)):
        return dashboard.get_status()

    @app.get("/api/stats")
    async def api_stats(_token: str = Depends(_verify_auth)):
        return dashboard.get_stats()

    @app.get("/api/health")
    async def api_health(_token: str = Depends(_verify_auth)):
        return dashboard.get_health()

    @app.post("/api/control/pause")
    async def api_pause(token: str = Depends(_verify_auth)):
        result = dashboard.pause(token)
        if "error" in result:
            raise HTTPException(status_code=401, detail=result["error"])
        return result

    @app.post("/api/control/resume")
    async def api_resume(token: str = Depends(_verify_auth)):
        result = dashboard.resume(token)
        if "error" in result:
            raise HTTPException(status_code=401, detail=result["error"])
        return result

    @app.get("/api/events")
    async def api_events(_token: str = Depends(_verify_auth)):
        q = dashboard.add_event_queue()

        async def event_stream():
            try:
                while True:
                    try:
                        event = q.get(timeout=30)
                        yield f"data: {json.dumps(event)}\n\n"
                    except queue.Empty:
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            finally:
                dashboard.remove_event_queue(q)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    return app
