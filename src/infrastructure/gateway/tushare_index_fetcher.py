import os

try:
    import tushare as ts
except ImportError:
    ts = None


class TushareIndexFetcher:
    """专门用于获取指数数据的 Fetcher。"""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.getenv("TUSHARE_TOKEN")
        if self.token and ts:
            ts.set_token(self.token)
            self.pro = ts.pro_api()
        else:
            self.pro = None

    def fetch_index_daily(
        self, index_symbol: str, start_date: str, end_date: str
    ) -> list[dict]:
        """获取指数日线数据。"""
        if not ts or not self.pro:
            raise ImportError("tushare module not found or TUSHARE_TOKEN not set.")

        ts_start = start_date.replace("-", "")
        ts_end = end_date.replace("-", "")

        df = self.pro.index_daily(ts_code=index_symbol, start_date=ts_start, end_date=ts_end)
        if df is None or df.empty:
            return []

        df = df.sort_values("trade_date", ascending=True)
        results = []
        for _, row in df.iterrows():
            results.append({
                "trade_date": row["trade_date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["vol"],
            })
        return results
