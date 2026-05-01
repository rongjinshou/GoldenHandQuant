import os
import pandas as pd
from pathlib import Path
from src.domain.market.interfaces.gateways.history_fetcher import IHistoryDataFetcher
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe

try:
    import tushare as ts
except ImportError:
    ts = None


class TushareHistoryDataFetcher(IHistoryDataFetcher):
    """Tushare 历史数据获取器实现。"""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.getenv("TUSHARE_TOKEN")
        if self.token and ts:
            ts.set_token(self.token)
            self.pro = ts.pro_api()
        else:
            self.pro = None

    def fetch_history_bars(
        self, 
        symbol: str, 
        timeframe: Timeframe, 
        start_date: str, 
        end_date: str
    ) -> list[Bar]:
        """获取历史 K 线数据。

        优先从本地 CSV 读取，若不存在或数据缺失则调用 Tushare 下载并保存。
        遵循前复权规范 (adj='qfq')。
        """
        # 1. 构造缓存路径
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        
        csv_filename = f"{symbol}_{timeframe.value}_tushare.csv"
        csv_path = data_dir / csv_filename

        pd_start_dt = pd.to_datetime(start_date)
        pd_end_dt = pd.to_datetime(end_date)

        df = None
        
        # 2. 尝试读取本地缓存
        if csv_path.exists():
            try:
                cached_df = pd.read_csv(csv_path)
                if "datetime" in cached_df.columns:
                    cached_df["datetime"] = pd.to_datetime(cached_df["datetime"])
                    mask = (cached_df["datetime"] >= pd_start_dt) & (cached_df["datetime"] <= pd_end_dt)
                    if mask.any():
                        df = cached_df[mask].copy()
                    else:
                        df = None
                else:
                    df = None
            except Exception as e:
                print(f"Error reading cache {csv_path}: {e}, re-downloading...")
                df = None

        # 3. 调用 Tushare 接口下载
        if df is None:
            if not ts or not self.pro:
                raise ImportError("tushare module not found or TUSHARE_TOKEN not set. Please set the token or use cached data.")

            print(f"[{symbol}] Downloading history data from Tushare ({timeframe.value})...")
            
            # Tushare format: YYYYMMDD
            ts_start_date = start_date.replace("-", "")
            ts_end_date = end_date.replace("-", "")
            
            freq_map = {
                Timeframe.DAY_1: "D",
                Timeframe.MIN_1: "1min",
                Timeframe.MIN_5: "5min",
                Timeframe.MIN_15: "15min",
                Timeframe.MIN_30: "30min",
                Timeframe.HOUR_1: "60min",
            }
            freq = freq_map.get(timeframe)
            if not freq:
                raise ValueError(f"Unsupported timeframe for Tushare: {timeframe}")

            # pro_bar requires ts_code, start_date, end_date, freq, adj
            # Tushare expects symbol like 000001.SZ or 600000.SH which matches our domain
            try:
                df = ts.pro_bar(
                    ts_code=symbol, 
                    start_date=ts_start_date, 
                    end_date=ts_end_date, 
                    freq=freq, 
                    adj="qfq"
                )
            except Exception as e:
                print(f"Tushare API error: {e}")
                return []

            if df is None or df.empty:
                print(f"Warning: No data returned from Tushare for {symbol} between {start_date} and {end_date}.")
                return []

            # pro_bar returns desc order (latest first), we need asc
            if "trade_time" in df.columns:
                date_col = "trade_time"
            elif "trade_date" in df.columns:
                date_col = "trade_date"
            else:
                raise ValueError(f"Unknown date column in Tushare response: {df.columns}")

            df = df.sort_values(date_col, ascending=True)

            # Rename columns to our standard
            df = df.rename(columns={
                date_col: "datetime",
                "ts_code": "symbol",
                "vol": "volume"
            })
            
            # Convert datetime string to datetime object
            df["datetime"] = pd.to_datetime(df["datetime"])

            # Cache the full downloaded data
            save_df = df[["datetime", "symbol", "open", "high", "low", "close", "volume"]]
            save_df.to_csv(csv_path, index=False)

        # 4. 转换为 Bar 对象列表
        bars = []
        for _, row in df.iterrows():
            bars.append(Bar(
                symbol=str(row["symbol"]),
                timeframe=timeframe,
                timestamp=row["datetime"].to_pydatetime() if isinstance(row["datetime"], pd.Timestamp) else row["datetime"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"])
            ))
            
        return bars
