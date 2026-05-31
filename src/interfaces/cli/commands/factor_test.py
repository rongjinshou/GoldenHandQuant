"""quant factor-test 子命令实现（占位）。"""

import argparse


def run_factor_test(args: argparse.Namespace) -> None:
    """因子测试 — 暂为占位实现。"""
    factors = args.factors
    print("[factor-test] 因子测试功能即将推出。")
    print(f"[factor-test] 请求测试因子: {factors}")
    if args.start_date:
        print(f"[factor-test] 起始日期: {args.start_date}")
    if args.end_date:
        print(f"[factor-test] 结束日期: {args.end_date}")
    print("[factor-test] 敬请期待后续版本。")
