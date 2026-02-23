from datetime import datetime
import pandas as pd
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway

class MockMarketGateway(IMarketGateway):
    """基于内存的模拟行情网关。"""

    def __init__(self, initial_data: dict[str, dict[Timeframe, list[Bar]]] | None = None) -> None:
        """初始化模拟行情网关。

        Args:
            initial_data: 初始行情数据，第一层 key 为 symbol，第二层 key 为 timeframe，值为按时间升序排列的 Bar 列表。
        """
        self.data: dict[str, dict[Timeframe, list[Bar]]] = initial_data or {}
        self._current_time: datetime = datetime.min

    def set_current_time(self, dt: datetime) -> None:
        """设置当前模拟时间。"""
        self._current_time = dt

    def get_recent_bars(self, symbol: str, timeframe: Timeframe, limit: int) -> list[Bar]:
        """获取当前时间之前的 K 线切片。

        Args:
            symbol: 标的代码。
            timeframe: K 线周期。
            limit: 获取数量。

        Returns:
            list[Bar]: 切片后的 K 线列表。
        """
        if symbol not in self.data or timeframe not in self.data[symbol]:
            return []

        all_bars = self.data[symbol][timeframe]
        # 找到当前时间之前的 bars (防偷看机制)
        valid_bars = [bar for bar in all_bars if bar.timestamp <= self._current_time]
        
        # 返回最近的 limit 个
        return valid_bars[-limit:]

    def load_bars(self, bars: list[Bar]) -> None:
        """批量加载 K 线数据。

        Args:
            bars: Bar 对象列表。
        """
        # 按 symbol 分组
        grouped_bars: dict[str, list[Bar]] = {}
        for bar in bars:
            if bar.symbol not in grouped_bars:
                grouped_bars[bar.symbol] = []
            grouped_bars[bar.symbol].append(bar)
        
        for symbol, symbol_bars in grouped_bars.items():
            self.add_bars(symbol, symbol_bars)

    def load_data(self, df: pd.DataFrame, timeframe: Timeframe = Timeframe.DAY_1) -> None:
        """从 DataFrame 加载数据。
        
        Args:
            df: 包含历史数据的 DataFrame，必须包含:
                datetime, symbol, open, high, low, close, volume
            timeframe: 数据周期，默认为日线。
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
                    timeframe=timeframe,
                    timestamp=dt,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume'])
                ))
            
            self.add_bars(str(symbol), bars)

    def add_bars(self, symbol: str, bars: list[Bar]) -> None:
        """添加行情数据。"""
        if not bars:
            return
            
        # 按 timeframe 分组
        for bar in bars:
            tf = bar.timeframe
            if symbol not in self.data:
                self.data[symbol] = {}
            if tf not in self.data[symbol]:
                self.data[symbol][tf] = []
            self.data[symbol][tf].append(bar)
        
        # 确保每个 timeframe 下的 bars 按时间排序
        for tf in self.data[symbol]:
            self.data[symbol][tf].sort(key=lambda x: x.timestamp)

    def get_all_timestamps(self, timeframe: Timeframe) -> list[datetime]:
        """获取指定周期下的所有去重时间戳。

        Args:
            timeframe: K 线周期。

        Returns:
            list[datetime]: 时间戳列表，按时间升序排列。
        """
        timestamps = set()
        for symbol_data in self.data.values():
            if timeframe in symbol_data:
                for bar in symbol_data[timeframe]:
                    timestamps.add(bar.timestamp)
        
        return sorted(list(timestamps))
