"""QMT 基本面数据获取器实现（基于 xtquant.xtdata）。

平替 TushareFundamentalFetcher，完全使用 QMT 本地数据源。
数据口径说明：
- equity_roe: 加权净资产收益率（季报原始值，非 TTM 滚动）
- s_fa_ocfps: 每股经营现金流（季报原始值，非 TTM 滚动）
- market_cap: close_price × TotalVolume（实时计算，TotalVolume 来自合约详情）
"""

from datetime import datetime
from threading import Event

import pandas as pd

from src.domain.market.interfaces.gateways.fundamental_fetcher import IFundamentalFetcher, IIndexDataFetcher
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot

from .xtquant_client import xtdata


class QmtFundamentalFetcher(IFundamentalFetcher, IIndexDataFetcher):
    """QMT 基本面数据获取器。

    数据来源：
    - 股票名称/上市日期/总股本: get_instrument_detail
    - ROE/OCF/EPS: get_financial_data → PershareIndex
    - 收盘价: get_market_data_ex（用于计算总市值）
    - 指数日线: get_market_data_ex
    """

    # 所需的财务报表
    _TABLE_LIST = ['PershareIndex']

    def fetch_by_range(
        self, start_date: str, end_date: str, symbols: list[str] | None = None
    ) -> list[FundamentalSnapshot]:
        """批量预加载指定区间的基本面数据。

        以 ann_date（公告日期）为时间轴，杜绝未来函数。

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            symbols: 指定股票列表。为 None 时拉取全市场。
        """
        qmt_start = start_date.replace("-", "")
        qmt_end = end_date.replace("-", "")

        # 1. 获取股票列表
        if symbols is None:
            symbols = []
            for sector in ['沪深A股']:
                try:
                    symbols.extend(xtdata.get_stock_list_in_sector(sector))
                except Exception:
                    pass
            if not symbols:
                print("[QmtFundamentalFetcher] Failed to get stock list, falling back to empty.")
                return []
        symbols = sorted(set(symbols))
        print(f"[QmtFundamentalFetcher] Fetching fundamentals for {len(symbols)} stocks "
              f"({start_date} ~ {end_date})...")

        # 2. 财务数据: 直接获取（QMT 本地已有，无需下载）
        # 注意: download_financial_data 同步版会卡死，已跳过

        # 3. 获取合约详情（股票名称、上市日期、总股本）
        instrument_map: dict[str, dict] = {}
        for sym in symbols:
            detail = xtdata.get_instrument_detail(sym)
            if detail:
                instrument_map[sym] = detail
        print(f"[QmtFundamentalFetcher] Loaded {len(instrument_map)} instrument details.")

        # 4. 批量下载历史数据 + 获取收盘价（用于计算总市值）
        close_map: dict[str, dict[str, float]] = {}
        trading_date_strs: list[str] = []
        batch_size = 200
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            # 必须先下载历史数据，否则 get_market_data_ex 返回空
            for sym in batch:
                try:
                    xtdata.download_history_data(
                        stock_code=sym, period='1d',
                        start_time=qmt_start, end_time=qmt_end,
                    )
                except Exception:
                    pass
            try:
                data = xtdata.get_market_data_ex(
                    field_list=['close'],
                    stock_list=batch,
                    period='1d',
                    start_time=qmt_start,
                    end_time=qmt_end,
                    dividend_type='none',
                    fill_data=False,
                )
                for sym in batch:
                    if sym in data and not data[sym].empty:
                        df = data[sym]
                        close_map[sym] = dict(zip(df.index, df['close']))
                        # 从第一批有数据的股票提取交易日历
                        if not trading_date_strs:
                            trading_date_strs = sorted(df.index.tolist())
            except Exception:
                pass
        if not trading_date_strs:
            print("[QmtFundamentalFetcher] No trading dates found, returning empty.")
            return []
        print(f"[QmtFundamentalFetcher] Loaded close prices for {len(close_map)} stocks, "
              f"{len(trading_date_strs)} trading days.")

        # 6. 获取财务数据（PershareIndex）
        fina_map: dict[str, list[tuple[str, dict]]] = {}
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            try:
                fin = xtdata.get_financial_data(
                    stock_list=batch,
                    table_list=self._TABLE_LIST,
                    start_time='',
                    end_time='',
                    report_type='announce_time',
                )
                for sym in batch:
                    if sym in fin and 'PershareIndex' in fin[sym]:
                        df = fin[sym]['PershareIndex']
                        if isinstance(df, pd.DataFrame) and not df.empty:
                            entries = []
                            for _, row in df.iterrows():
                                ann_time = str(row.get('m_anntime', ''))
                                if not ann_time or ann_time == 'nan':
                                    continue
                                metrics = {}
                                for field in ['equity_roe', 's_fa_ocfps', 's_fa_eps_basic',
                                              's_fa_bps', 'gear_ratio', 'net_roe', 'total_roe',
                                              'du_return_on_equity', 'gross_profit', 'net_profit',
                                              'inc_revenue_rate', 'inc_net_profit_rate',
                                              'sales_cash_flow', 'inventory_turnover']:
                                    val = row.get(field)
                                    if pd.notna(val):
                                        metrics[field] = float(val)
                                if metrics:
                                    entries.append((ann_time, metrics))
                            if entries:
                                entries.sort(key=lambda x: x[0])
                                fina_map[sym] = entries
            except Exception:
                pass
        print(f"[QmtFundamentalFetcher] Loaded financial data for {len(fina_map)} stocks.")

        # 7. 组装 FundamentalSnapshot
        snapshots: list[FundamentalSnapshot] = []
        for sym in symbols:
            detail = instrument_map.get(sym)
            if not detail:
                continue

            name = detail.get('InstrumentName', '')
            open_date_raw = str(detail.get('OpenDate', '0'))
            if open_date_raw and open_date_raw != '0':
                try:
                    list_date = datetime.strptime(open_date_raw, '%Y%m%d')
                except ValueError:
                    list_date = datetime(1990, 1, 1)
            else:
                list_date = datetime(1990, 1, 1)

            total_volume = float(detail.get('TotalVolume', 0) or 0)

            sym_close = close_map.get(sym, {})
            sym_fina = fina_map.get(sym, [])
            fina_idx = 0

            for td in trading_date_strs:
                close_price = sym_close.get(td)
                if close_price is None or close_price <= 0:
                    continue

                # 推进财务指标指针到该交易日之前（含当日）公告的最新数据
                while fina_idx < len(sym_fina) and sym_fina[fina_idx][0] <= td:
                    fina_idx += 1
                latest_idx = fina_idx - 1

                metrics = sym_fina[latest_idx][1] if latest_idx >= 0 else {}

                market_cap = close_price * total_volume

                # 计算 PB/PE
                bps = metrics.get('s_fa_bps')
                eps = metrics.get('s_fa_eps_basic')
                pb_ratio = (close_price / bps) if bps and bps > 0 else None
                pe_ratio = (close_price / eps) if eps and eps > 0 else None

                snapshots.append(FundamentalSnapshot(
                    symbol=sym,
                    date=datetime.strptime(td, '%Y%m%d'),
                    name=name,
                    list_date=list_date,
                    market_cap=market_cap,
                    roe_ttm=metrics.get('equity_roe'),
                    ocf_ttm=metrics.get('s_fa_ocfps'),
                    pe_ratio=pe_ratio,
                    pb_ratio=pb_ratio,
                ))

        print(f"[QmtFundamentalFetcher] Generated {len(snapshots)} snapshots.")
        return snapshots

    def fetch_index_daily(
        self, index_symbol: str, start_date: str, end_date: str
    ) -> list[dict]:
        """获取指数日线数据（复用 QMT 行情接口）。"""
        qmt_start = start_date.replace("-", "")
        qmt_end = end_date.replace("-", "")

        # 下载历史数据
        try:
            xtdata.download_history_data(
                stock_code=index_symbol,
                period='1d',
                start_time=qmt_start,
                end_time=qmt_end,
            )
        except Exception:
            pass

        data = xtdata.get_market_data_ex(
            field_list=['open', 'high', 'low', 'close', 'volume'],
            stock_list=[index_symbol],
            period='1d',
            start_time=qmt_start,
            end_time=qmt_end,
            dividend_type='none',
            fill_data=False,
        )

        if index_symbol not in data or data[index_symbol].empty:
            return []

        df = data[index_symbol].sort_index()
        results = []
        for idx, row in df.iterrows():
            results.append({
                "trade_date": str(idx),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": float(row['volume']),
            })
        return results

    @staticmethod
    def _download_financial(symbols: list[str]) -> None:
        """异步批量下载财务数据（使用 download_financial_data2，避免阻塞）。"""
        done = Event()

        def callback(data):
            if data.get('finished', 0) == data.get('total', 1) or data.get('finished') is True:
                done.set()

        batch_size = 200
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            try:
                xtdata.download_financial_data2(stock_list=batch, callback=callback)
                if not done.wait(timeout=300):
                    print(f"[QmtFundamentalFetcher] Warning: financial download batch "
                          f"{i // batch_size + 1} timed out.")
                done.clear()
            except Exception as e:
                print(f"[QmtFundamentalFetcher] Warning: financial download failed: {e}")
