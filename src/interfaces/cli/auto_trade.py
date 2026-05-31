"""自动交易 CLI 入口。

用法:
    python -m src.interfaces.cli.auto_trade --config resources/trading.yaml
    python -m src.interfaces.cli.auto_trade --config resources/trading.yaml --once
"""
import argparse
import logging
import signal
import sys
import time

from src.infrastructure.config.settings import load_trading_config


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="GoldenHandQuant 自动交易引擎")
    parser.add_argument(
        "--config", default="resources/trading.yaml",
        help="交易配置文件路径",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="仅执行一次交易循环 (不启动守护线程)",
    )
    parser.add_argument(
        "--enable", action="store_true",
        help="显式启用自动交易 (覆盖配置文件中的 enabled=false)",
    )
    args = parser.parse_args()

    _setup_logging()
    logger = logging.getLogger(__name__)

    try:
        _settings = load_trading_config(args.config)
    except Exception as e:
        logger.error("加载配置失败: %s", e)
        sys.exit(1)

    logger.info("自动交易引擎启动中...")
    logger.info("配置文件: %s", args.config)

    # 构建依赖 (简化版，实盘需要根据配置构建完整依赖链)
    logger.info("提示: 自动交易引擎需要完整的依赖注入才能运行。")
    logger.info("请使用 AutoTradingEngine 构建完整实例后调用 run_cycle()。")
    logger.info("当前为 CLI 骨架，完整集成参见文档。")

    if args.once:
        logger.info("执行单次交易循环...")
        # engine.run_cycle()
        logger.info("单次循环完成")
    else:
        logger.info("启动守护循环...")
        logger.info("按 Ctrl+C 停止")

        def _shutdown(signum, frame):
            logger.info("收到停止信号，正在关闭...")
            # engine.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        # engine.start()
        # 主线程等待
        try:
            while True:
                signal.pause() if hasattr(signal, 'pause') else None
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("用户中断，正在关闭...")
            # engine.stop()


if __name__ == "__main__":
    main()
