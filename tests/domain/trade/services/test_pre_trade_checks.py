"""盘前闸纯函数测试 — 口径必须与首单 ticket 完全一致（取整/边界/文案关键词）。"""
from datetime import datetime

from src.domain.market.value_objects.quote import Quote
from src.domain.trade.services.pre_trade_checks import (
    build_limit_price,
    check_buy_cash,
    check_daily_loss_block_buys,
    check_notional_cap,
    check_price_band,
    check_sell_volume,
    check_symbol_scope,
    check_trading_session,
    run_pre_trade_gates,
)
from src.domain.trade.value_objects.order_direction import OrderDirection

WED = datetime(2026, 6, 10, 10, 0)  # 周三盘中


def _quote(last=5.0, bid1=4.99, ask1=5.01, prev_close=5.0) -> Quote:
    return Quote(symbol="601006.SH", last=last, bid1=bid1, ask1=ask1,
                 prev_close=prev_close, timestamp=WED)


class TestScopeAndSession:
    def test_main_board_passes(self):
        assert check_symbol_scope("601006.SH") is None
        assert check_symbol_scope("000001.SZ") is None

    def test_gem_and_sme_rejected(self):
        assert check_symbol_scope("300750.SZ") is not None
        assert check_symbol_scope("002284.SZ") is not None

    def test_session_boundaries(self):
        assert check_trading_session(datetime(2026, 6, 10, 9, 29)) is not None
        assert check_trading_session(datetime(2026, 6, 10, 9, 30)) is None
        assert check_trading_session(datetime(2026, 6, 13, 10, 0)) is not None  # 周六


class TestPricing:
    def test_buy_price_is_min_of_ask_and_protection(self):
        assert build_limit_price(OrderDirection.BUY, _quote(ask1=5.20)) == round(5.0 * 1.002, 2)
        assert build_limit_price(OrderDirection.BUY, _quote(ask1=5.001)) == 5.0

    def test_buy_falls_back_when_no_ask(self):
        assert build_limit_price(OrderDirection.BUY, _quote(ask1=None)) == round(5.0 * 1.002, 2)

    def test_sell_price_is_max_of_bid_and_protection(self):
        assert build_limit_price(OrderDirection.SELL, _quote(bid1=5.0)) == 5.0
        assert build_limit_price(OrderDirection.SELL, _quote(bid1=None)) == round(5.0 * 0.998, 2)
        assert build_limit_price(OrderDirection.SELL, _quote(bid1=4.5)) == round(5.0 * 0.998, 2)

    def test_price_band(self):
        assert check_price_band(5.49, prev_close=5.0) is None
        assert check_price_band(5.51, prev_close=5.0) is not None


class TestCapsAndFunds:
    def test_notional_cap(self):
        assert check_notional_cap(1500.0, cap=1500.0) is None
        assert check_notional_cap(1500.01, cap=1500.0) is not None

    def test_notional_cap_hard_ceiling(self):
        assert check_notional_cap(5000.01, cap=99999.0) is not None

    def test_notional_cap_ceiling_default_unchanged(self):
        assert check_notional_cap(5001.0, cap=9000.0) is not None  # 默认硬顶 5000 仍生效

    def test_notional_cap_ceiling_raised(self):
        assert check_notional_cap(7300.0, cap=9000.0, ceiling=10000.0) is None
        assert check_notional_cap(9500.0, cap=9000.0, ceiling=10000.0) is not None  # cap 仍约束

    def test_buy_cash_includes_fee_buffer(self):
        assert check_buy_cash(1000.0, available_cash=1010.0) is None
        assert check_buy_cash(1000.0, available_cash=1009.9) is not None

    def test_sell_volume(self):
        assert check_sell_volume(100, available_volume=100) is None
        assert check_sell_volume(200, available_volume=100) is not None

    def test_daily_loss_block(self):
        assert check_daily_loss_block_buys(100000.0, 97999.0, limit_ratio=0.02) is True
        assert check_daily_loss_block_buys(100000.0, 98001.0, limit_ratio=0.02) is False
        assert check_daily_loss_block_buys(0.0, 0.0, limit_ratio=0.02) is False


class TestAggregateGates:
    def test_buy_happy_path_returns_price_and_notional(self):
        r = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.BUY, volume=100,
            quote=_quote(), now=WED, max_notional=1500.0, available_cash=10000.0,
        )
        assert r.passed and r.reject_reason is None
        assert r.limit_price == 5.01 and r.notional == 501.0  # min(ask1, last×1.002)

    def test_each_gate_rejects_in_order(self):
        bad_scope = run_pre_trade_gates(
            symbol="300750.SZ", direction=OrderDirection.BUY, volume=100,
            quote=_quote(), now=WED, max_notional=1500.0, available_cash=1e6,
        )
        assert not bad_scope.passed and "范围" in bad_scope.reject_reason

        stale = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.BUY, volume=100,
            quote=None, now=WED, max_notional=1500.0, available_cash=1e6,
        )
        assert not stale.passed and "报价" in stale.reject_reason

    def test_buy_odd_lot_rejected(self):
        r = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.BUY, volume=150,
            quote=_quote(), now=WED, max_notional=1500.0, available_cash=1e6,
        )
        assert not r.passed and "100" in r.reject_reason

    def test_sell_odd_lot_allowed(self):
        """A 股零股(送配产生)允许一次性卖出 — 卖出不受 100 整数倍限制。"""
        r = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.SELL, volume=150,
            quote=_quote(), now=WED, max_notional=1500.0, available_volume=150,
        )
        assert r.passed

    def test_stale_quote_rejected(self):
        """报价新鲜度闸: 停牌/断连回退的陈旧快照必须拒单。"""
        from datetime import timedelta
        stale = Quote(symbol="601006.SH", last=5.0, bid1=4.99, ask1=5.01,
                      prev_close=5.0, timestamp=WED - timedelta(minutes=10))
        r = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.BUY, volume=100,
            quote=stale, now=WED, max_notional=1500.0, available_cash=1e6,
        )
        assert not r.passed and "过期" in r.reject_reason

    def test_run_pre_trade_gates_passes_ceiling(self):
        """notional≈7300 > 默认硬顶 5000, 抬高 notional_ceiling=10000 后过闸。"""
        r = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.BUY, volume=1000,
            quote=_quote(last=7.3, bid1=7.29, ask1=7.31, prev_close=7.3),
            now=WED, max_notional=9000.0, notional_ceiling=10000.0,
            available_cash=10000.0,
        )
        assert r.passed and r.reject_reason is None
        assert r.notional == 7310.0  # min(ask1, last×1.002)=7.31 × 1000

    def test_sell_uses_volume_gate_not_cash(self):
        r = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.SELL, volume=100,
            quote=_quote(), now=WED, max_notional=1500.0, available_volume=100,
        )
        assert r.passed
        r2 = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.SELL, volume=200,
            quote=_quote(), now=WED, max_notional=1500.0, available_volume=100,
        )
        assert not r2.passed
