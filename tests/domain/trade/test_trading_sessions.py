"""trading_sessions 测试（2026-07-10 六西格玛体检 D5 — 补零覆盖实盘模块）。

时段单一真相源(债 D3 收敛产物)决定「什么时候允许下单」, 此前 0 覆盖。
边界值(9:30/11:30/13:00/15:00/9:25)按闭区间语义逐一钉死。
"""

from datetime import datetime

from src.domain.trade.services.trading_sessions import (
    is_continuous_session,
    is_scheduler_session,
)


def _at(h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 7, 8, h, m, s)  # 周三


class TestContinuousSession:
    def test_morning_and_afternoon_sessions_inclusive_bounds(self):
        assert is_continuous_session(_at(9, 30))       # 开盘边界(含)
        assert is_continuous_session(_at(11, 30))      # 午盘收边界(含)
        assert is_continuous_session(_at(13, 0))       # 午后开边界(含)
        assert is_continuous_session(_at(15, 0))       # 收盘边界(含)
        assert is_continuous_session(_at(10, 15))
        assert is_continuous_session(_at(14, 59, 59))

    def test_outside_sessions_rejected(self):
        assert not is_continuous_session(_at(9, 29, 59))    # 集合竞价尾
        assert not is_continuous_session(_at(11, 30, 1))    # 午休
        assert not is_continuous_session(_at(12, 30))
        assert not is_continuous_session(_at(15, 0, 1))     # 收盘后
        assert not is_continuous_session(_at(1, 11))        # 凌晨(2026-06-30 冒烟实录被拒时段)


class TestSchedulerSession:
    def test_scheduler_opens_five_minutes_early(self):
        assert is_scheduler_session(_at(9, 25))        # 预备期开始
        assert is_scheduler_session(_at(9, 29))
        assert not is_continuous_session(_at(9, 29))   # 预备期可备不可下单

    def test_scheduler_rejects_before_prep(self):
        assert not is_scheduler_session(_at(9, 24, 59))
        assert not is_scheduler_session(_at(15, 0, 1))
