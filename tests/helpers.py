"""测试共享工厂函数。

将各测试文件中重复定义的 _make_snapshot / _make_signal 等工厂函数
统一提取到此处，通过 **kwargs 适配不同测试场景。
"""
from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection


def make_snapshot(symbol: str, **kwargs) -> StockSnapshot:
    """创建测试用 StockSnapshot，所有必填字段提供合理默认值。

    Args:
        symbol: 证券代码。
        **kwargs: 覆盖任意 StockSnapshot 字段（如 pb_ratio=1.0, pe_ratio=10.0）。

    Returns:
        StockSnapshot 实例。
    """
    defaults = dict(
        symbol=symbol,
        date=datetime(2024, 1, 1),
        open=10.0,
        high=10.0,
        low=10.0,
        close=10.0,
        volume=1000.0,
        name=f"stock_{symbol}",
        list_date=datetime(2020, 1, 1),
        market_cap=1e10,
    )
    defaults.update(kwargs)
    return StockSnapshot(**defaults)


def make_signal(
    symbol: str = "600000.SH",
    direction: SignalDirection = SignalDirection.BUY,
    confidence: float = 0.8,
    strategy: str = "test",
) -> Signal:
    """创建测试用 Signal。"""
    return Signal(
        symbol=symbol,
        direction=direction,
        confidence_score=confidence,
        strategy_name=strategy,
    )
