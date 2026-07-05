"""交易时段定义 — 单一真相源。

解决债 D3: 调度器时段判断(9:25)与安全闸时段判断(9:30)用两套独立定义。
统一为连续竞价时段(9:30-11:30, 13:00-15:00), 调度器提前 5 分钟(9:25)
允许预备, 但下单仍受安全闸 9:30 限制。
"""

from __future__ import annotations

from datetime import datetime, time

# 连续竞价时段 (下单有效时段)
CONTINUOUS_SESSIONS: tuple[tuple[time, time], ...] = (
    (time(9, 30), time(11, 30)),
    (time(13, 0), time(15, 0)),
)

# 调度器预备时段 (比连续竞价提前 5 分钟, 用于行情预热/信号计算)
SCHEDULER_SESSIONS: tuple[tuple[time, time], ...] = (
    (time(9, 25), time(11, 30)),
    (time(13, 0), time(15, 0)),
)


def is_continuous_session(now: datetime) -> bool:
    """检查是否在连续竞价时段内 (下单有效)。"""
    t = now.time()
    return any(start <= t <= end for start, end in CONTINUOUS_SESSIONS)


def is_scheduler_session(now: datetime) -> bool:
    """检查是否在调度器时段内 (预备 + 连续竞价)。"""
    t = now.time()
    return any(start <= t <= end for start, end in SCHEDULER_SESSIONS)
