"""OrderTicketAppService 单测 — 五道安全闸逐一拒绝 + happy path。"""

from datetime import datetime

from src.application.order_ticket_app import OrderTicketAppService, OrderTicketResult
from src.domain.account.entities.asset import Asset
from src.domain.market.value_objects.quote import Quote


class _StubQuotes:
    def __init__(self, quote: Quote | None):
        self._quote = quote

    def get_quotes(self, symbols):
        return {self._quote.symbol: self._quote} if self._quote else {}

    def subscribe_first_tick(self, symbol, timeout=3.0):
        return self._quote


class _StubTrade:
    def __init__(self, statuses: list[str | None] | None = None):
        self.placed: list = []
        self._statuses = statuses or ["ALIVE", "FILLED"]
        self._i = 0

    def place_order(self, order):
        self.placed.append(order)
        return "880001"

    def query_order_status(self, order_id):
        s = self._statuses[min(self._i, len(self._statuses) - 1)]
        self._i += 1
        return s


class _StubAccount:
    def __init__(self, cash: float):
        self._cash = cash

    def get_asset(self, account_id=None):
        return Asset(account_id="55****88", total_asset=self._cash,
                     available_cash=self._cash, frozen_cash=0.0)


_TRADING_TIME = datetime(2026, 6, 11, 13, 5)  # 周四 13:05, 连续竞价中


def _quote(last=5.0, bid1=4.99, ask1=5.01, prev_close=5.0) -> Quote:
    return Quote(symbol="601288.SH", last=last, bid1=bid1, ask1=ask1,
                 prev_close=prev_close, timestamp=_TRADING_TIME)


def _service(quote=None, cash=10_000.0, trade=None, now=_TRADING_TIME,
             max_notional=1500.0) -> tuple[OrderTicketAppService, _StubTrade]:
    trade = trade or _StubTrade()
    svc = OrderTicketAppService(
        quote_fetcher=_StubQuotes(quote),
        trade_gateway=trade,
        account_gateway=_StubAccount(cash),
        max_notional=max_notional,
        clock=lambda: now,
        sleep=lambda s: None,
    )
    return svc, trade


class TestGates:
    def test_rejects_non_main_board(self):
        svc, trade = _service(_quote())
        r = svc.buy_lots("300750.SZ")  # 创业板
        assert not r.accepted and "主板" in r.reject_reason
        assert trade.placed == []

    def test_rejects_outside_trading_session(self):
        svc, trade = _service(_quote(), now=datetime(2026, 6, 11, 12, 0))  # 午休
        r = svc.buy_lots("601288.SH")
        assert not r.accepted and "非连续竞价时段" in r.reject_reason

    def test_rejects_weekend(self):
        svc, _ = _service(_quote(), now=datetime(2026, 6, 13, 10, 0))  # 周六
        assert not svc.buy_lots("601288.SH").accepted

    def test_rejects_when_no_quote(self):
        svc, trade = _service(quote=None)
        r = svc.buy_lots("601288.SH")
        assert not r.accepted and "实时报价" in r.reject_reason
        assert trade.placed == []

    def test_rejects_price_outside_band(self):
        # 卖一已飘到涨停带外 (前收 5.0, +10% 带顶 5.5, ask=5.6)
        svc, trade = _service(_quote(last=5.6, ask1=5.61, prev_close=5.0))
        r = svc.buy_lots("601288.SH")
        assert not r.accepted and "涨跌停带" in r.reject_reason

    def test_rejects_notional_above_cap(self):
        svc, _ = _service(_quote(last=20.0, ask1=20.01, prev_close=20.0))
        r = svc.buy_lots("601288.SH")  # 20.01*100 > 1500
        assert not r.accepted and "超上限" in r.reject_reason

    def test_rejects_insufficient_cash(self):
        svc, _ = _service(_quote(), cash=100.0)
        r = svc.buy_lots("601288.SH")
        assert not r.accepted and "可用资金" in r.reject_reason

    def test_max_notional_hard_ceiling(self):
        svc, _ = _service(_quote(last=55.0, ask1=55.0, prev_close=55.0),
                          max_notional=999_999.0)  # 请求上限被压到 5000
        r = svc.buy_lots("601288.SH")  # 5500 > 5000 硬顶
        assert not r.accepted and "超上限" in r.reject_reason


class TestHappyPath:
    def test_places_limit_order_and_polls_to_filled(self):
        svc, trade = _service(_quote(last=5.0, ask1=5.01))
        r = svc.buy_lots("601288.SH", lots=1)

        assert isinstance(r, OrderTicketResult)
        assert r.accepted and r.order_id == "880001"
        assert r.final_status == "FILLED"

        order = trade.placed[0]
        assert order.volume == 100
        assert order.price == 5.01  # min(ask1, last*1.002=5.01)
        assert r.ticket["notional"] == 501.0
        assert [s["status"] for s in r.ticket["status_trail"]] == ["ALIVE", "FILLED"]

    def test_price_falls_back_when_no_ask(self):
        svc, trade = _service(_quote(last=5.0, ask1=None))
        r = svc.buy_lots("601288.SH")
        assert r.accepted
        assert trade.placed[0].price == round(5.0 * 1.002, 2)  # 5.01

    def test_price_capped_by_last_protection(self):
        # ask1 异常飘高时, 限价被 last*1.002 保护(不追价)
        svc, trade = _service(_quote(last=5.0, ask1=5.4, prev_close=5.0))
        r = svc.buy_lots("601288.SH")
        assert r.accepted
        assert trade.placed[0].price == 5.01

    def test_timeout_reports_last_known_state(self):
        trade = _StubTrade(statuses=["ALIVE"])
        # poll_timeout=0 → 立即超时, 报告 TIMEOUT
        svc, _ = _service(_quote(), trade=trade)
        r = svc.buy_lots("601288.SH", poll_timeout=0)
        assert r.accepted and r.final_status == "TIMEOUT"
