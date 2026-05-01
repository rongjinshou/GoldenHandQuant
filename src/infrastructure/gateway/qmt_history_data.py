import pandas as pd
from pathlib import Path
from src.domain.market.interfaces.gateways.history_fetcher import IHistoryDataFetcher
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe

from threading import Event

from .xtquant_client import xtdata

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
        4. 解决异步竞态：使用 download_history_data2 + callback 同步等待
        5. 确保复权准确：预先下载财务数据
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

            xtdata.download_financial_data(stock_list=[symbol])

            # 3.1 下载历史数据
            print(f"[{symbol}] Downloading history data ({timeframe.value})...")
            download_complete = Event()
            
            def _download_callback(data):
                # 修复回调死锁：只有当明确完成时才放行
                if data.get('finished', 0) == data.get('total', 1) or data.get('finished') is True:
                    download_complete.set()
            print(qmt_start_date)
            xtdata.download_history_data2(
                stock_list=[symbol],
                period=timeframe.value,
                start_time=qmt_start_date,
                end_time=qmt_end_date,
                callback=_download_callback
            )
            
            # 由于你之前提到不想用 download_financial_data 阻塞
            # 这里超时时间可以设短一点，比如 5-10 秒。
            # 60 秒还是太长了，如果本地缓存最新，它根本不触发回调，你得干等一分钟。
            if not download_complete.wait(timeout=60):
                print(f"[{symbol}] Notice: Data might be up-to-date or download timed out.")
            
            # 3.2 获取数据 (去掉 'time' 字段，防止冗余)
            field_list = ['open', 'high', 'low', 'close', 'volume']
            
            data_map = xtdata.get_market_data_ex(
                field_list=field_list,
                stock_list=[symbol],
                period=timeframe.value,
                start_time=qmt_start_date,
                end_time=qmt_end_date,
                dividend_type='front',
                fill_data=True
            )
            
            if symbol not in data_map or data_map[symbol].empty:
                print(f"No data found for {symbol} via QMT.")
                return []
                
            raw_df = data_map[symbol]
            
            # 3.3 数据清洗与格式化 (修复毫秒解析和导出格式)
            raw_df.index.name = 'datetime'
            try:
                # 针对 QMT 的毫秒时间戳特殊处理
                if raw_df.index.dtype == 'int64':
                    raw_df.index = pd.to_datetime(raw_df.index, unit='ms')
                else:
                    raw_df.index = pd.to_datetime(raw_df.index) 
            except Exception as e:
                print(f"[{symbol}] Error parsing dates: {e}")
            
            df = raw_df.reset_index()
            
            # 3.4 写入缓存
            df.to_csv(csv_path, index=False)

        # 4. 转换为实体对象列表
        bars = []
        if df is not None and not df.empty:
            # 确保按时间排序
            df = df.sort_values('datetime')

            # 获取不复权收盘价用于真实账本结算
            unadjusted_close_map: dict = {}
            try:
                unadj_map = xtdata.get_market_data_ex(
                    field_list=["close"],
                    stock_list=[symbol],
                    period=timeframe.value,
                    start_time=qmt_start_date,
                    end_time=qmt_end_date,
                    dividend_type="none",
                    fill_data=True,
                )
                if symbol in unadj_map and not unadj_map[symbol].empty:
                    unadj_series = unadj_map[symbol]["close"]
                    unadjusted_close_map = unadj_series.to_dict()
            except Exception:
                pass

            for _, row in df.iterrows():
                try:
                    # 转换 volume 为 int (根据用户要求)
                    vol = int(row['volume'])
                    ts = row['datetime']
                    unadj_close = float(unadjusted_close_map.get(ts, 0.0))

                    bar = Bar(
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=row['datetime'].to_pydatetime(),  # 转换为 python datetime
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=float(vol), # 实体定义是 float，但数值要是整数
                        unadjusted_close=unadj_close,
                    )
                    bars.append(bar)
                except (KeyError, ValueError) as e:
                    # print(f"Error parsing row for {symbol}: {e}")
                    continue
                    
        return bars
