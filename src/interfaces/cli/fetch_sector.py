"""获取行业板块成分股及行情。

使用方式:
    python -m src.interfaces.cli.fetch_sector --sector semiconductor
    python -m src.interfaces.cli.fetch_sector --sector 半导体 --top 10
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

SECTOR_MAP = {
    "semiconductor": "半导体",
    "new_energy": "新能源",
    "pharma": "医药",
    "consumer": "消费",
    "finance": "金融",
    "tech": "科技",
    "auto": "汽车",
    "military": "军工",
    "real_estate": "房地产",
    "material": "材料",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="获取行业板块成分股及行情")
    parser.add_argument(
        "--sector", "-s", type=str, required=True,
        help="板块代码或名称（如 semiconductor 或 半导体）",
    )
    parser.add_argument(
        "--top", "-t", type=int, default=20,
        help="显示前 N 只（默认 20）",
    )
    return parser.parse_args()


def _resolve_sector_name(sector: str) -> str:
    """将英文代码映射为中文板块名。"""
    return SECTOR_MAP.get(sector, sector)


def _get_sector_change_pct(stocks_data: list[dict]) -> float | None:
    """计算板块平均涨跌幅。"""
    changes = [s["change_pct"] for s in stocks_data if s.get("change_pct") is not None]
    if not changes:
        return None
    return round(sum(changes) / len(changes), 2)


def fetch_sector(sector: str, top: int = 20) -> dict:
    """获取板块成分股及行情。"""
    from src.infrastructure.gateway.xtquant_client import xtdata

    sector_name = _resolve_sector_name(sector)

    # 获取板块成分股列表
    stocks: list[str] = []
    for name_candidate in [sector_name, sector]:
        try:
            result = xtdata.get_stock_list_in_sector(name_candidate)
            if result:
                stocks = result
                break
        except Exception:
            continue

    if not stocks:
        raise ValueError(f"板块 '{sector}' ({sector_name}) 未找到，请检查板块名称是否正确")

    # 下载历史数据
    for sym in stocks:
        try:
            xtdata.download_history_data(stock_code=sym, period='1d', count=5)
        except Exception:
            pass

    # 获取行情数据
    data = xtdata.get_market_data_ex(
        field_list=['open', 'high', 'low', 'close', 'volume', 'amount'],
        stock_list=stocks,
        period='1d',
        count=2,
        dividend_type='front',
        fill_data=False,
    )

    stock_list = []
    for sym in stocks:
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

        stock_list.append({
            "symbol": sym,
            "name": name,
            "price": round(price, 3),
            "change_pct": change_pct,
            "volume": int(latest.get("volume", 0)),
            "amount": round(float(latest.get("amount", 0)), 2),
        })

    # 按涨跌幅排序
    stock_list.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    sector_change_pct = _get_sector_change_pct(stock_list)

    return {
        "sector": sector,
        "sector_name": sector_name,
        "stock_count": len(stock_list),
        "stocks": stock_list[:top],
        "sector_change_pct": sector_change_pct,
    }


def main() -> None:
    args = parse_args()
    setup_timeout()
    try:
        if not check_qmt_connection():
            output_error("QMT 客户端未连接，请先启动 MiniQMT")
            sys.exit(1)

        print(f"正在获取 {args.sector} 板块数据...", file=sys.stderr)
        data = fetch_sector(args.sector, args.top)
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
