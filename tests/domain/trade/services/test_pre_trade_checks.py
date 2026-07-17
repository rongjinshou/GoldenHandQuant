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
    check_st_name,
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


class TestStNameGate:
    """实时 ST 闸(0704 真单前置 DD-3): 当日刚戴帽的股 T-1 数据不知情, 下单前实时名称校验。"""

    def test_st_prefixes_rejected(self):
        for name in ("ST 星源", "*ST深天", "SST前锋", "S*ST新亿", "st小写"):
            assert check_st_name(name) is not None, name

    def test_normal_or_none_passes(self):
        assert check_st_name("平安银行") is None
        assert check_st_name("") is None       # 空名不可判 → 放行(报价闸兜底)
        assert check_st_name(None) is None     # 名称不可得 → 放行

    def test_gate_blocks_buy_but_not_sell(self):
        buy = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.BUY, volume=100,
            quote=_quote(), now=WED, max_notional=1500.0, available_cash=1e6,
            instrument_name="ST 星源",
        )
        assert not buy.passed and "ST" in buy.reject_reason

        sell = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.SELL, volume=100,
            quote=_quote(), now=WED, max_notional=1500.0, available_volume=100,
            instrument_name="ST 星源",
        )
        assert sell.passed  # 退出持仓不拦


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


class TestTradingCalendarGate:
    """M7 交易日历闸（2026-07-10 六西格玛体检, 决策项 Q8 获批）。

    旧时段闸只排周末: 法定节假日(工作日)会通过时段判定, 唯一兜底是报价
    新鲜度 180s。日历从 bars 推导: 已知休市拒单, 未来日 unknown 放行。
    """

    def test_known_holiday_workday_rejected(self):
        from datetime import date, datetime

        from src.domain.trade.services.pre_trade_checks import check_trading_session
        from src.domain.trade.services.trading_calendar import TradingCalendar

        # 2026-06-10(周三)不在交易日集合 → 休市(如端午)
        cal = TradingCalendar.from_dates([date(2026, 6, 9), date(2026, 6, 11)])

        reason = check_trading_session(datetime(2026, 6, 10, 9, 35), cal)

        assert reason is not None and "休市" in reason

    def test_known_trading_day_passes(self):
        from datetime import date, datetime

        from src.domain.trade.services.pre_trade_checks import check_trading_session
        from src.domain.trade.services.trading_calendar import TradingCalendar

        cal = TradingCalendar.from_dates([date(2026, 6, 10)])

        assert check_trading_session(datetime(2026, 6, 10, 9, 35), cal) is None

    def test_future_unknown_day_falls_back_to_session_logic(self):
        from datetime import date, datetime

        from src.domain.trade.services.pre_trade_checks import check_trading_session
        from src.domain.trade.services.trading_calendar import TradingCalendar

        cal = TradingCalendar.from_dates([date(2026, 6, 10)])  # known_until=6/10

        # 未来工作日盘中: 日历 unknown → 放行(新鲜度闸兜底)
        assert check_trading_session(datetime(2026, 6, 17, 9, 35), cal) is None

    def test_no_calendar_keeps_legacy_behavior(self):
        from datetime import datetime

        from src.domain.trade.services.pre_trade_checks import check_trading_session

        assert check_trading_session(datetime(2026, 6, 10, 9, 35), None) is None


class TestSellExitAsymmetry:
    """买严卖畅(0713 彩排实证: 趋势闸清仓单被金额闸/白名单拦死, 防御性退出失效)。

    先例: 实时 ST 闸 buy-only(0704 DD-3)。SELL 仍受: 时段/新鲜度/价格带/T+1 可用量/
    同标的当日一次/日总额度——放宽的只是"为防错买设计"的两道闸。
    """

    def _quote(self, now):
        from src.domain.market.value_objects.quote import Quote
        return Quote(symbol="002284.SZ", last=9.0, bid1=8.99, ask1=9.01,
                     prev_close=9.2, timestamp=now)

    def test_sell_of_off_whitelist_holding_passes_scope(self):
        from datetime import datetime

        from src.domain.trade.services.pre_trade_checks import run_pre_trade_gates
        from src.domain.trade.value_objects.order_direction import OrderDirection
        now = datetime(2026, 7, 13, 10, 0, 0)
        r = run_pre_trade_gates(symbol="002284.SZ", direction=OrderDirection.SELL,
                                volume=3800, quote=self._quote(now), now=now,
                                max_notional=9000.0, available_volume=3800)
        assert r.passed, r.reject_reason  # 002 板持仓退出不受买入白名单约束

    def test_sell_beyond_notional_cap_passes(self):
        from datetime import datetime

        from src.domain.market.value_objects.quote import Quote
        from src.domain.trade.services.pre_trade_checks import run_pre_trade_gates
        from src.domain.trade.value_objects.order_direction import OrderDirection
        now = datetime(2026, 7, 13, 10, 0, 0)
        q = Quote(symbol="000021.SZ", last=54.0, bid1=53.99, ask1=54.01,
                  prev_close=57.9, timestamp=now)
        r = run_pre_trade_gates(symbol="000021.SZ", direction=OrderDirection.SELL,
                                volume=600, quote=q, now=now,
                                max_notional=9000.0, available_volume=600)
        assert r.passed, r.reject_reason  # ¥32k 卖单不再被 ¥9k 单笔闸拦死

    def test_buy_still_gated_by_scope_and_cap(self):
        from datetime import datetime

        from src.domain.trade.services.pre_trade_checks import run_pre_trade_gates
        from src.domain.trade.value_objects.order_direction import OrderDirection
        now = datetime(2026, 7, 13, 10, 0, 0)
        r1 = run_pre_trade_gates(symbol="002284.SZ", direction=OrderDirection.BUY,
                                 volume=100, quote=self._quote(now), now=now,
                                 max_notional=9000.0, available_cash=1e6)
        assert not r1.passed and "允许范围" in r1.reject_reason
        from src.domain.market.value_objects.quote import Quote
        q = Quote(symbol="000021.SZ", last=54.0, bid1=53.99, ask1=54.01,
                  prev_close=53.0, timestamp=now)
        r2 = run_pre_trade_gates(symbol="000021.SZ", direction=OrderDirection.BUY,
                                 volume=600, quote=q, now=now,
                                 max_notional=9000.0, available_cash=1e6)
        assert not r2.passed and "上限" in r2.reject_reason
