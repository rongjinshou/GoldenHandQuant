"""QMT 实时行情实现 — get_full_tick 快照 + subscribe_quote 订阅。

设计: docs/feat/0611-realtime-order/2026-06-11-realtime-order-design.md D1
"""

import logging
import threading
from datetime import datetime

from src.domain.market.value_objects.quote import Quote

from .xtquant_client import xtdata

logger = logging.getLogger(__name__)


def _to_quote(symbol: str, tick: dict) -> Quote | None:
    """xtdata tick dict → Quote。关键字段缺失/非法时返回 None。"""
    last = float(tick.get("lastPrice") or 0)
    prev_close = float(tick.get("lastClose") or 0)
    if last <= 0 or prev_close <= 0:
        return None

    def _first_level(key: str) -> float | None:
        levels = tick.get(key)
        try:
            v = float(levels[0]) if levels is not None else 0.0
        except (TypeError, IndexError, ValueError):
            return None
        return v if v > 0 else None

    ts_raw = tick.get("time")
    if isinstance(ts_raw, (int, float)) and ts_raw > 0:
        timestamp = datetime.fromtimestamp(ts_raw / 1000)
    else:
        timestamp = datetime.now()

    return Quote(
        symbol=symbol,
        last=last,
        bid1=_first_level("bidPrice"),
        ask1=_first_level("askPrice"),
        prev_close=prev_close,
        timestamp=timestamp,
    )


class QmtRealtimeQuoteFetcher:
    """实时行情获取（实现 IRealtimeQuoteFetcher）。"""

    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        try:
            ticks = xtdata.get_full_tick(symbols)
        except Exception as e:
            logger.error("get_full_tick failed: %s", e)
            return {}
        quotes: dict[str, Quote] = {}
        for symbol in symbols:
            tick = ticks.get(symbol)
            if not tick:
                continue
            quote = _to_quote(symbol, tick)
            if quote is not None:
                quotes[symbol] = quote
        return quotes

    def subscribe_first_tick(self, symbol: str, timeout: float = 3.0) -> Quote | None:
        """订阅 tick 推送等首笔；超时回退快照。"""
        received: dict[str, Quote] = {}
        event = threading.Event()

        def _on_tick(data: dict) -> None:
            # subscribe_quote 回调: {symbol: [tick_dict, ...]} 或 {symbol: tick_dict}
            try:
                payload = data.get(symbol)
                if payload is None:
                    return
                tick = payload[-1] if isinstance(payload, list) else payload
                quote = _to_quote(symbol, tick)
                if quote is not None:
                    received["quote"] = quote
                    event.set()
            except Exception as e:  # 回调内异常不许外抛(xtdata 推送线程)
                logger.error("tick callback error: %s", e)

        seq = -1
        try:
            seq = xtdata.subscribe_quote(symbol, period="tick", callback=_on_tick)
            if event.wait(timeout):
                logger.info("subscribe_quote got first tick for %s", symbol)
                return received["quote"]
            logger.warning("subscribe_quote timeout (%.1fs) for %s, fallback to snapshot",
                           timeout, symbol)
        except Exception as e:
            logger.error("subscribe_quote failed for %s: %s", symbol, e)
        finally:
            if seq != -1:
                try:
                    xtdata.unsubscribe_quote(seq)
                except Exception:
                    pass

        return self.get_quotes([symbol]).get(symbol)
