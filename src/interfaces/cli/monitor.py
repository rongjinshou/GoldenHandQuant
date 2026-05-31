"""监控 CLI 入口。

用法:
    python -m src.interfaces.cli.monitor status
    python -m src.interfaces.cli.monitor stats
    python -m src.interfaces.cli.monitor pause --strategy xxx
    python -m src.interfaces.cli.monitor resume --strategy xxx
"""
import argparse
import logging
import sys


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_status(args: object) -> None:
    """显示系统状态。"""
    print("=== GoldenHandQuant 系统状态 ===")
    print("提示: 完整状态需要注入 AutoTradingEngine 实例")
    print("状态: 未连接")


def cmd_stats(args: object) -> None:
    """显示执行统计。"""
    print("=== 执行统计 ===")
    print("提示: 完整统计需要注入 ExecutionMonitor 实例")


def cmd_pause(args: object) -> None:
    """暂停策略。"""
    strategy = getattr(args, 'strategy', None) or "all"
    print(f"暂停策略: {strategy}")
    print("提示: 完整暂停需要注入 AutoPauseManager 实例")


def cmd_resume(args: object) -> None:
    """恢复策略。"""
    strategy = getattr(args, 'strategy', None) or "all"
    print(f"恢复策略: {strategy}")
    print("提示: 完整恢复需要注入 AutoPauseManager 实例")


def main() -> None:
    parser = argparse.ArgumentParser(description="GoldenHandQuant 监控 CLI")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # status
    subparsers.add_parser("status", help="显示系统状态")

    # stats
    subparsers.add_parser("stats", help="显示执行统计")

    # pause
    pause_parser = subparsers.add_parser("pause", help="暂停交易")
    pause_parser.add_argument("--strategy", help="策略名称 (默认暂停全部)")

    # resume
    resume_parser = subparsers.add_parser("resume", help="恢复交易")
    resume_parser.add_argument("--strategy", help="策略名称 (默认恢复全部)")

    args = parser.parse_args()
    _setup_logging()

    commands = {
        "status": cmd_status,
        "stats": cmd_stats,
        "pause": cmd_pause,
        "resume": cmd_resume,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
