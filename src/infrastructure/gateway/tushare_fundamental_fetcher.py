import bisect
from datetime import datetime

import pandas as pd

from src.domain.market.interfaces.gateways.fundamental_fetcher import IFundamentalFetcher
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot

try:
    import tushare as ts
except ImportError:
    ts = None


class TushareFundamentalFetcher(IFundamentalFetcher):
    def __init__(self, token: str | None = None) -> None:
        self.token = token
        if self.token and ts:
            ts.set_token(self.token)
            self.pro = ts.pro_api()
        else:
            self.pro = None

    def fetch_by_range(
        self, start_date: str, end_date: str
    ) -> list[FundamentalSnapshot]:
        """批量预加载指定区间的基本面数据。"""
        if not ts or not self.pro:
            raise ImportError("tushare module not found or TUSHARE_TOKEN not set.")

        ts_start = start_date.replace("-", "")
        ts_end = end_date.replace("-", "")

        print(f"Downloading fundamental data from Tushare ({start_date} to {end_date})...")

        # 1. 股票基本信息 (stock_basic)
        df_basic = self.pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,list_date')
        if df_basic is None or df_basic.empty:
            return []

        # 将 list_date 转换为 datetime
        df_basic['list_date'] = pd.to_datetime(df_basic['list_date'], format='%Y%m%d', errors='coerce')
        basic_dict = df_basic.set_index('ts_code').to_dict('index')

        # 2. 每日指标 (daily_basic) 获取市值
        # 为了不超限频，只拉取这段时间的横截面快照数据
        df_daily_basic = self.pro.daily_basic(
            ts_code='', start_date=ts_start, end_date=ts_end, fields='ts_code,trade_date,total_mv,pe_ttm,pb'
        )
        if df_daily_basic is None or df_daily_basic.empty:
            return []

        # 3. 财务指标 (fina_indicator) 获取 roe, ocf
        # 实际生产中应循环或分批获取，这里简化拉取
        df_fina = self.pro.fina_indicator(
            start_date=ts_start, end_date=ts_end, fields='ts_code,ann_date,roe_ttm,ocf_ttm'
        )

        # 按 (symbol, ann_date) 构建财务数据索引，避免未来函数
        # fina_by_sym[sym] = (sorted_ann_dates: list[str], data_list: list[dict])
        fina_by_sym: dict[str, tuple[list[str], list[dict]]] = {}
        if df_fina is not None and not df_fina.empty:
            df_fina = df_fina.sort_values(by=['ts_code', 'ann_date'])
            for sym, group in df_fina.groupby('ts_code'):
                dates: list[str] = []
                data_list: list[dict] = []
                for _, row in group.iterrows():
                    dates.append(row['ann_date'])
                    data_list.append({
                        "roe_ttm": row['roe_ttm'] if pd.notna(row['roe_ttm']) else None,
                        "ocf_ttm": row['ocf_ttm'] if pd.notna(row['ocf_ttm']) else None,
                    })
                fina_by_sym[sym] = (dates, data_list)

        snapshots = []
        for _, row in df_daily_basic.iterrows():
            symbol = row['ts_code']
            if symbol not in basic_dict:
                continue

            info = basic_dict[symbol]
            list_date = info['list_date']
            if pd.isna(list_date):
                continue

            # 查找 ann_date <= trade_date 的最近一条财务数据
            fina_info: dict = {}
            if symbol in fina_by_sym:
                dates, data_list = fina_by_sym[symbol]
                idx = bisect.bisect_right(dates, row['trade_date'])
                if idx > 0:
                    fina_info = data_list[idx - 1]

            snapshot = FundamentalSnapshot(
                symbol=symbol,
                date=datetime.strptime(row['trade_date'], "%Y%m%d"),
                name=info['name'],
                list_date=list_date.to_pydatetime(),
                market_cap=row['total_mv'] * 10000,  # 万转元
                roe_ttm=fina_info.get("roe_ttm"),
                ocf_ttm=fina_info.get("ocf_ttm"),
                pe_ratio=row['pe_ttm'] if pd.notna(row.get('pe_ttm')) else None,
                pb_ratio=row['pb'] if pd.notna(row.get('pb')) else None,
            )
            snapshots.append(snapshot)

        return snapshots


