"""获取单只标的实时行情数据。

使用方式:
    python -m src.interfaces.cli.fetch_quote --symbol 600519.SH
"""

import argparse
import sys

from .cli_utils import (
    cancel_timeout,
    check_qmt_connection,
    output_error,
    output_success,
    setup_timeout,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="获取单只标的实时行情")
    parser.add_argument(
        "--symbol", "-s", type=str, required=True,
        help="标的代码，如 600519.SH",
    )
    parser.add_argument(
        "--config", "-c", type=str, default="resources/trading.yaml",
        help="配置文件路径",
    )
    return parser.parse_args()


def _get_realtime_tick(symbol: str) -> dict | None:
    """通过 get_full_tick 获取实时快照，失败返回 None。"""
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata
        tick_data = xtdata.get_full_tick([symbol])
        if not tick_data or symbol not in tick_data:
            return None
        tick = tick_data[symbol]
        # tick 是一个 dict-like 对象
        last_price = tick.get("lastPrice", 0) or tick.get("last_price", 0)
        if not last_price:
            return None
        return {
            "price": float(last_price),
            "open": float(tick.get("open", 0) or 0),
            "high": float(tick.get("high", 0) or 0),
            "low": float(tick.get("low", 0) or 0),
            "pre_close": float(tick.get("lastClose", 0) or tick.get("last_close", 0) or 0),
            "volume": int(tick.get("volume", 0) or 0),
            "amount": float(tick.get("amount", 0) or 0),
        }
    except Exception:
        return None


def _get_latest_bar(symbol: str) -> dict | None:
    """降级方案：通过 get_market_data_ex 获取最近一个交易日数据。"""
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata
        xtdata.download_history_data(stock_code=symbol, period='1d', count=5)
        data = xtdata.get_market_data_ex(
            field_list=['open', 'high', 'low', 'close', 'volume', 'amount'],
            stock_list=[symbol],
            period='1d',
            count=5,
            dividend_type='front',
            fill_data=False,
        )
        if symbol not in data or data[symbol].empty:
            return None
        df = data[symbol].sort_index()
        latest = df.iloc[-1]
        prev_close = float(df.iloc[-2]["close"]) if len(df) >= 2 else float(latest["close"])
        return {
            "price": float(latest["close"]),
            "open": float(latest["open"]),
            "high": float(latest["high"]),
            "low": float(latest["low"]),
            "pre_close": prev_close,
            "volume": int(latest["volume"]),
            "amount": float(latest.get("amount", 0)),
        }
    except Exception:
        return None


def _get_instrument_detail(symbol: str) -> dict:
    """获取合约详情：名称、总股本。"""
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata
        detail = xtdata.get_instrument_detail(symbol)
        if not detail:
            return {"name": symbol, "total_shares": 0}
        return {
            "name": detail.get("InstrumentName", symbol),
            "total_shares": int(detail.get("TotalVolume", 0) or 0),
        }
    except Exception:
        return {"name": symbol, "total_shares": 0}


def _get_financial_ratios(symbol: str) -> dict:
    """获取 PE / PB 等财务指标。"""
    try:
        import pandas as pd

        from src.infrastructure.gateway.xtquant_client import xtdata
        fin = xtdata.get_financial_data(
            stock_list=[symbol],
            table_list=['PershareIndex'],
            start_time='',
            end_time='',
            report_type='announce_time',
        )
        if not fin or symbol not in fin:
            return {}
        psi = fin[symbol].get('PershareIndex')
        if psi is None or not isinstance(psi, pd.DataFrame) or psi.empty:
            return {}
        # 按公告日期排序取最新
        psi = psi.sort_values('m_anntime', ascending=False)
        latest = psi.iloc[0]
        result: dict = {}
        eps = latest.get('s_fa_eps_basic')
        if pd.notna(eps) and float(eps) > 0:
            result['eps'] = float(eps)
        bps = latest.get('s_fa_bps')
        if pd.notna(bps) and float(bps) > 0:
            result['bps'] = float(bps)
        roe = latest.get('equity_roe')
        if pd.notna(roe):
            result['roe'] = float(roe)
        return result
    except Exception:
        return {}


def fetch_quote(symbol: str) -> dict:
    """获取标的完整行情数据。"""
    # 1. 实时快照（优先），降级为最近 K 线
    quote = _get_realtime_tick(symbol)
    if quote is None:
        quote = _get_latest_bar(symbol)
    if quote is None:
        raise ValueError(f"无法获取 {symbol} 的行情数据，请检查标的代码是否正确")

    # 2. 合约详情
    detail = _get_instrument_detail(symbol)

    # 3. 财务指标
    fina = _get_financial_ratios(symbol)

    # 4. 计算衍生字段
    price = quote["price"]
    pre_close = quote["pre_close"]
    change = price - pre_close if pre_close else 0.0
    change_pct = (change / pre_close * 100) if pre_close else 0.0
    total_shares = detail["total_shares"]
    market_cap = price * total_shares if total_shares else None

    pe_ratio = (price / fina["eps"]) if fina.get("eps") and fina["eps"] > 0 else None
    pb_ratio = (price / fina["bps"]) if fina.get("bps") and fina["bps"] > 0 else None

    # 量比：当日成交量 / 过去 5 日平均成交量（此处简化，取最近 5 日平均）
    vol_ratio = None
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata
        data = xtdata.get_market_data_ex(
            field_list=['volume'], stock_list=[symbol],
            period='1d', count=6, dividend_type='front', fill_data=False,
        )
        if symbol in data and not data[symbol].empty:
            vols = data[symbol]['volume'].tolist()
            if len(vols) >= 2:
                avg_vol = sum(vols[-6:-1]) / max(len(vols) - 1, 1)
                if avg_vol > 0:
                    vol_ratio = round(vols[-1] / avg_vol, 2)
    except Exception:
        pass

    result = {
        "symbol": symbol,
        "name": detail["name"],
        "price": round(price, 3),
        "open": round(quote["open"], 3),
        "high": round(quote["high"], 3),
        "low": round(quote["low"], 3),
        "pre_close": round(pre_close, 3),
        "change": round(change, 3),
        "change_pct": round(change_pct, 2),
        "volume": quote["volume"],
        "amount": quote["amount"],
        "turnover_rate": None,
        "pe_ratio": round(pe_ratio, 2) if pe_ratio is not None else None,
        "pb_ratio": round(pb_ratio, 2) if pb_ratio is not None else None,
        "market_cap": round(market_cap, 2) if market_cap is not None else None,
        "total_shares": total_shares,
    }
    if vol_ratio is not None:
        result["vol_ratio"] = vol_ratio
    return result


def main() -> None:
    args = parse_args()
    setup_timeout()
    try:
        if not check_qmt_connection():
            output_error("QMT 客户端未连接，请先启动 MiniQMT")
            sys.exit(1)

        print(f"正在获取 {args.symbol} 行情数据...", file=sys.stderr)
        data = fetch_quote(args.symbol)
        output_success(data)
    except TimeoutError:
        output_error("请求超时 (30s)")
        sys.exit(1)
    except Exception as e:
        output_error(str(e))
        sys.exit(1)
    finally:
        cancel_timeout()


if __name__ == "__main__":
    main()
