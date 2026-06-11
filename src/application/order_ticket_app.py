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
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType

if TYPE_CHECKING:
    from src.domain.market.interfaces.gateways.realtime_quote_fetcher import IRealtimeQuoteFetcher

# 主板涨跌停带（v1 只允许主板, 见设计 D4）
_PRICE_BAND = 0.10
# CLI 可调金额上限的硬顶
MAX_NOTIONAL_CEILING = 5000.0

# A 股连续竞价时段 (本地时钟)
_SESSIONS = (("09:30", "11:30"), ("13:00", "15:00"))


@dataclass(slots=True, kw_only=True)
class OrderTicketResult:
    """单笔下单结果（含审计 ticket）。"""
    accepted: bool
    reject_reason: str | None = None
    order_id: str | None = None
    final_status: str | None = None  # FILLED/PARTIAL/ALIVE/CANCELED/REJECTED/TIMEOUT
    ticket: dict = field(default_factory=dict)


def _in_trading_session(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    hm = now.strftime("%H:%M")
    return any(start <= hm <= end for start, end in _SESSIONS)


def _is_main_board(symbol: str) -> bool:
    code, _, market = symbol.partition(".")
    if market == "SH":
        return code.startswith("60")
    if market == "SZ":
        return code.startswith("000") or code.startswith("001")
    return False


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

        # 闸 0: 标的范围 (主板 only, 设计 D4)
        if lots <= 0:
            return self._reject(ticket, f"手数非法: {lots}")
        if not _is_main_board(symbol):
            return self._reject(ticket, f"{symbol} 不在 v1 允许范围 (仅沪深主板 60xxxx/000xxx)")

        # 闸 1: 交易时段
        now = self._clock()
        if not _in_trading_session(now):
            return self._reject(ticket, f"非连续竞价时段: {now:%Y-%m-%d %H:%M} (9:30-11:30/13:00-15:00)")

        # 闸 2: 实时报价 (订阅优先, 快照兜底)
        quote = self._quotes.subscribe_first_tick(symbol)
        if quote is None or quote.last <= 0 or quote.prev_close <= 0:
            return self._reject(ticket, "拿不到有效实时报价 (停牌/退市/行情断连?)")
        ticket["quote"] = {
            "last": quote.last, "bid1": quote.bid1, "ask1": quote.ask1,
            "prev_close": quote.prev_close, "ts": quote.timestamp.isoformat(),
        }

        # 闸 3: 限价构造 + 涨跌停带 (设计 D3)
        raw_price = quote.ask1 if quote.ask1 else quote.last * 1.002
        price = round(min(raw_price, quote.last * 1.002), 2)
        low = round(quote.prev_close * (1 - _PRICE_BAND), 2)
        high = round(quote.prev_close * (1 + _PRICE_BAND), 2)
        if not (low <= price <= high):
            return self._reject(
                ticket, f"限价 {price} 超出涨跌停带 [{low}, {high}] (前收 {quote.prev_close})"
            )
        volume = lots * 100
        notional = price * volume
        ticket.update({"price": price, "volume": volume, "notional": round(notional, 2),
                       "price_band": [low, high]})

        # 闸 4: 单笔金额上限
        if notional > self._max_notional:
            return self._reject(
                ticket, f"金额 {notional:.2f} 超上限 {self._max_notional:.2f}"
            )

        # 闸 5: 可用资金
        asset = self._account.get_asset()
        if asset is None:
            return self._reject(ticket, "查询账户资金失败")
        required = notional * 1.01  # 费用 buffer
        ticket["available_cash"] = asset.available_cash
        if asset.available_cash < required:
            return self._reject(
                ticket, f"可用资金 {asset.available_cash:.2f} < 需求 {required:.2f}"
            )

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
        trail: list[dict] = []
        deadline = self._clock().timestamp() + timeout
        last_state: str | None = None
        while self._clock().timestamp() < deadline:
            state = self._trade.query_order_status(order_id)
            if state and state != last_state:
                trail.append({"t": self._clock().isoformat(), "status": state})
                last_state = state
            if state in ("FILLED", "CANCELED", "REJECTED"):
                return state, trail
            self._sleep(2.0)
        return last_state or "TIMEOUT", trail

    @staticmethod
    def _reject(ticket: dict, reason: str) -> OrderTicketResult:
        ticket["reject_reason"] = reason
        return OrderTicketResult(accepted=False, reject_reason=reason, ticket=ticket)
