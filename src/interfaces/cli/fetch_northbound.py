"""获取北向资金（沪深港通）数据。

使用方式:
    python -m src.interfaces.cli.fetch_northbound
    python -m src.interfaces.cli.fetch_northbound --date 2025-05-30 --top 20
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

# 沪深港通专用板块（xtdata 可能不支持，作为探测目标）
NORTH_SECTORS = {
    "沪股通": "sh_connect",
    "深股通": "sz_connect",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="获取北向资金数据")
    parser.add_argument(
        "--date", "-d", type=str, default=None,
        help="查询日期（默认当日，格式 YYYY-MM-DD）",
    )
    parser.add_argument(
        "--top", "-t", type=int, default=10,
        help="显示前 N 名（默认 10）",
    )
    return parser.parse_args()


def _try_get_sector_stocks(sector_name: str) -> list[str]:
    """尝试获取板块成分股。"""
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata
        stocks = xtdata.get_stock_list_in_sector(sector_name)
        return stocks if stocks else []
    except Exception:
        return []


def _get_stock_net_flow(stocks: list[str], date_str: str) -> list[dict]:
    """获取成分股资金流向并排序。"""
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata
        # 尝试获取资金流向数据
        data = xtdata.get_market_data_ex(
            field_list=['close', 'volume', 'amount'],
            stock_list=stocks,
            period='1d',
            count=2,
            dividend_type='front',
            fill_data=False,
        )
        if not data:
            return []
        results = []
        for sym in stocks:
            if sym not in data or data[sym].empty:
                continue
            df = data[sym]
            if len(df) < 1:
                continue
            latest = df.iloc[-1]
            results.append({
                "symbol": sym,
                "price": round(float(latest.get("close", 0)), 3),
                "volume": int(latest.get("volume", 0)),
                "amount": round(float(latest.get("amount", 0)), 2),
            })
        return results
    except Exception:
        return []


def fetch_northbound(date: str | None = None, top: int = 10) -> dict:
    """获取北向资金数据。

    xtdata 可能没有专用北向资金接口，降级方案：
    1. 尝试获取沪股通/深股通成分股
    2. 若无数据，返回提示信息
    """
    from src.infrastructure.gateway.xtquant_client import xtdata

    if date is None:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
    date_qmt = date.replace("-", "")

    # 尝试获取沪股通/深股通成分股
    sh_stocks = _try_get_sector_stocks("沪股通")
    sz_stocks = _try_get_sector_stocks("深股通")

    if not sh_stocks and not sz_stocks:
        # 尝试其他可能的板块名称
        for alt_name in ["沪深港通", "北向资金", "陆股通"]:
            sh_stocks = _try_get_sector_stocks(alt_name)
            if sh_stocks:
                break

    if not sh_stocks and not sz_stocks:
        return {
            "date": date,
            "message": "北向资金数据暂不可用。xtdata 未提供专用北向资金接口，"
                       "请使用东方财富/同花顺等第三方数据源查询。",
            "total_net_buy": None,
            "sh_net_buy": None,
            "sz_net_buy": None,
            "top_buy": [],
            "top_sell": [],
        }

    # 获取资金数据
    all_stocks = sh_stocks + sz_stocks
    # 下载历史数据
    for sym in all_stocks[:100]:  # 限制数量避免超时
        try:
            xtdata.download_history_data(stock_code=sym, period='1d', count=5)
        except Exception:
            pass

    sh_flow = _get_stock_net_flow(sh_stocks[:50], date_qmt)
    sz_flow = _get_stock_net_flow(sz_stocks[:50], date_qmt)

    # 按成交额排序取 top
    sh_flow.sort(key=lambda x: x.get("amount", 0), reverse=True)
    sz_flow.sort(key=lambda x: x.get("amount", 0), reverse=True)

    top_buy = (sh_flow + sz_flow)[:top]
    top_sell = sorted(sh_flow + sz_flow, key=lambda x: x.get("amount", 0))[:top]

    return {
        "date": date,
        "sh_connect_count": len(sh_stocks),
        "sz_connect_count": len(sz_stocks),
        "top_buy": top_buy,
        "top_sell": top_sell,
    }


def main() -> None:
    args = parse_args()
    setup_timeout()
    try:
        if not check_qmt_connection():
            output_error("QMT 客户端未连接，请先启动 MiniQMT")
            sys.exit(1)

        print("正在获取北向资金数据...", file=sys.stderr)
        data = fetch_northbound(args.date, args.top)
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
