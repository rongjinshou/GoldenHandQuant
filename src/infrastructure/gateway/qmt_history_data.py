import pandas as pd
from datetime import datetime
from pathlib import Path
from src.domain.market.interfaces.gateways.history_fetcher import IHistoryDataFetcher
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe

try:
    from src.infrastructure.libs.xtquant import xtdata
except ImportError:
    xtdata = None

class QmtHistoryDataFetcher(IHistoryDataFetcher):
    """QMT 历史数据获取器实现 (基于 xtquant.xtdata)。"""

    def fetch_history_bars(
        self, 
        symbol: str, 
        timeframe: Timeframe, 
        start_date: str, 
        end_date: str
    ) -> list[Bar]:
        """获取历史 K 线数据。

        优先从本地 CSV 读取，若不存在或数据缺失则调用 xtdata 下载并保存。
        遵循 QMT 实盘接口规范：
        1. 时间格式转换 (YYYY-MM-DD -> YYYYMMDD)
        2. 使用 get_market_data_ex 获取标准数据结构
        3. 强制前复权 (dividend_type='front')
        """
        # 1. 构造缓存路径
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        
        csv_filename = f"{symbol}_{timeframe.value}.csv"
        csv_path = data_dir / csv_filename

        # 统一处理时间格式
        # 输入格式: YYYY-MM-DD
        # QMT 要求格式: YYYYMMDD
        qmt_start_date = start_date.replace("-", "")
        qmt_end_date = end_date.replace("-", "")
        
        # Pandas 过滤用的 datetime 对象
        pd_start_dt = pd.to_datetime(start_date)
        pd_end_dt = pd.to_datetime(end_date)

        df = None
        
        # 2. 尝试读取本地缓存
        if csv_path.exists():
            try:
                # 读取 CSV，解析 datetime 列
                cached_df = pd.read_csv(csv_path)
                
                if 'datetime' in cached_df.columns:
                    cached_df['datetime'] = pd.to_datetime(cached_df['datetime'])
                    
                    # 检查缓存数据是否覆盖请求的时间段
                    # 简单策略：检查缓存中是否有处于请求时间范围内的数据
                    # 更严格策略：检查 min(date) <= start 和 max(date) >= end (但考虑到停牌等因素，这里只做简单检查)
                    mask = (cached_df['datetime'] >= pd_start_dt) & (cached_df['datetime'] <= pd_end_dt)
                    
                    if mask.any():
                        # 有数据命中，使用缓存 (截取所需片段)
                        df = cached_df[mask].copy()
                        # print(f"Loaded {len(df)} bars from cache: {csv_path}")
                    else:
                        # 缓存存在但无匹配数据 (可能是时间段不重合)，需要重新下载
                        # print(f"Cache miss (time range mismatch) for {symbol}, re-downloading...")
                        df = None
                else:
                    # 格式不对，重新下载
                    df = None
            except Exception as e:
                print(f"Error reading cache {csv_path}: {e}, re-downloading...")
                df = None

        # 3. 调用 QMT 接口下载 (如果缓存未命中)
        if df is None:
            if xtdata is None:
                raise ImportError("xtquant module not found. Please install it or use cached data.")
            
            # 3.1 下载历史数据
            # print(f"Downloading history data for {symbol} ({timeframe.value})...")
            xtdata.download_history_data(
                stock_code=symbol, 
                period=timeframe.value, 
                start_time=qmt_start_date, 
                end_time=qmt_end_date
            )
            
            # 3.2 获取数据 (get_market_data_ex)
            # 必须使用 ex 接口以获取标准 DataFrame 结构
            # 字段: time, open, high, low, close, volume (amount, settl_price, etc. optional)
            field_list = ['time', 'open', 'high', 'low', 'close', 'volume']
            
            data_map = xtdata.get_market_data_ex(
                field_list=field_list,
                stock_list=[symbol],
                period=timeframe.value,
                start_time=qmt_start_date,
                end_time=qmt_end_date,
                dividend_type='front',  # 强制前复权
                fill_data=True
            )
            
            # data_map 结构: { "000001.SZ": DataFrame }
            if symbol not in data_map or data_map[symbol].empty:
                print(f"No data found for {symbol} via QMT.")
                return []
                
            raw_df = data_map[symbol]
            
            # 3.3 数据清洗与格式化
            # get_market_data_ex 返回的 DataFrame index 通常是时间戳 (int64 ms) 或 字符串
            # 必须强制转换为 datetime
            raw_df.index.name = 'datetime'
            # 这里的 index 可能是 "20230101093000" (str) 或 timestamp
            # 统一转换为 datetime 对象
            try:
                # 尝试智能推断格式
                raw_df.index = pd.to_datetime(raw_df.index)
            except Exception:
                # 如果失败，可能需要指定格式，视 QMT 版本而定，通常 to_datetime 足够智能
                pass
            
            # 重置索引，将 datetime 变为普通列，方便保存 CSV
            df = raw_df.reset_index()
            
            # 确保列名存在 (open, high, low, close, volume)
            # QMT 返回的列名通常就是 field_list 中的名字
            
            # 3.4 更新缓存 (覆盖写入)
            # 注意：这里直接覆盖了旧文件。如果需要增量更新，逻辑会更复杂。
            # 鉴于回测场景通常是一次性拉取一段，覆盖是可接受的。
            df.to_csv(csv_path, index=False)
            # print(f"Saved history data to {csv_path}")

        # 4. 转换为实体对象列表
        bars = []
        if df is not None and not df.empty:
            # 确保按时间排序
            df = df.sort_values('datetime')
            
            for _, row in df.iterrows():
                try:
                    # 转换 volume 为 int (根据用户要求)
                    vol = int(row['volume'])
                    
                    bar = Bar(
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=row['datetime'].to_pydatetime(),  # 转换为 python datetime
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=float(vol) # 实体定义是 float，但数值要是整数
                    )
                    bars.append(bar)
                except (KeyError, ValueError) as e:
                    # print(f"Error parsing row for {symbol}: {e}")
                    continue
                    
        return bars
