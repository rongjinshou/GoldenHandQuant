"""Dry-run 交易网关 — 读真实账户/持仓, 下单只记录不触达 QMT (纸面前向载体)。

设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md DD-2
"""

from __future__ import annotations

import logging
import uuid

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.trade.entities.order import Order

logger = logging.getLogger(__name__)


class DryRunTradeGateway:
    """包装真实网关: 读操作透传, 写操作模拟。状态 DRY_RUN 为终态。

    单号用 uuid 而非进程内计数器: execution_records 以 order_id 为主键,
    计数器在进程重启后从头计数会静默覆盖历史留痕。
    """

    is_dry_run = True  # 装配一致性校验用 (mode 必须与网关真实性配对)

    def __init__(self, real_gateway) -> None:
        self._real = real_gateway

    def place_order(self, order: Order) -> str:
        order_id = f"dry-{uuid.uuid4().hex[:10]}"
        logger.info(
            "[DRY-RUN] 模拟下单 %s: %s %s %d股 @ %.2f",
            order_id, order.ticker, order.direction.value, order.volume, order.price,
        )
        return order_id

    def query_order_status(self, order_id: str) -> str | None:
        return "DRY_RUN"

    def cancel_order(self, order_id: str) -> bool:
        return True

    def get_asset(self) -> Asset | None:
        return self._real.get_asset()

    def get_positions(self) -> list[Position]:
        return self._real.get_positions()
