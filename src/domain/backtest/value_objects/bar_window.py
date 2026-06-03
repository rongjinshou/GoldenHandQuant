from dataclasses import dataclass

from src.domain.market.value_objects.bar import Bar


@dataclass(frozen=True, slots=True, kw_only=True)
class BarWindow:
    """从一段连续 bar 派生回测决策所需的价格视图,统一信息边界与成交时点。

    信息边界(info_bars)严格早于成交时点(exec_bar),消除前视偏差。
    这是将来 T+0 / 日内交易的单一职责扩展点。
    """

    info_bars: list[Bar]   # 决策可见:截至 T-1(不含成交 bar)
    exec_bar: Bar          # 成交 bar:T 日

    @property
    def exec_price(self) -> float:
        """成交参考价:T 日开盘价(前复权)。"""
        return self.exec_bar.open

    @property
    def mark_price(self) -> float:
        """估值价:T 日收盘价(前复权)。"""
        return self.exec_bar.close


def make_bar_window(recent: list[Bar]) -> BarWindow | None:
    """recent 需至少 2 根(>=1 根信息 + 1 根成交),否则返回 None 由调用方跳过。"""
    if len(recent) < 2:
        return None
    return BarWindow(info_bars=recent[:-1], exec_bar=recent[-1])
