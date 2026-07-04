"""退市强平(B1 DD-9): 持仓股 bars 断流(退市)时于末根日按收盘强平, 活股行为零变化。

无强平语义时断流持仓变僵尸(卖单无执行价发不出, 市值冻结) — 含退市股宇宙的
敏感性复跑(docs/feat/0704-b1-delisted-backfill/)以此为可信前提。
"""

from datetime import datetime, timedelta

from src.application.backtest_app import BacktestAppService
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.services.base_strategy import BaseStrategy
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway

_BASE = datetime(2025, 1, 2)


def _bars(symbol: str, n_days: int, price: float = 10.0) -> list[Bar]:
    return [Bar(
        symbol=symbol, timeframe=Timeframe.DAY_1,
        timestamp=_BASE + timedelta(days=i),
        open=price, high=price * 1.01, low=price * 0.99, close=price,
        volume=1_000_000, unadjusted_close=price, prev_close=price,
    ) for i in range(n_days)]


class _BuyOnceHold(BaseStrategy):
    """首个交易日对全部标的发 BUY, 之后永远 hold(不再发信号)。"""

    def __init__(self) -> None:
        self._bought = False

    @property
    def name(self) -> str:
        return "BuyOnceHold"

    def generate_signals(self, market_data, current_positions):
        if self._bought or not market_data:   # 首日窗口不足时不消耗唯一一次买入
            return []
        self._bought = True
        return [
            Signal(symbol=s, direction=SignalDirection.BUY,
                   confidence_score=1.0, strategy_name=self.name, reason="init")
            for s in sorted(market_data)
        ]


def _run(bars_a: list[Bar], bars_b: list[Bar]):
    market_gw = MockMarketGateway()
    market_gw.load_bars(bars_a + bars_b)
    trade_gw = MockTradeGateway(market_gateway=market_gw, initial_capital=1_000_000.0)
    app = BacktestAppService(
        market_gateway=market_gw, trade_gateway=trade_gw,
        strategy=_BuyOnceHold(), evaluator=PerformanceEvaluator(),
    )
    reports = app.run_backtest(
        symbols=["600A00.SH", "600B00.SH"],
        start_date=_BASE, end_date=bars_a[-1].timestamp,
        base_timeframe=Timeframe.DAY_1,
    )
    return reports[0], trade_gw


def test_delisted_position_liquidated_on_last_bar_day():
    bars_a = _bars("600A00.SH", 30)
    bars_b = _bars("600B00.SH", 15, price=8.0)   # 第 15 天后断流 = 退市

    report, trade_gw = _run(bars_a, bars_b)

    sells_b = [t for t in trade_gw.list_trade_records()
               if t.symbol == "600B00.SH" and t.direction == OrderDirection.SELL]
    assert sells_b, "退市股必须在末根日被强平卖出"
    liq = sells_b[-1]
    assert liq.execute_at.date() == bars_b[-1].timestamp.date()  # 末根日当日
    assert abs(liq.price - bars_b[-1].close) / bars_b[-1].close < 0.005  # 按末根收盘(容滑点)
    assert liq.remark.startswith("delisted-liquidation")  # 标记透传, 供敏感性统计辨识强平

    positions = {p.ticker: p for p in trade_gw.get_positions()}
    assert positions.get("600B00.SH") is None or positions["600B00.SH"].total_volume == 0
    assert positions["600A00.SH"].total_volume > 0  # 活股不受影响


def test_all_alive_no_liquidation():
    """活股宇宙(末根=回测末日)零强平 — 既有行为回归。"""
    bars_a = _bars("600A00.SH", 30)
    bars_b = _bars("600B00.SH", 30, price=8.0)

    report, trade_gw = _run(bars_a, bars_b)

    buys = [t for t in trade_gw.list_trade_records()
            if t.direction == OrderDirection.BUY]
    assert len(buys) >= 2  # 前置: 两只都确实买入(防平凡通过)
    sells = [t for t in trade_gw.list_trade_records()
             if t.direction == OrderDirection.SELL]
    assert sells == []  # BuyOnceHold 从不卖出, 也不得被强平


def test_no_zombie_value_after_liquidation():
    """强平后净值无僵尸市值: 终值 = 现金 + 活股市值, 与 B 末价无关。"""
    bars_a = _bars("600A00.SH", 30)
    bars_b = _bars("600B00.SH", 15, price=8.0)

    report, trade_gw = _run(bars_a, bars_b)

    asset = trade_gw.get_asset()
    positions = {p.ticker: p for p in trade_gw.get_positions()}
    market_value_a = positions["600A00.SH"].total_volume * bars_a[-1].close
    # 终值应≈可用现金+冻结现金+A 市值(B 已变现, 无残留市值项)
    assert abs(asset.total_asset - (asset.available_cash + asset.frozen_cash + market_value_a)) < 1.0
