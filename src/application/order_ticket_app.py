"""单笔下单编排服务 — 五道安全闸 + 限价单 + 状态轮询。

受控验证用途：买入指定手数，闸门任一失败即拒单不提交。
设计: docs/feat/0611-realtime-order/2026-06-11-realtime-order-design.md D2/D3/D5
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from src.domain.trade.entities.order import Order
from src.domain.trade.services.pre_trade_checks import (
    MAX_NOTIONAL_CEILING,
    PRICE_BAND,
    build_limit_price,
    check_buy_cash,
    check_notional_cap,
    check_price_band,
    check_symbol_scope,
    check_trading_session,
)
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType

if TYPE_CHECKING:
    from src.domain.market.interfaces.gateways.realtime_quote_fetcher import IRealtimeQuoteFetcher

__all__ = ["MAX_NOTIONAL_CEILING", "OrderTicketAppService", "OrderTicketResult"]


@dataclass(slots=True, kw_only=True)
class OrderTicketResult:
    """单笔下单结果（含审计 ticket）。"""
    accepted: bool
    reject_reason: str | None = None
    order_id: str | None = None
    final_status: str | None = None  # FILLED/PARTIAL/ALIVE/CANCELED/REJECTED/TIMEOUT
    ticket: dict = field(default_factory=dict)


class OrderTicketAppService:
    """受控单笔买入。全部依赖注入，可 mock 单测。"""

    def __init__(
        self,
        quote_fetcher: IRealtimeQuoteFetcher,
        trade_gateway,
        account_gateway,
        max_notional: float = 1500.0,
        clock: Callable[[], datetime] = datetime.now,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._quotes = quote_fetcher
        self._trade = trade_gateway
        self._account = account_gateway
        self._max_notional = min(max_notional, MAX_NOTIONAL_CEILING)
        self._clock = clock
        self._sleep = sleep

    def buy_lots(
        self, symbol: str, lots: int = 1, poll_timeout: float = 60.0
    ) -> OrderTicketResult:
        ticket: dict = {
            "symbol": symbol, "lots": lots, "direction": "BUY",
            "max_notional": self._max_notional,
            "requested_at": self._clock().isoformat(),
        }

        # 闸 0: 标的范围 (主板 only, 设计 D4; 闸实现见 domain pre_trade_checks)
        if lots <= 0:
            return self._reject(ticket, f"手数非法: {lots}")
        if reason := check_symbol_scope(symbol):
            return self._reject(ticket, reason)

        # 闸 1: 交易时段
        now = self._clock()
        if reason := check_trading_session(now):
            return self._reject(ticket, reason)

        # 闸 2: 实时报价 (订阅优先, 快照兜底)
        quote = self._quotes.subscribe_first_tick(symbol)
        if quote is None or quote.last <= 0 or quote.prev_close <= 0:
            return self._reject(ticket, "拿不到有效实时报价 (停牌/退市/行情断连?)")
        ticket["quote"] = {
            "last": quote.last, "bid1": quote.bid1, "ask1": quote.ask1,
            "prev_close": quote.prev_close, "ts": quote.timestamp.isoformat(),
        }

        # 闸 3: 限价构造 + 涨跌停带 (设计 D3)
        price = build_limit_price(OrderDirection.BUY, quote)
        if reason := check_price_band(price, prev_close=quote.prev_close):
            return self._reject(ticket, reason)
        volume = lots * 100
        notional = price * volume
        band = [round(quote.prev_close * (1 - PRICE_BAND), 2),
                round(quote.prev_close * (1 + PRICE_BAND), 2)]
        ticket.update({"price": price, "volume": volume, "notional": round(notional, 2),
                       "price_band": band})

        # 闸 4: 单笔金额上限 (构造时已压硬顶)
        if reason := check_notional_cap(notional, cap=self._max_notional):
            return self._reject(ticket, reason)

        # 闸 5: 可用资金
        asset = self._account.get_asset()
        if asset is None:
            return self._reject(ticket, "查询账户资金失败")
        ticket["available_cash"] = asset.available_cash
        if reason := check_buy_cash(notional, available_cash=asset.available_cash):
            return self._reject(ticket, reason)

        # 提交限价单
        order = Order(
            order_id=f"ticket-{uuid.uuid4().hex[:8]}",
            account_id=getattr(asset, "account_id", ""),
            ticker=symbol,
            direction=OrderDirection.BUY,
            price=price,
            volume=volume,
            type=OrderType.LIMIT,
            remark="order-ticket-v1",
        )
        order_id = self._trade.place_order(order)
        ticket["order_id"] = order_id
        ticket["submitted_at"] = self._clock().isoformat()

        final_status, trail = self._poll_until_terminal(order_id, poll_timeout)
        ticket["status_trail"] = trail
        return OrderTicketResult(
            accepted=True, order_id=order_id, final_status=final_status, ticket=ticket
        )

    def _poll_until_terminal(
        self, order_id: str, timeout: float
    ) -> tuple[str, list[dict]]:
        """轮询订单状态至终态/超时。返回 (终态, 状态轨迹)。"""
        from src.domain.trade.services.order_poller import poll_order_until_terminal

        result = poll_order_until_terminal(
            order_id,
            query_status=self._trade.query_order_status,
            timeout_seconds=timeout,
            clock=lambda: self._clock().timestamp(),
            sleep=self._sleep,
            cancel_on_timeout=False,  # ticket 手动下单不撤单
        )
        return result.final_status, result.trail

    @staticmethod
    def _reject(ticket: dict, reason: str) -> OrderTicketResult:
        ticket["reject_reason"] = reason
        return OrderTicketResult(accepted=False, reject_reason=reason, ticket=ticket)
