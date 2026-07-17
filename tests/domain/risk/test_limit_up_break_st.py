"""LimitUpBreakPolicy 注入 is_st_fn 后, ST 股按 5% 涨停价判破板(设计 0711-st-honesty §4.3)。"""
from datetime import datetime

from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.risk.services.risk_policies.limit_up_break_policy import LimitUpBreakPolicy

D = datetime(2023, 1, 3)


def _pos():
    return Position(account_id="A", ticker="000021.SZ",
                    total_volume=100, available_volume=100, average_cost=10.0)


def _bar(high, close):
    return Bar(symbol="000021.SZ", timeframe=Timeframe.DAY_1, timestamp=D,
               open=10.0, high=high, low=9.9, close=close, volume=1000.0,
               prev_close=10.0)


def test_st_5pct_limit_touched_and_broken_triggers_sell():
    policy = LimitUpBreakPolicy(is_st_fn=lambda sym, ts: True)
    # 5% 涨停 10.5: 高点触及、收盘回落 → 破板卖出
    signals = policy.evaluate_positions([_pos()], {"000021.SZ": _bar(high=10.5, close=10.2)})
    assert len(signals) == 1


def test_same_bar_without_st_fn_no_signal():
    policy = LimitUpBreakPolicy()
    # 普通 10% 涨停 11.0: 高点 10.5 未触及 → 无信号(既有行为回归)
    signals = policy.evaluate_positions([_pos()], {"000021.SZ": _bar(high=10.5, close=10.2)})
    assert signals == []
