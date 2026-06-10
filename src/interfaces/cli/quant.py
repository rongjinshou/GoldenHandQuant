"""GoldenHandQuant 统一投研 CLI 入口。

使用方式:
    python -m src.interfaces.cli.quant list
    python -m src.interfaces.cli.quant research --idea "微盘价值" --period 2020-2025
    python -m src.interfaces.cli.quant backtest --strategy dual_ma
    python -m src.interfaces.cli.quant live --strategy dual_ma
    python -m src.interfaces.cli.quant compare --strategies a,b
    python -m src.interfaces.cli.quant factor-test --factors pb_value
    python -m src.interfaces.cli.quant auto-trade --config resources/trading.yaml
    python -m src.interfaces.cli.quant ml-train --start-date 2020-01-01 --end-date 2024-12-31
    python -m src.interfaces.cli.quant ml-evaluate --model-name lgbm_5d
    python -m src.interfaces.cli.quant monitor status
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
    p_ft = subparsers.add_parser("factor-test", help="因子假设测试")
    p_ft.add_argument("--factors", type=str, required=True,
                       help="因子标识: F01,F02 / 小市值,短期反转 / P0 / all")
    p_ft.add_argument("--start-date", type=str, default="2021-01-01", help="测试开始日期")
    p_ft.add_argument("--end-date", type=str, default="2025-12-31", help="测试结束日期")
    p_ft.add_argument("--split-date", type=str, default=None,
                       help="样本内截止日期(如 2023-12-31)，启用样本外验证")
    p_ft.add_argument("--num-layers", type=int, default=5, help="分层数")
    p_ft.add_argument("--rebalance-days", type=int, default=1,
                       help="分层回测调仓间隔(交易日): 1=每日, 5=约每周; "
                            "持有期内不重排、不计换手成本")
    p_ft.add_argument("--output", type=str, default=None, help="报告输出路径(JSON)")
    p_ft.add_argument("--config", type=str, default="resources/backtest.yaml", help="配置文件")
    p_ft.add_argument("--no-store", action="store_true",
                       help="不走市场数据库快路径, 回退旧内存管道")

    # --- data ---
    p_data = subparsers.add_parser("data", help="市场数据库维护 (DuckDB)")
    p_data.add_argument("data_action", choices=["refresh", "status"], help="数据子命令")
    p_data.add_argument("--start-date", type=str, default="2021-01-01", help="刷新开始日期")
    p_data.add_argument("--end-date", type=str, default="2025-12-31", help="刷新结束日期")
    p_data.add_argument("--config", type=str, default="resources/backtest.yaml", help="配置文件")
    p_data.add_argument("--db", type=str, default="data/market.duckdb", help="数据库文件路径")

    # --- dashboard ---
    p_db = subparsers.add_parser("dashboard", help="投研驾驶舱 (浏览器查看数据/判决/个股)")
    p_db.add_argument("--port", type=int, default=8501, help="监听端口")
    p_db.add_argument("--db", type=str, default="data/market.duckdb", help="数据库文件路径")

    # --- list ---
    subparsers.add_parser("list", help="列出所有可用策略")

    # --- auto-trade ---
    p_at = subparsers.add_parser("auto-trade", help="自动交易引擎")
    p_at.add_argument("--config", default="resources/trading.yaml", help="交易配置文件路径")
    p_at.add_argument("--once", action="store_true", help="仅执行一次交易循环")
    p_at.add_argument("--enable", action="store_true", help="显式启用自动交易")

    # --- ml-train ---
    p_mt = subparsers.add_parser("ml-train", help="ML 模型训练")
    p_mt.add_argument("--symbols", type=str, default="000300.SH", help="股票列表，逗号分隔")
    p_mt.add_argument("--start-date", type=str, required=True, help="训练开始日期")
    p_mt.add_argument("--end-date", type=str, required=True, help="训练结束日期")
    p_mt.add_argument("--label-horizon", type=int, default=5, help="前瞻天数")
    p_mt.add_argument("--model-name", type=str, default="lgbm_return_5d", help="模型名称")
    p_mt.add_argument("--n-trials", type=int, default=50, help="Optuna 搜索次数")
    p_mt.add_argument("--n-cv-splits", type=int, default=5, help="CV 折数")
    p_mt.add_argument("--top-n", type=int, default=10, help="选股 Top N")
    p_mt.add_argument("--config", type=str, default=None, help="YAML 配置文件路径")

    # --- ml-evaluate ---
    p_me = subparsers.add_parser("ml-evaluate", help="ML 模型评估")
    p_me.add_argument("--model-name", type=str, required=True, help="模型名称")
    p_me.add_argument("--eval-start", type=str, required=True, help="评估开始日期")
    p_me.add_argument("--eval-end", type=str, required=True, help="评估结束日期")
    p_me.add_argument("--quintiles", type=int, default=5, help="分层数")
    p_me.add_argument("--plot", action="store_true", help="绘制图表")

    # --- monitor ---
    p_mon = subparsers.add_parser("monitor", help="系统监控")
    p_mon.add_argument("monitor_command", choices=["status", "stats", "pause", "resume"], help="监控子命令")
    p_mon.add_argument("--strategy", type=str, default=None, help="策略名称 (pause/resume)")

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
        case "data":
            from src.interfaces.cli.commands.data_cmd import run_data

            run_data(args)
        case "dashboard":
            from src.interfaces.cli.commands.dashboard_cmd import run_dashboard

            run_dashboard(args)
        case "list":
            from src.domain.strategy.registry import list_strategies

            for s in list_strategies():
                print(f"  {s.name:<20} [{s.strategy_type}] {s.description}")
        case "auto-trade":
            from src.interfaces.cli.auto_trade import main as auto_trade_main

            auto_trade_main(args)
        case "ml-train":
            from src.interfaces.cli.ml_train import main as ml_train_main

            ml_train_main(args)
        case "ml-evaluate":
            from src.interfaces.cli.ml_evaluate import main as ml_evaluate_main

            ml_evaluate_main(args)
        case "monitor":
            from src.interfaces.cli.monitor import (
                cmd_pause,
                cmd_resume,
                cmd_stats,
                cmd_status,
            )

            monitor_commands = {
                "status": cmd_status,
                "stats": cmd_stats,
                "pause": cmd_pause,
                "resume": cmd_resume,
            }
            handler = monitor_commands.get(args.monitor_command)
            if handler:
                handler(args)


if __name__ == "__main__":
    main()
