"""订单状态轮询 — 共享 helper。

解决债 D1: ticket 手动下单与 auto-trade 自动循环各写一套超时轮询逻辑,
行为已分叉(前者不撤单/后者撤单)。抽取共享 helper, 通过 cancel_on_timeout
参数控制超时行为。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

TERMINAL_STATES = ("FILLED", "CANCELED", "REJECTED", "DRY_RUN")


@dataclass(slots=True, kw_only=True)
class PollResult:
    """轮询结果。"""
    final_status: str
    trail: list[dict]
    canceled: bool = False  # 是否执行了撤单


def poll_order_until_terminal(
    order_id: str,
    *,
    query_status: Callable[[str], str | None],
    cancel_order: Callable[[str], bool] | None = None,
    timeout_seconds: float = 30.0,
    poll_interval: float = 2.0,
    clock: Callable[[], float] | None = None,
    sleep: Callable[[float], None] | None = None,
    cancel_on_timeout: bool = False,
) -> PollResult:
    """轮询订单状态至终态或超时。

    Args:
        order_id: 订单 ID。
        query_status: 查询订单状态的回调。
        cancel_order: 撤单回调(仅 cancel_on_timeout=True 时需要)。
        timeout_seconds: 超时秒数。
        poll_interval: 轮询间隔秒数。
        clock: 时钟回调(返回 epoch 秒数)。
        sleep: 休眠回调。
        cancel_on_timeout: 超时后是否尝试撤单。
            - ticket 手动下单: False (不撤单, 用户自行处理)
            - auto-trade 自动循环: True (撤单, 避免收盘前意外敞口)

    Returns:
        PollResult 包含终态、状态轨迹和是否执行了撤单。
    """
    import time as _time

    _clock = clock or (lambda: _time.time())
    _sleep = sleep or _time.sleep

    trail: list[dict] = []
    deadline = _clock() + timeout_seconds
    last_state: str | None = None

    while _clock() < deadline:
        state = query_status(order_id)
        if state and state != last_state:
            trail.append({"t": _clock(), "status": state})
            last_state = state
        if state in TERMINAL_STATES:
            return PollResult(final_status=state, trail=trail)
        _sleep(poll_interval)

    # 超时
    if cancel_on_timeout and cancel_order is not None:
        if cancel_order(order_id):
            logger.info("订单 %s 超时已撤单", order_id)
            return PollResult(
                final_status="TIMEOUT_CANCELED", trail=trail, canceled=True,
            )
        logger.error("订单 %s 超时且撤单未受理, 需人工处理!", order_id)
        return PollResult(
            final_status="TIMEOUT_UNCANCELED", trail=trail, canceled=False,
        )

    return PollResult(final_status=last_state or "TIMEOUT", trail=trail)
