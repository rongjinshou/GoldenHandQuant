"""GoldenHandQuant 统一投研 CLI 入口。

使用方式:
    python -m src.interfaces.cli.quant list
    python -m src.interfaces.cli.quant research --idea "微盘价值" --period 2020-2025
    python -m src.interfaces.cli.quant backtest --strategy dual_ma
    python -m src.interfaces.cli.quant live --strategy dual_ma
    python -m src.interfaces.cli.quant compare --strategies a,b
    python -m src.interfaces.cli.quant factor-test --factors pb_value
"""

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quant",
        description="GoldenHandQuant 统一投研 CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # --- research ---
    p_research = subparsers.add_parser("research", help="自然语言投研: 选股->回测->报告")
    p_research.add_argument("--idea", type=str, required=True, help="投资想法描述")
    p_research.add_argument("--period", type=str, default="2020-2025", help="回测周期 (如 2020-2025, 3y)")
    p_research.add_argument("--config", type=str, default=None, help="配置文件路径")
    p_research.add_argument("--plot", action="store_true", help="显示图表")

    # --- backtest ---
    p_bt = subparsers.add_parser("backtest", help="直接回测")
    p_bt.add_argument("--strategy", "-s", type=str, required=True, help="策略名称")
    p_bt.add_argument("--config", type=str, default="resources/backtest.yaml", help="配置文件")
    p_bt.add_argument("--start-date", type=str, default=None, help="开始日期")
    p_bt.add_argument("--end-date", type=str, default=None, help="结束日期")
    p_bt.add_argument("--plot", action="store_true", help="显示图表")

    # --- live ---
    p_live = subparsers.add_parser("live", help="半自动交易")
    p_live.add_argument("--strategy", "-s", type=str, default=None, help="策略名称")
    p_live.add_argument("--symbols", type=str, default=None, help="标的列表 (逗号分隔)")
    p_live.add_argument("--config", type=str, default="resources/trading.yaml", help="配置文件")

    # --- compare ---
    p_cmp = subparsers.add_parser("compare", help="多策略对比")
    p_cmp.add_argument("--strategies", type=str, required=True, help="逗号分隔的策略列表")
    p_cmp.add_argument("--start-date", type=str, default=None)
    p_cmp.add_argument("--end-date", type=str, default=None)
    p_cmp.add_argument("--plot", action="store_true")

    # --- factor-test ---
    p_ft = subparsers.add_parser("factor-test", help="因子测试")
    p_ft.add_argument("--factors", type=str, required=True, help="逗号分隔的因子列表")
    p_ft.add_argument("--start-date", type=str, default=None)
    p_ft.add_argument("--end-date", type=str, default=None)

    # --- list ---
    subparsers.add_parser("list", help="列出所有可用策略")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    match args.command:
        case "research":
            from src.interfaces.cli.commands.research import run_research

            run_research(args)
        case "backtest":
            from src.interfaces.cli.commands.backtest import run_backtest

            run_backtest(args)
        case "live":
            from src.interfaces.cli.commands.live import run_live

            run_live(args)
        case "compare":
            from src.interfaces.cli.commands.compare import run_compare

            run_compare(args)
        case "factor-test":
            from src.interfaces.cli.commands.factor_test import run_factor_test

            run_factor_test(args)
        case "list":
            from src.domain.strategy.registry import list_strategies

            for s in list_strategies():
                print(f"  {s.name:<20} [{s.strategy_type}] {s.description}")


if __name__ == "__main__":
    main()
