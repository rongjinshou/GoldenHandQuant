from datetime import datetime
import pandas as pd
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
        self._current_time: datetime = datetime.min

    def set_current_time(self, dt: datetime) -> None:
        """设置当前模拟时间。"""
        self._current_time = dt

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
        # 找到当前时间之前的 bars (防偷看机制)
        valid_bars = [bar for bar in all_bars if bar.timestamp <= self._current_time]
        
        # 返回最近的 limit 个
        return valid_bars[-limit:]

    def load_data(self, df: pd.DataFrame) -> None:
        """从 DataFrame 加载数据。
        
        Args:
            df: 包含历史数据的 DataFrame，必须包含:
                datetime, symbol, open, high, low, close, volume
        """
        # 简单校验
        required_cols = {'datetime', 'symbol', 'open', 'high', 'low', 'close', 'volume'}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"DataFrame missing required columns: {missing}")

        # 按 symbol 分组处理，提高效率
        for symbol, group in df.groupby('symbol'):
            bars = []
            for _, row in group.iterrows():
                # 转换 datetime
                dt = row['datetime']
                if not isinstance(dt, datetime):
                    dt = pd.to_datetime(dt).to_pydatetime()
                    
                bars.append(Bar(
                    symbol=str(symbol),
                    timestamp=dt,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume'])
                ))
            
            # 排序并存储
            bars.sort(key=lambda x: x.timestamp)
            if symbol not in self.data:
                self.data[symbol] = []
            self.data[symbol].extend(bars)
            # 再次确保整体有序
            self.data[symbol].sort(key=lambda x: x.timestamp)

    def add_bars(self, symbol: str, bars: list[Bar]) -> None:
        """添加行情数据。"""
        if symbol not in self.data:
            self.data[symbol] = []
        self.data[symbol].extend(bars)
        # 确保按时间排序
        self.data[symbol].sort(key=lambda x: x.timestamp)
