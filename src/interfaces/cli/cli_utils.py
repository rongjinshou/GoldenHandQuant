"""CLI 数据接口公共工具模块。

提供统一 JSON 输出、超时控制、QMT 连接检测等公共功能。
所有 fetcher CLI 命令复用此模块。
"""

import json
import platform
import signal
import sys
import threading
from datetime import datetime

TIMEOUT_SECONDS = 30

_is_windows = platform.system() == "Windows"
_timer: threading.Timer | None = None


def _timeout_handler(signum: int, frame: object) -> None:
    raise TimeoutError(f"请求超时 ({TIMEOUT_SECONDS}s)")


def _timeout_handler_windows() -> None:
    """Windows 超时处理：通过 ctypes 注入异常到主线程。"""
    import ctypes
    tid = threading.main_thread().ident
    if tid is not None:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(tid),
            ctypes.py_object(TimeoutError),
        )


def setup_timeout(seconds: int = TIMEOUT_SECONDS) -> None:
    """设置超时。WSL/Linux 使用 signal.SIGALRM，Windows 使用 threading.Timer。"""
    global _timer
    if _is_windows:
        _timer = threading.Timer(seconds, _timeout_handler_windows)
        _timer.daemon = True
        _timer.start()
    else:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(seconds)


def cancel_timeout() -> None:
    """取消超时。"""
    global _timer
    if _is_windows:
        if _timer is not None:
            _timer.cancel()
            _timer = None
    else:
        signal.alarm(0)


def output_json(data: dict) -> None:
    """统一 JSON 输出到 stdout。"""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def output_error(message: str) -> None:
    """统一错误输出到 stderr，并输出 JSON 错误到 stdout。"""
    print(f"ERROR: {message}", file=sys.stderr)
    output_json({
        "success": False,
        "data": None,
        "error": message,
        "timestamp": datetime.now().astimezone().isoformat(),
    })


def output_success(data: dict) -> None:
    """封装 success 信封输出。"""
    output_json({
        "success": True,
        "data": data,
        "error": None,
        "timestamp": datetime.now().astimezone().isoformat(),
    })


def check_qmt_connection() -> bool:
    """检测 QMT 客户端是否可用。

    通过尝试获取一个已知标的的详情来检测连接。
    """
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata
        detail = xtdata.get_instrument_detail("000001.SZ")
        return detail is not None and len(detail) > 0
    except Exception:
        return False
