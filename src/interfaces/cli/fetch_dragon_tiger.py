"""获取龙虎榜数据。

使用方式:
    python -m src.interfaces.cli.fetch_dragon_tiger
    python -m src.interfaces.cli.fetch_dragon_tiger --date 2025-05-30 --top 20
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
    parser = argparse.ArgumentParser(description="获取龙虎榜数据")
    parser.add_argument(
        "--date", "-d", type=str, default=None,
        help="查询日期（默认当日，格式 YYYY-MM-DD）",
    )
    parser.add_argument(
        "--top", "-t", type=int, default=20,
        help="显示前 N 名（默认 20）",
    )
    return parser.parse_args()


def fetch_dragon_tiger(date: str | None = None, top: int = 20) -> dict:
    """获取龙虎榜数据。

    xtdata 没有专用龙虎榜接口，返回提示信息并尝试从行情数据中
    筛选异常波动的标的作为参考。
    """
    from datetime import datetime

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    try:
        from src.infrastructure.gateway.xtquant_client import xtdata
        # 尝试获取龙虎榜相关板块
        for sector_name in ["龙虎榜", "龙虎榜单", "异常波动"]:
            try:
                stocks = xtdata.get_stock_list_in_sector(sector_name)
                if stocks:
                    # 获取这些股票的行情
                    for sym in stocks[:top]:
                        try:
                            xtdata.download_history_data(stock_code=sym, period='1d', count=5)
                        except Exception:
                            pass
                    data = xtdata.get_market_data_ex(
                        field_list=['open', 'high', 'low', 'close', 'volume', 'amount'],
                        stock_list=stocks[:top],
                        period='1d',
                        count=2,
                        dividend_type='front',
                        fill_data=False,
                    )
                    items = []
                    for sym in stocks[:top]:
                        if sym not in data or data[sym].empty:
                            continue
                        df = data[sym]
                        latest = df.iloc[-1]
                        prev_close = float(df.iloc[-2]["close"]) if len(df) >= 2 else float(latest["close"])
                        price = float(latest["close"])
                        change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0

                        # 获取名称
                        name = sym
                        try:
                            detail = xtdata.get_instrument_detail(sym)
                            if detail:
                                name = detail.get("InstrumentName", sym)
                        except Exception:
                            pass

                        items.append({
                            "symbol": sym,
                            "name": name,
                            "close": round(price, 3),
                            "change_pct": change_pct,
                            "volume": int(latest.get("volume", 0)),
                            "amount": round(float(latest.get("amount", 0)), 2),
                            "buy_seats": [],
                            "sell_seats": [],
                        })

                    if items:
                        return {"date": date, "items": items[:top]}
            except Exception:
                continue

    except Exception:
        pass

    # 兜底：返回提示信息
    return {
        "date": date,
        "message": "龙虎榜数据暂不可用。xtdata 未提供专用龙虎榜接口，"
                   "请使用东方财富/同花顺等第三方数据源查询。",
        "items": [],
    }


def main() -> None:
    args = parse_args()
    setup_timeout()
    try:
        if not check_qmt_connection():
            output_error("QMT 客户端未连接，请先启动 MiniQMT")
            sys.exit(1)

        print("正在获取龙虎榜数据...", file=sys.stderr)
        data = fetch_dragon_tiger(args.date, args.top)
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
