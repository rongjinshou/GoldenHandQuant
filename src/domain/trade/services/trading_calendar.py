"""交易日历 — 从 bars 历史推导的休市判定（2026-07-10 六西格玛 M7, 决策项 Q8）。

为什么不用静态节假日表: 放假安排逐年发布、调休复杂, 手工维护迟早写错;
而 bars 库本身就是权威历史日历(全市场有 bar 的日子 = 交易日)。

语义(三值, 保守设计):
- 已知范围内(d <= known_until): 精确判定 True/False;
- 未来日期: 返回 None(unknown) —— 调用方放行, 由报价新鲜度闸(180s)兜底;
  数据越新鲜, 日历盲区越小, 而新鲜度本身有 `data status --check` 门禁保障。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(slots=True, frozen=True)
class TradingCalendar:
    trading_days: frozenset[date]
    known_until: date

    @classmethod
    def from_dates(cls, dates: list[date]) -> TradingCalendar | None:
        """从 bars 的 distinct 日期列表构建; 空列表返回 None(无日历可用)。"""
        if not dates:
            return None
        return cls(trading_days=frozenset(dates), known_until=max(dates))

    def is_trading_day(self, d: date) -> bool | None:
        """已知范围内精确判定; 超出范围返回 None(unknown)。"""
        if d > self.known_until:
            return None
        return d in self.trading_days
