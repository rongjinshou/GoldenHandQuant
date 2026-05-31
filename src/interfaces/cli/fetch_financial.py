"""获取单只标的财务数据。

使用方式:
    python -m src.interfaces.cli.fetch_financial --symbol 600519.SH
    python -m src.interfaces.cli.fetch_financial --symbol 600519.SH --quarters 8
"""

import argparse
import sys
from datetime import datetime

import pandas as pd

from .cli_utils import (
    cancel_timeout,
    check_qmt_connection,
    output_error,
    output_success,
    setup_timeout,
)

FIELD_MAP = {
    "equity_roe": "roe",
    "s_fa_eps_basic": "eps",
    "s_fa_bps": "bps",
    "s_fa_ocfps": "ocf_per_share",
    "gear_ratio": "debt_ratio",
    "gross_profit": "gross_profit",
    "net_profit": "net_profit",
    "inc_revenue_rate": "revenue_growth",
    "inc_net_profit_rate": "net_profit_growth",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="获取单只标的财务数据")
    parser.add_argument(
        "--symbol", "-s", type=str, required=True,
        help="标的代码，如 600519.SH",
    )
    parser.add_argument(
        "--quarters", "-q", type=int, default=4,
        help="获取最近 N 个季度（默认 4）",
    )
    return parser.parse_args()


def _get_instrument_detail(symbol: str) -> dict:
    """获取合约详情。"""
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata
        detail = xtdata.get_instrument_detail(symbol)
        if not detail:
            return {"name": symbol, "list_date": None, "total_shares": 0}
        open_date_raw = str(detail.get("OpenDate", "0"))
        list_date = None
        if open_date_raw and open_date_raw != "0":
            try:
                list_date = datetime.strptime(open_date_raw, "%Y%m%d").strftime("%Y-%m-%d")
            except ValueError:
                pass
        return {
            "name": detail.get("InstrumentName", symbol),
            "list_date": list_date,
            "total_shares": int(detail.get("TotalVolume", 0) or 0),
        }
    except Exception:
        return {"name": symbol, "list_date": None, "total_shares": 0}


def _parse_financial_data(symbol: str, quarters: int) -> tuple[dict | None, list[dict]]:
    """解析 PershareIndex 财务数据。

    Returns:
        (latest_report, quarters_list)
    """
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata
        # 注意: download_financial_data 同步版会卡死，已跳过
        # get_financial_data 在本地有数据时可直接返回
        fin = xtdata.get_financial_data(
            stock_list=[symbol],
            table_list=['PershareIndex'],
            start_time='',
            end_time='',
            report_type='announce_time',
        )
        if not fin or symbol not in fin:
            return None, []
        psi = fin[symbol].get('PershareIndex')
        if psi is None or not isinstance(psi, pd.DataFrame) or psi.empty:
            return None, []

        # 按公告日期排序
        psi = psi.sort_values('m_anntime', ascending=False)
        # 取最近 N 期
        psi = psi.head(quarters)

        quarter_list = []
        for _, row in psi.iterrows():
            ann_time = str(row.get('m_anntime', ''))
            if not ann_time or ann_time == 'nan':
                continue
            # 格式化公告日期
            try:
                dt = datetime.strptime(ann_time[:8], "%Y%m%d")
                report_date = dt.strftime("%Y-%m-%d")
            except (ValueError, IndexError):
                report_date = ann_time

            entry: dict = {"report_date": report_date}
            for src_field, dst_field in FIELD_MAP.items():
                val = row.get(src_field)
                if pd.notna(val):
                    entry[dst_field] = round(float(val), 4)
            quarter_list.append(entry)

        if not quarter_list:
            return None, []

        latest_report = quarter_list[0] if quarter_list else None
        return latest_report, quarter_list

    except Exception:
        return None, []


def fetch_financial(symbol: str, quarters: int = 4) -> dict:
    """获取标的财务数据。"""
    detail = _get_instrument_detail(symbol)
    latest_report, quarter_list = _parse_financial_data(symbol, quarters)

    return {
        "symbol": symbol,
        "name": detail["name"],
        "list_date": detail["list_date"],
        "latest_report": latest_report,
        "quarters": quarter_list,
    }


def main() -> None:
    args = parse_args()
    setup_timeout()
    try:
        if not check_qmt_connection():
            output_error("QMT 客户端未连接，请先启动 MiniQMT")
            sys.exit(1)

        print(f"正在获取 {args.symbol} 财务数据...", file=sys.stderr)
        data = fetch_financial(args.symbol, args.quarters)
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
