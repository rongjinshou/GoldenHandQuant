"""quant compare 子命令实现（占位）。"""

import argparse


def run_compare(args: argparse.Namespace) -> None:
    """多策略对比 — 暂为占位实现。"""
    strategies = args.strategies
    print("[compare] 多策略对比功能即将推出。")
    print(f"[compare] 请求对比策略: {strategies}")
    if args.start_date:
        print(f"[compare] 起始日期: {args.start_date}")
    if args.end_date:
        print(f"[compare] 结束日期: {args.end_date}")
    print("[compare] 敬请期待后续版本。")
