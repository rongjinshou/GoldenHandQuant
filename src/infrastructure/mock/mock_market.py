from datetime import datetime
from src.domain.market.value_objects.bar import Bar
from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway

class MockMarketGateway(IMarketGateway):
    """基于内存的模拟行情网关。"""

    def __init__(self, initial_data: dict[str, list[Bar]] | None = None) -> None:
        """初始化模拟行情网关。

        Args:
            initial_data: 初始行情数据，键为 symbol，值为按时间升序排列的 Bar 列表。
        """
        self.data: dict[str, list[Bar]] = initial_data or {}
        self.current_time: datetime = datetime.min

    def set_current_time(self, dt: datetime) -> None:
        """设置当前模拟时间。"""
        self.current_time = dt

    def get_recent_bars(self, symbol: str, timeframe: str, limit: int) -> list[Bar]:
        """获取当前时间之前的 K 线切片。

        Args:
            symbol: 标的代码。
            timeframe: 周期 (暂时忽略，假设都是日线)。
            limit: 获取数量。

        Returns:
            list[Bar]: 切片后的 K 线列表。
        """
        if symbol not in self.data:
            return []

        all_bars = self.data[symbol]
        # 找到当前时间之前的 bars
        valid_bars = [bar for bar in all_bars if bar.timestamp <= self.current_time]
        
        # 返回最近的 limit 个
        return valid_bars[-limit:]

    def add_bars(self, symbol: str, bars: list[Bar]) -> None:
        """添加行情数据。"""
        if symbol not in self.data:
            self.data[symbol] = []
        self.data[symbol].extend(bars)
        # 确保按时间排序
        self.data[symbol].sort(key=lambda x: x.timestamp)
