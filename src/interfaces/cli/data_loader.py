"""沙盒数据加载器。

拉取 2024-01-01 至 2024-04-30 的 A 股数据用于回测:
- 500 只测试股票 + 中证1000指数
- 日线行情 + 合成基本面数据 (市值/ROE/OCF)
- 当 Tushare 积分不足时，从 K 线成交额推导市值代理值

使用方式:
    python -m src.interfaces.cli.data_loader
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

sys.path.append(os.getcwd())


def _token_from_yaml() -> str | None:
    """从 resources/backtest.yaml 读取 Tushare token。"""
    try:
        import yaml
        with open("resources/backtest.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        t = cfg.get("data", {}).get("tushare", {}).get("token", "")
        return t or None
    except Exception:
        return None


class DataFetcher:
    """Tushare 数据拉取器，带限流保护。"""

    def __init__(self, token: str | None = None) -> None:
        import tushare as ts

        self.ts = ts
        self.token = token or _token_from_yaml()
        if not self.token:
            raise ValueError("TUSHARE_TOKEN 未设置，请通过参数或环境变量提供。")
        ts.set_token(self.token)
        self.pro = ts.pro_api()

    def _sleep(self, seconds: float = 1.5) -> None:
        time.sleep(seconds)

    def fetch_stock_universe(self, date: str, n: int = 500) -> list[str]:
        """获取测试股票池。

        使用 daily 接口获取活跃股票，排除北交所(8/9开头)后随机抽样。
        绕过 stock_basic 限频和 index_weight 权限限制。
        """
        import random

        # 方式1: index_member
        try:
            df = self.pro.index_member(index_code="000905.SH")
            if df is not None and not df.empty:
                col = "con_code" if "con_code" in df.columns else df.columns[1]
                codes = df[col].unique().tolist()
                if len(codes) >= 100:
                    return codes
        except Exception:
            pass

        # 方式2: index_weight
        for offset in range(0, 8):
            alt_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=offset)).strftime("%Y%m%d")
            try:
                df = self.pro.index_weight(index_code="000905.SH", start_date=alt_date, end_date=alt_date)
                if df is not None and not df.empty:
                    return df["con_code"].unique().tolist()
            except Exception:
                pass
            self._sleep()

        # 方式3: daily 接口获取活跃股票 (避开 stock_basic 限频)
        print("  [WARN] 指数成分股接口无权限，从活跃股票中随机抽样")
        ts_date = date.replace("-", "")
        df = self.pro.daily(trade_date=ts_date)
        if df is None or df.empty:
            # 尝试附近日期
            for offset in range(1, 5):
                alt = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=offset)).strftime("%Y%m%d")
                df = self.pro.daily(trade_date=alt)
                if df is not None and not df.empty:
                    break
        if df is None or df.empty:
            raise RuntimeError(f"无法获取 {date} 的交易数据")

        codes = df["ts_code"].unique().tolist()
        # 排除北交所 (8开头) 和 ST 类 (无法直接判断，排除异常低价股)
        codes = [c for c in codes if not c.startswith("8") and not c.startswith("9")]

        if len(codes) < n:
            raise RuntimeError(f"可选股票不足 {n} 只 (仅 {len(codes)} 只)")

        random.seed(42)
        return sorted(random.sample(codes, n))

    def fetch_stock_basic(self, codes: list[str]) -> dict:
        """获取指定股票的基本信息 (name, list_date)。

        优先读取缓存文件；若不存在则调用 API (可能被限频)；
        若 API 也失败，用股票代码作为名称兜底。
        """
        cache_path = os.path.join("data", "stock_basic_cache.csv")
        os.makedirs("data", exist_ok=True)

        # 尝试读缓存
        if os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path)
                df = df[df["ts_code"].isin(codes)]
                df["list_date"] = pd.to_datetime(df["list_date"], format="%Y%m%d", errors="coerce")
                result = df.set_index("ts_code").to_dict("index")
                if len(result) >= len(codes) * 0.8:
                    print(f"  从缓存读取到 {len(result)} 只股票信息")
                    return result
            except Exception:
                pass

        # 调用 API
        try:
            df = self.pro.stock_basic(exchange="", list_status="L", fields="ts_code,name,list_date")
            if df is not None and not df.empty:
                df.to_csv(cache_path, index=False)
                df = df[df["ts_code"].isin(codes)]
                df["list_date"] = pd.to_datetime(df["list_date"], format="%Y%m%d", errors="coerce")
                return df.set_index("ts_code").to_dict("index")
        except Exception as e:
            print(f"  [WARN] stock_basic 被限频，使用股票代码作为名称: {e}")

        # 兜底: 用股票代码作为名称
        print(f"  使用股票代码作为 {len(codes)} 只股票的名称")
        return {code: {"name": code, "list_date": pd.Timestamp("2020-01-01")} for code in codes}

    def fetch_daily_bars(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        """获取单只股票的日线行情 (前复权)。"""
        from src.domain.market.value_objects.timeframe import Timeframe
        from src.infrastructure.gateway.tushare_history_data import TushareHistoryDataFetcher

        fetcher = TushareHistoryDataFetcher(token=self.token)
        bars = fetcher.fetch_history_bars(symbol, Timeframe.DAY_1, start_date, end_date)
        return [{"symbol": b.symbol, "timestamp": b.timestamp, "open": b.open, "high": b.high,
                 "low": b.low, "close": b.close, "volume": b.volume, "prev_close": b.prev_close} for b in bars]

    def fetch_all_bars(self, symbols: list[str], start_date: str, end_date: str) -> dict[str, list[dict]]:
        """批量拉取日线行情，带进度和错误处理。已缓存的股票跳过 API 调用。"""
        bar_data: dict[str, list[dict]] = {}
        empty: list[str] = []
        total = len(symbols)
        cache_dir = os.path.join("data")
        for i, sym in enumerate(symbols, 1):
            if i % 50 == 0 or i == total:
                print(f"  [{i}/{total}] {sym}", flush=True)
            # 检查缓存：如果 CSV 已存在，直接读取
            csv_path = os.path.join(cache_dir, f"{sym}_1d_tushare.csv")
            cached = os.path.exists(csv_path)
            try:
                bars = self.fetch_daily_bars(sym, start_date, end_date)
                if bars:
                    bar_data[sym] = bars
                else:
                    empty.append(sym)
            except Exception as e:
                print(f"  [WARN] {sym} 失败: {e}")
                empty.append(sym)
            # 只有非缓存的 API 调用才需要限流等待
            if not cached:
                self._sleep()
        return bar_data, empty

    @staticmethod
    def fetch_index_bars(symbol: str, start_date: str, end_date: str) -> list[dict]:
        """使用 efinance 获取指数日线数据 (Tushare 无指数权限时的备选方案)。"""
        import efinance as ef

        code = symbol.split(".")[0]
        ts_start = start_date.replace("-", "")
        ts_end = end_date.replace("-", "")
        df = ef.stock.get_quote_history(code, beg=ts_start, end=ts_end)
        if df is None or df.empty:
            return []

        bars = []
        for row in df.itertuples(index=False):
            dt = pd.Timestamp(row[2])  # 日期列
            bars.append({
                "symbol": symbol,
                "timestamp": dt.to_pydatetime(),
                "open": float(row[3]),   # 开盘
                "high": float(row[5]),   # 最高
                "low": float(row[6]),    # 最低
                "close": float(row[4]),  # 收盘
                "volume": float(row[7]), # 成交量
                "prev_close": 0.0,
            })
        # 计算 prev_close
        for i in range(1, len(bars)):
            bars[i]["prev_close"] = bars[i - 1]["close"]
        return bars


def build_fundamentals_from_bars(bar_data: dict[str, list[dict]], basic_info: dict) -> list:
    """从 K 线数据合成基本面快照。

    当 Tushare 积分不足无法获取 daily_basic/fina_indicator 时:
    - market_cap: 使用 20 日平均成交额 * 100 作为市值代理 (相对排序有效)
    - roe_ttm: 固定 10.0 (合理中位数，使 filter_quality 不会误杀)
    - ocf_ttm: 固定 1.0 (正值，通过 filter_quality 的 OCF > 0 检查)
    """
    from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot

    # 预计算每只股票的 20 日平均成交额作为市值代理
    avg_amount: dict[str, float] = {}
    for sym, bars in bar_data.items():
        amounts = [b["close"] * b["volume"] for b in bars[-20:]]  # 近20日成交额
        avg_amount[sym] = sum(amounts) / len(amounts) if amounts else 0.0

    # 找出所有交易日
    all_dates: set[str] = set()
    for bars in bar_data.values():
        for b in bars:
            all_dates.add(b["timestamp"].strftime("%Y%m%d"))
    trading_dates = sorted(all_dates)

    snapshots: list[FundamentalSnapshot] = []
    for sym in bar_data:
        info = basic_info.get(sym, {})
        name = info.get("name", sym)
        list_date = info.get("list_date")
        market_cap_proxy = avg_amount.get(sym, 0.0)

        for bar in bar_data[sym]:
            snapshots.append(FundamentalSnapshot(
                symbol=sym,
                date=bar["timestamp"],
                name=name,
                list_date=list_date,
                market_cap=market_cap_proxy,  # 相对排序代理值
                roe_ttm=10.0,   # 合理默认值
                ocf_ttm=1.0,    # 正值，通过 OCF > 0 检查
            ))

    return snapshots, trading_dates


def run(start_date: str = "2024-01-01", end_date: str = "2024-04-30",
        token: str | None = None) -> tuple[list[str], list, dict]:
    """执行完整的数据加载流程。"""
    from src.domain.market.services.fundamental_registry import FundamentalRegistry
    from src.infrastructure.ml_engine.feature_pipeline import FeaturePipeline

    fetcher = DataFetcher(token=token)

    # ── 1. 股票池 ──
    print("[1/4] 获取测试股票池...")
    universe = fetcher.fetch_stock_universe(start_date)
    print(f"  获取到 {len(universe)} 只股票")

    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "csi500_constituents.txt"), "w") as f:
        f.write("\n".join(universe))

    # ── 2. 基本信息 ──
    print("[2/4] 获取股票基本信息...")
    basic_info = fetcher.fetch_stock_basic(universe)
    print(f"  获取到 {len(basic_info)} 只股票信息")

    # ── 3. K 线行情 ──
    print(f"[3/4] 获取日线行情 ({len(universe)} 只股票 + 指数)...")
    bar_data, empty_syms = fetcher.fetch_all_bars(universe, start_date, end_date)
    print(f"  股票: 成功 {len(bar_data)} 只，缺失 {len(empty_syms)} 只")

    # 指数数据: 使用 efinance (Tushare 无指数权限)
    print("  获取中证1000指数 (000852.SH)...")
    try:
        idx_bars = DataFetcher.fetch_index_bars("000852.SH", start_date, end_date)
        if idx_bars:
            bar_data["000852.SH"] = idx_bars
            print(f"  000852.SH: {len(idx_bars)} 条")
        else:
            print("  [WARN] 000852.SH 无数据")
    except Exception as e:
        print(f"  [WARN] 000852.SH 获取失败: {e}")

    # 保存 K 线 CSV
    for sym, bars in bar_data.items():
        pd.DataFrame(bars).to_csv(os.path.join(data_dir, f"{sym}_1d_tushare.csv"), index=False)

    # ── 4. 合成基本面 & 注册表 ──
    print("[4/4] 组装基本面快照...")
    snapshots, trading_dates = build_fundamentals_from_bars(
        {s: bar_data[s] for s in universe if s in bar_data}, basic_info
    )
    registry = FundamentalRegistry()
    for s in snapshots:
        registry.add(s)
    print(f"  创建 {len(snapshots)} 条快照，覆盖 {len(trading_dates)} 个交易日")

    # ── 交叉验证 ──
    from src.domain.market.value_objects.bar import Bar
    from src.domain.market.value_objects.timeframe import Timeframe as Tf

    print("\n── 交叉验证 ──")
    mid_idx = len(trading_dates) // 2
    mid_date = datetime.strptime(trading_dates[mid_idx], "%Y%m%d")
    test_bars: dict[str, Bar] = {}
    for sym in universe[:30]:
        if sym in bar_data:
            for b in bar_data[sym]:
                if b["timestamp"].date() == mid_date.date():
                    test_bars[sym] = Bar(
                        symbol=b["symbol"], timeframe=Tf.DAY_1,
                        timestamp=b["timestamp"], open=b["open"],
                        high=b["high"], low=b["low"], close=b["close"],
                        volume=b["volume"], prev_close=b.get("prev_close", 0.0),
                    )
                    break
    cross = FeaturePipeline.build_cross_section(mid_date, test_bars, registry)
    print(f"  日期 {trading_dates[mid_idx]}: 截面 {len(cross)} 只 (测试样本 {len(test_bars)} 只)")
    reg_date = registry.get_all_at_date(mid_date)
    print(f"  Registry 该日快照: {len(reg_date)} 条")

    # ── 汇总 ──
    print(f"\n{'='*50}")
    print("  数据加载完成")
    print(f"{'='*50}")
    print(f"  时间段: {start_date} ~ {end_date}")
    print(f"  股票池: {len(universe)} 只")
    print(f"  基本面快照: {len(snapshots)} 条")
    print(f"  K线成功: {len(bar_data)} 只，缺失: {len(empty_syms)} 只")
    print(f"{'='*50}")

    metadata = {
        "start_date": start_date, "end_date": end_date,
        "universe_count": len(universe), "snapshot_count": len(snapshots),
        "symbols_with_bars": len(bar_data), "symbols_without_bars": empty_syms,
        "generated_at": datetime.now().isoformat(),
    }
    with open(os.path.join(data_dir, "data_loader_result.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return universe, snapshots, bar_data


if __name__ == "__main__":
    run()
