"""quant research 子命令实现 — 自然语言投研：策略匹配 -> 回测 -> 报告。"""

import argparse
from datetime import datetime, timedelta

from src.interfaces.cli.strategy_matcher import format_available_strategies, match_strategy


def _parse_period(period: str) -> tuple[str, str]:
    """解析 period 字符串为 (start_date, end_date)。

    支持格式:
      - "2020-2025"       -> 2020-01-01, 2025-12-31
      - "20200101-20251231" -> 2020-01-01, 2025-12-31
      - "3y"              -> 最近 3 年
    """
    period = period.strip()

    # "3y" / "5y" 模式
    if period.lower().endswith("y") and period[:-1].strip().isdigit():
        years = int(period[:-1])
        end = datetime.now()
        start = end - timedelta(days=years * 365)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # "YYYY-YYYY" 或 "YYYYMMDD-YYYYMMDD"
    parts = period.split("-")
    if len(parts) == 2:
        left, right = parts
        if len(left) == 4 and len(right) == 4 and left.isdigit() and right.isdigit():
            # "2020-2025" -> 年份范围
            return f"{left}-01-01", f"{right}-12-31"
        if len(left) == 8 and len(right) == 8:
            # "20200101-20251231"
            return f"{left[:4]}-{left[4:6]}-{left[6:]}", f"{right[:4]}-{right[4:6]}-{right[6:]}"

    # 默认回退
    return "2020-01-01", "2025-12-31"


def run_research(args: argparse.Namespace) -> None:
    """执行自然语言投研流程。"""
    idea: str = args.idea
    period: str = args.period

    # 匹配策略
    strategy_name = match_strategy(idea)
    if strategy_name is None:
        print(f'无法从 "{idea}" 匹配到策略。可用策略:')
        print(format_available_strategies())
        print("请使用 quant backtest --strategy <名称> 直接指定。")
        return

    print(f'投资想法: "{idea}" -> 匹配策略: {strategy_name}')

    # 解析周期
    start_date, end_date = _parse_period(period)
    print(f"回测周期: {start_date} ~ {end_date}")

    # 复用 backtest 子命令逻辑
    from src.interfaces.cli.commands.backtest import run_backtest

    # 构造一个 Namespace 传递给 run_backtest
    bt_args = argparse.Namespace(
        strategy=strategy_name,
        config=args.config or "resources/backtest.yaml",
        start_date=start_date,
        end_date=end_date,
        plot=args.plot,
    )
    run_backtest(bt_args)
