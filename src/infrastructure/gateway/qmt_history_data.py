import os
import pandas as pd
from datetime import datetime
from pathlib import Path
from src.domain.market.interfaces.gateways.history_fetcher import IHistoryDataFetcher
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe

try:
    from xtquant import xtdata
except ImportError:
    xtdata = None

class QmtHistoryDataFetcher(IHistoryDataFetcher):
    """QMT 历史数据获取器实现。"""

    def fetch_history_bars(
        self, 
        symbol: str, 
        timeframe: Timeframe, 
        start_date: str, 
        end_date: str
    ) -> list[Bar]:
        """获取历史 K 线数据。

        优先从本地 CSV 读取，若不存在则调用 xtdata 下载并保存。
        """
        # 1. 构造缓存路径
        # 确保 data 目录存在
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        
        csv_filename = f"{symbol}_{timeframe.value}.csv"
        csv_path = data_dir / csv_filename

        df = None
        
        # 2. 检查缓存是否存在
        if csv_path.exists():
            try:
                # 尝试读取 CSV
                # 假设 CSV 包含 datetime, open, high, low, close, volume 等列
                # 注意: 这里简单假设文件存在即包含所需数据，实际生产中可能需要校验时间范围覆盖
                # 为简化逻辑，若文件存在直接读取，若需更新数据可手动删除文件或增强逻辑
                df = pd.read_csv(csv_path)
                
                # 转换 datetime 列
                if 'time' in df.columns:
                     df['datetime'] = pd.to_datetime(df['time'])
                elif 'datetime' in df.columns:
                     df['datetime'] = pd.to_datetime(df['datetime'])
                
                # 筛选时间范围
                # 统一 start_date/end_date 格式处理
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                
                mask = (df['datetime'] >= start_dt) & (df['datetime'] <= end_dt)
                if not mask.any():
                    # 缓存中没有所需时间段的数据，可能需要重新下载
                    # 这里简化处理：如果缓存存在但没有数据，尝试重新下载覆盖 (或者追加? 简单起见覆盖)
                    print(f"Cache miss for time range in {csv_path}, re-downloading...")
                    df = None
                else:
                    df = df[mask]
            except Exception as e:
                print(f"Error reading cache {csv_path}: {e}, re-downloading...")
                df = None

        # 3. 若无缓存或读取失败，从 QMT 获取
        if df is None:
            if xtdata is None:
                raise ImportError("xtquant module not found. Please install it or use cached data.")
            
            # 下载数据
            # xtdata.download_history_data 的 period 参数即 timeframe.value (如 '1d', '5m')
            # start_time, end_time 格式通常为 'YYYYMMDD' 或 'YYYYMMDDHHMMSS'
            # 这里的 start_date, end_date 是 'YYYY-MM-DD'，需要转换格式
            xt_start = start_date.replace("-", "")
            xt_end = end_date.replace("-", "")
            
            print(f"Downloading history data for {symbol} ({timeframe.value})...")
            xtdata.download_history_data(symbol, period=timeframe.value, start_time=xt_start, end_time=xt_end)
            
            # 获取数据 (前复权)
            # dividend_type="front"
            market_data = xtdata.get_market_data(
                field_list=[],  # 空列表获取所有字段
                stock_list=[symbol],
                period=timeframe.value,
                start_time=xt_start,
                end_time=xt_end,
                dividend_type="front",
                count=-1
            )
            
            # market_data 是一个 dict {symbol: DataFrame}
            if symbol not in market_data:
                 print(f"No data found for {symbol}")
                 return []
            
            df = market_data[symbol]
            
            if df.empty:
                print(f"Empty data for {symbol}")
                return []
            
            # 处理 DataFrame 列名和索引
            # xtdata 返回的 DataFrame index 通常是 time (int64 ms) 或 string
            # 列名通常是 open, high, low, close, volume, amount, ...
            
            # 重置索引以将 time 变为列 (如果它是索引)
            df = df.reset_index()
            
            # 确保有 datetime 列
            # xtdata 的 time 列通常是 毫秒时间戳 (int) 或 字符串
            # 常见的列名是 'time'
            if 'time' in df.columns:
                # 尝试转换 time 列
                # 如果是 int (ms)
                if pd.api.types.is_integer_dtype(df['time']):
                    df['datetime'] = pd.to_datetime(df['time'], unit='ms')
                else:
                    df['datetime'] = pd.to_datetime(df['time'])
            elif 'index' in df.columns: # sometimes reset_index creates 'index'
                 df['datetime'] = pd.to_datetime(df['index'])
            
            # 4. 落盘保存
            # 保存所有列，以便下次读取
            df.to_csv(csv_path, index=False)
            print(f"Saved history data to {csv_path}")

        # 5. 转换为 Bar 对象列表
        bars = []
        for _, row in df.iterrows():
            # 确保必要的字段存在
            # 假设列名: open, high, low, close, volume
            # 如果是 xtdata，通常是小写
            try:
                bar = Bar(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=row['datetime'].to_pydatetime(),
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume'])
                )
                bars.append(bar)
            except KeyError as e:
                print(f"Missing column in data for {symbol}: {e}")
                continue
                
        return bars
