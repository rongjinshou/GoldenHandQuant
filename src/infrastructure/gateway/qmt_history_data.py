import json
from pathlib import Path

import pandas as pd

from src.domain.market.interfaces.gateways.history_fetcher import IHistoryDataFetcher
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe

from .xtquant_client import xtdata

# 下载元数据: {f"{symbol}_{timeframe}": 已完整下载过的最早 requested start}。
# 用途: 晚上市股票的缓存起点(上市日)天然晚于请求 start, 仅凭数据无法区分
# "缓存残缺"和"就只有这么多" -> 以 meta 记录的已履约 start 为准, 避免每次重拉。
_FETCH_META_NAME = "_fetch_meta.json"


def _load_fetch_meta(data_dir: Path) -> dict[str, str]:
    try:
        return json.loads((data_dir / _FETCH_META_NAME).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_fetch_meta(data_dir: Path, meta: dict[str, str]) -> None:
    try:
        (data_dir / _FETCH_META_NAME).write_text(
            json.dumps(meta, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
    except Exception as e:
        print(f"Warning: failed to save fetch meta: {e}")


class QmtHistoryDataFetcher(IHistoryDataFetcher):
    """QMT 历史数据获取器实现 (基于 xtquant.xtdata)。

    T2(2026-07-11, 台账 P6): CSV 透明缓存**默认退役**——QMT 客户端本地行情库
    (download_history_data 幂等)与 market.duckdb(fetch_meta 表)已是两级存储,
    中间 CSV 层是第三份冗余, 且其 `_fetch_meta.json` 与 DuckDB `fetch_meta`
    形成两套各说各话的履约账本。无 DuckDB 的轻量用途可显式 `csv_cache=True`。
    """

    def __init__(self, csv_cache: bool = False, data_dir: str = "data") -> None:
        self._csv_cache = csv_cache
        self._data_dir = Path(data_dir)

    def fetch_history_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_date: str,
        end_date: str
    ) -> list[Bar]:
        """获取历史 K 线数据。

        默认直连 xtdata(QMT 本地库幂等下载); csv_cache=True 时优先读本地 CSV。
        遵循 QMT 实盘接口规范：
        1. 时间格式转换 (YYYY-MM-DD -> YYYYMMDD)
        2. 使用 get_market_data_ex 获取标准数据结构
        3. 强制前复权 (dividend_type='front')
        4. 解决异步竞态：使用 download_history_data2 + callback 同步等待
        5. 确保复权准确：预先下载财务数据
        """
        # 1. 构造缓存路径
        data_dir = self._data_dir
        if self._csv_cache:
            data_dir.mkdir(parents=True, exist_ok=True)

        meta_key = f"{symbol}_{timeframe.value}"
        csv_path = data_dir / f"{meta_key}.csv"

        # 统一处理时间格式
        # 输入格式: YYYY-MM-DD
        # QMT 要求格式: YYYYMMDD
        qmt_start_date = start_date.replace("-", "")
        qmt_end_date = end_date.replace("-", "")

        # Pandas 过滤用的 datetime 对象
        pd_start_dt = pd.to_datetime(start_date)
        pd_end_dt = pd.to_datetime(end_date)

        df = None

        # 2. 尝试读取本地缓存(仅显式开启时)
        if self._csv_cache and csv_path.exists():
            try:
                # 读取 CSV，解析 datetime 列
                cached_df = pd.read_csv(csv_path)

                if 'datetime' in cached_df.columns:
                    cached_df['datetime'] = pd.to_datetime(cached_df['datetime'])

                    # 缓存必须"新鲜到请求的 end"且"回溯到请求的 start"才可用，
                    # 否则重拉完整区间。
                    # 旧逻辑只看 mask.any()（区间内有任意一根 K 线就命中），
                    # 会把沙盒期遗留的残缺缓存当成命中 -> 请求多年却只回放那几个月。
                    in_range = cached_df[
                        (cached_df['datetime'] >= pd_start_dt)
                        & (cached_df['datetime'] <= pd_end_dt)
                    ]
                    cache_reaches_end = (
                        not cached_df.empty
                        and cached_df['datetime'].max() >= pd_end_dt
                    )
                    # start 侧: 数据回溯到 start, 或 meta 确认曾按该 start
                    # (或更早) 完整拉取过 (晚上市股票数据天然到不了 start)
                    cache_covers_start = (
                        not cached_df.empty
                        and (
                            cached_df['datetime'].min() <= pd_start_dt
                            or _load_fetch_meta(data_dir).get(
                                meta_key, "9999-99-99"
                            ) <= start_date
                        )
                    )

                    if not in_range.empty and cache_reaches_end and cache_covers_start:
                        # 缓存完整覆盖请求区间，使用缓存 (截取所需片段)
                        df = in_range.copy()
                    else:
                        # 缓存残缺/过期 (start 或 end 侧有缺口) -> 重新下载完整区间
                        df = None
                else:
                    # 格式不对，重新下载
                    df = None
            except Exception as e:
                print(f"Error reading cache {csv_path}: {e}, re-downloading...")
                df = None

        # 3. 调用 QMT 接口获取数据 (如果缓存未命中)
        if df is None:
            if xtdata is None:
                raise ImportError("xtquant module not found. Please install it or use cached data.")

            # 确保数据已下载（已缓存时 0.0s 完成）
            try:
                xtdata.download_history_data(
                    stock_code=symbol, period=timeframe.value,
                    start_time=qmt_start_date, end_time=qmt_end_date,
                )
            except Exception as e:
                # 不中断: get_market_data_ex 仍可能读到 QMT 本地已有数据
                print(f"Warning: download_history_data failed for {symbol}: {e}")

            field_list = ['open', 'high', 'low', 'close', 'volume']

            data_map = xtdata.get_market_data_ex(
                field_list=field_list,
                stock_list=[symbol],
                period=timeframe.value,
                start_time=qmt_start_date,
                end_time=qmt_end_date,
                dividend_type='front',
                fill_data=False,
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

            # 3.4 写入缓存 + 记录本次履约的 requested start (仅显式开启时)
            if self._csv_cache:
                df.to_csv(csv_path, index=False)
                meta = _load_fetch_meta(data_dir)
                if start_date < meta.get(meta_key, "9999-99-99"):
                    meta[meta_key] = start_date
                    _save_fetch_meta(data_dir, meta)

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
                    fill_data=False,
                )
                if symbol in unadj_map and not unadj_map[symbol].empty:
                    unadj_series = unadj_map[symbol]["close"]
                    unadjusted_close_map = unadj_series.to_dict()
            except Exception as e:
                print(f"Warning: unadjusted close fetch failed for {symbol}: {e}; "
                      f"unadjusted_close=0.0")

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
                except (KeyError, ValueError):
                    # print(f"Error parsing row for {symbol}: {e}")
                    continue

        return bars

    def fetch(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, list[Bar]]:
        """批量获取多只标的的历史 K 线。"""
        result: dict[str, list[Bar]] = {}
        for sym in symbols:
            bars = self.fetch_history_bars(
                symbol=sym,
                timeframe=Timeframe.DAY_1,
                start_date=start_date,
                end_date=end_date,
            )
            if bars:
                result[sym] = bars
        return result
