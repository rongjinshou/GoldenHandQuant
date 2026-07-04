"""盘前安全闸 — domain 纯函数集，单笔 ticket 与自动循环共用（单一事实来源）。

口径与首笔实单验证一致（docs/feat/0611-realtime-order 设计 D2/D3/D4）：
主板 only、连续竞价时段、报价新鲜、±10% 涨跌停带、单笔金额硬顶、资金/持仓校验。
设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md DD-3
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.market.value_objects.quote import Quote
from src.domain.trade.value_objects.order_direction import OrderDirection

PRICE_BAND = 0.10                 # 主板涨跌停带
MAX_NOTIONAL_CEILING = 5000.0     # 单笔金额上限的硬顶
CASH_FEE_BUFFER = 1.01            # 买入资金费用 buffer
MAX_QUOTE_AGE_SECONDS = 180.0     # 报价新鲜度: 超龄视为停牌/断连的陈旧快照
_SESSIONS = (("09:30", "11:30"), ("13:00", "15:00"))


@dataclass(frozen=True, slots=True, kw_only=True)
class GateResult:
    """聚合闸结果：通过时携带限价与金额。"""
    passed: bool
    reject_reason: str | None = None
    limit_price: float | None = None
    notional: float | None = None


def check_symbol_scope(symbol: str) -> str | None:
    code, _, market = symbol.partition(".")
    if market == "SH" and code.startswith("60"):
        return None
    if market == "SZ" and (code.startswith("000") or code.startswith("001")):
        return None
    return f"{symbol} 不在 v1 允许范围 (仅沪深主板 60xxxx/000xxx)"


def check_st_name(name: str | None) -> str | None:
    """实时 ST 名称闸(0704 真单前置 DD-3): 当日刚戴帽的股 T-1 数据不知情。

    name 为 None/空 = 名称不可得 → 放行(不误拦; 停牌/断连由报价新鲜度闸兜底)。
    前缀口径同 domain/strategy 的 filter_st(ST/*ST/SST/S*ST)。
    """
    if not name:
        return None
    if name.upper().startswith(("ST", "*ST", "SST", "S*ST")):
        return f"实时名称含风险警示: {name} (当日戴帽? T-1 数据不知情)"
    return None


def check_trading_session(now: datetime) -> str | None:
    if now.weekday() >= 5:
        return f"非交易日: {now:%Y-%m-%d} (周{now.weekday() + 1})"
    hm = now.strftime("%H:%M")
    if any(start <= hm <= end for start, end in _SESSIONS):
        return None
    return f"非连续竞价时段: {now:%Y-%m-%d %H:%M} (9:30-11:30/13:00-15:00)"


def build_limit_price(direction: OrderDirection, quote: Quote) -> float:
    """买: 贴卖一但不超 last×1.002；卖: 贴买一但不低于 last×0.998。"""
    if direction == OrderDirection.BUY:
        raw = quote.ask1 if quote.ask1 else quote.last * 1.002
        return round(min(raw, quote.last * 1.002), 2)
    raw = quote.bid1 if quote.bid1 else quote.last * 0.998
    return round(max(raw, quote.last * 0.998), 2)


def check_price_band(price: float, *, prev_close: float, band: float = PRICE_BAND) -> str | None:
    low = round(prev_close * (1 - band), 2)
    high = round(prev_close * (1 + band), 2)
    if low <= price <= high:
        return None
    return f"限价 {price} 超出涨跌停带 [{low}, {high}] (前收 {prev_close})"


def check_notional_cap(
    notional: float, *, cap: float, ceiling: float = MAX_NOTIONAL_CEILING
) -> str | None:
    effective = min(cap, ceiling)
    if notional <= effective:
        return None
    return f"金额 {notional:.2f} 超上限 {effective:.2f}"


def check_buy_cash(notional: float, *, available_cash: float) -> str | None:
    required = notional * CASH_FEE_BUFFER
    if available_cash >= required:
        return None
    return f"可用资金 {available_cash:.2f} < 需求 {required:.2f}"


def check_sell_volume(volume: int, *, available_volume: int) -> str | None:
    if volume <= available_volume:
        return None
    return f"卖出量 {volume} > 可用持仓 {available_volume} (T+1)"


def check_daily_loss_block_buys(
    day_start_equity: float, current_equity: float, *, limit_ratio: float
) -> bool:
    """当日权益回撤超限 → True(禁买)。基准非正时不拦截。"""
    if day_start_equity <= 0:
        return False
    drawdown = (day_start_equity - current_equity) / day_start_equity
    return drawdown > limit_ratio


def run_pre_trade_gates(
    *,
    symbol: str,
    direction: OrderDirection,
    volume: int,
    quote: Quote | None,
    now: datetime,
    max_notional: float,
    notional_ceiling: float = MAX_NOTIONAL_CEILING,
    available_cash: float | None = None,
    available_volume: int | None = None,
    instrument_name: str | None = None,
) -> GateResult:
    """七道闸逐序检查（自动循环用的聚合入口）。"""
    if volume <= 0:
        return GateResult(passed=False, reject_reason=f"数量非法: {volume}")
    # 买入须 100 整数倍; 卖出允许零股(送配产生的不足一手持仓可一次性卖出)
    if direction == OrderDirection.BUY and volume % 100 != 0:
        return GateResult(passed=False, reject_reason=f"数量非法: {volume} (买入须为 100 整数倍)")
    if reason := check_symbol_scope(symbol):
        return GateResult(passed=False, reject_reason=reason)
    # 实时 ST 闸只拦买入: 退出持仓(卖出)不得被自身风险警示阻断
    if direction == OrderDirection.BUY and (reason := check_st_name(instrument_name)):
        return GateResult(passed=False, reject_reason=reason)
    if reason := check_trading_session(now):
        return GateResult(passed=False, reject_reason=reason)
    if quote is None or quote.last <= 0 or quote.prev_close <= 0:
        return GateResult(passed=False, reject_reason="拿不到有效实时报价 (停牌/退市/行情断连?)")
    age = (now - quote.timestamp).total_seconds()
    if age > MAX_QUOTE_AGE_SECONDS:
        return GateResult(
            passed=False,
            reject_reason=f"报价过期 {age:.0f}s (>{MAX_QUOTE_AGE_SECONDS:.0f}s, 停牌/行情断连?)",
        )

    price = build_limit_price(direction, quote)
    if reason := check_price_band(price, prev_close=quote.prev_close):
        return GateResult(passed=False, reject_reason=reason)

    notional = price * volume
    if reason := check_notional_cap(notional, cap=max_notional, ceiling=notional_ceiling):
        return GateResult(passed=False, reject_reason=reason)

    if direction == OrderDirection.BUY:
        if reason := check_buy_cash(notional, available_cash=available_cash or 0.0):
            return GateResult(passed=False, reject_reason=reason)
    else:
        if reason := check_sell_volume(volume, available_volume=available_volume or 0):
            return GateResult(passed=False, reject_reason=reason)

    return GateResult(passed=True, limit_price=price, notional=round(notional, 2))
