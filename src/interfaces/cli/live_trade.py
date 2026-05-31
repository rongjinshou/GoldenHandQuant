"""
半自动 CLI 交易入口。

使用方式:
    python -m src.interfaces.cli.live_trade --strategy dual_ma --symbols 600000.SH,000001.SZ
    python -m src.interfaces.cli.live_trade  # 使用 resources/trading.yaml 默认配置
    python -m src.interfaces.cli.live_trade --review-mode legacy  # 旧版纯文本模式
"""

import argparse
import logging
import sys
from datetime import datetime

from src.application.live_signal_service import LiveSignalService, OrderResult, SignalDisplay
from src.domain.strategy.registry import get_strategy, list_strategies
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.infrastructure.config.settings import load_trading_config

logger = logging.getLogger(__name__)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GoldenHandQuant 半自动交易")
    parser.add_argument(
        "--strategy", "-s", type=str, default=None,
        help="策略名称 (如 dual_ma, micro_value)",
    )
    parser.add_argument(
        "--symbols", type=str, default=None,
        help="标的列表，逗号分隔 (如 600000.SH,000001.SZ)",
    )
    parser.add_argument(
        "--config", type=str, default="resources/trading.yaml",
        help="配置文件路径",
    )
    parser.add_argument(
        "--review-mode", type=str, default="rich", choices=["rich", "legacy"],
        help="审核界面模式: rich (默认) 或 legacy (旧版纯文本)",
    )
    return parser.parse_args()


def print_header() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print()
    print(f"{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN}  GoldenHandQuant 半自动交易信号{' '*40}{now}{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}")


def main() -> None:
    args = parse_args()

    try:
        settings = load_trading_config(args.config)
    except FileNotFoundError:
        print(f"{RED}配置文件未找到: {args.config}{RESET}")
        sys.exit(1)

    lt = settings.live_trade
    strategy_name = args.strategy or lt.strategy
    symbols = args.symbols.split(",") if args.symbols else lt.symbols

    if not symbols:
        print(f"{RED}未指定标的列表。请通过 --symbols 或配置文件指定。{RESET}")
        sys.exit(1)

    try:
        config = get_strategy(strategy_name)
    except KeyError:
        available = [s.name for s in list_strategies()]
        print(f"{RED}未知策略: {strategy_name}。可选: {', '.join(available)}{RESET}")
        sys.exit(1)

    print_header()
    print(f"\n{BOLD}加载策略:{RESET} {config.description}")
    print(f"{BOLD}标的列表:{RESET} {', '.join(symbols)}")
    print(f"{BOLD}策略类型:{RESET} {config.strategy_type}")

    from src.infrastructure.gateway.qmt_market import QmtMarketGateway
    from src.infrastructure.gateway.qmt_trade import QmtTradeGateway

    qmt = settings.qmt
    if not qmt.userdata_path:
        print(f"{RED}QMT 路径未配置。请在 {args.config} 中设置 qmt.userdata_path。{RESET}")
        sys.exit(1)

    print(f"\n{BOLD}连接 QMT...{RESET}")
    try:
        market_gw = QmtMarketGateway()
        trade_gw = QmtTradeGateway(
            path=qmt.userdata_path,
            session_id=qmt.session_id,
            account_id=qmt.account_id,
            account_type=qmt.account_type,
        )
        account_gw = trade_gw
    except Exception as e:
        print(f"{RED}QMT 连接失败: {e}{RESET}")
        sys.exit(1)

    service = LiveSignalService(
        market_gateway=market_gw,
        account_gateway=account_gw,
        trade_gateway=trade_gw,
        slippage_buy=lt.slippage_buy,
        slippage_sell=lt.slippage_sell,
        bar_lookback=lt.bar_lookback,
    )

    if args.review_mode == "rich":
        _run_rich_review(service, strategy_name, symbols)
    else:
        _run_legacy_review(service, strategy_name, symbols, account_gw)


def _run_rich_review(
    service: LiveSignalService,
    strategy_name: str,
    symbols: list[str],
) -> None:
    from src.interfaces.cli.signal_review.review_store import ReviewStore
    from src.interfaces.cli.signal_review.review_ui import SignalReviewUI

    store = ReviewStore()
    ui = SignalReviewUI(service=service, store=store)
    ui.run(strategy_name, symbols)


def _run_legacy_review(
    service: LiveSignalService,
    strategy_name: str,
    symbols: list[str],
    account_gw,
) -> None:
    """旧版纯文本审核模式 (向后兼容)。"""
    asset = account_gw.get_asset()
    positions = account_gw.get_positions()

    print(f"\n{BOLD}正在扫描信号...{RESET}")
    displays = service.scan(strategy_name=strategy_name, symbols=symbols)

    _print_signal_table(displays)
    _print_status_bar(displays, asset, len(positions))

    if not displays:
        return

    print(f"\n{BOLD}输入序号确认下单 (逗号分隔, a=全部, q=退出):{RESET} ", end="")
    choice = input().strip().lower()

    if choice == "q":
        print(f"{YELLOW}已退出，未执行任何交易。{RESET}")
        return

    if choice == "a":
        selected = displays
    else:
        try:
            indices = [int(x.strip()) for x in choice.split(",")]
            selected = [displays[i - 1] for i in indices if 1 <= i <= len(displays)]
        except (ValueError, IndexError):
            print(f"{RED}输入无效。{RESET}")
            return

    if not selected:
        print(f"{YELLOW}未选择任何信号。{RESET}")
        return

    confirmed: list[SignalDisplay] = []
    for d in selected:
        if _confirm_single(d):
            confirmed.append(d)

    if not confirmed:
        print(f"{YELLOW}未确认任何订单。{RESET}")
        return

    print(f"\n{BOLD}正在下单...{RESET}")
    results = service.place_confirmed_orders(confirmed)
    _print_order_results(results)


def _print_signal_table(displays: list[SignalDisplay]) -> None:
    if not displays:
        print(f"\n{YELLOW}当前无交易信号。{RESET}\n")
        return

    header = (
        f"{'序号':>4}  {'标的':<12} {'方向':<6} {'当前价':>8} {'挂单价':>8} "
        f"{'数量':>6} {'所需资金':>10} {'触发原因'}"
    )
    print(f"\n{BOLD}{header}{RESET}")
    print("-" * 80)

    for i, d in enumerate(displays, 1):
        dir_color = GREEN if d.direction == SignalDirection.BUY else RED
        dir_text = "BUY " if d.direction == SignalDirection.BUY else "SELL"
        print(
            f"{i:>4}  {d.symbol:<12} {dir_color}{dir_text:<6}{RESET} "
            f"{d.current_price:>8.2f} {d.suggested_price:>8.2f} "
            f"{d.suggested_volume:>6} {d.required_capital:>10,.0f} "
            f"{d.reason}"
        )
    print("-" * 80)


def _print_status_bar(displays: list[SignalDisplay], asset, position_count: int) -> None:
    strategy_name = displays[0].strategy_name if displays else "-"
    available = asset.available_cash if asset else 0
    print(
        f"{CYAN}策略: {strategy_name}  |  "
        f"可用资金: {available:,.0f}  |  "
        f"当前持仓: {position_count} 只{RESET}"
    )


def _confirm_single(display: SignalDisplay) -> bool:
    dir_text = "买入" if display.direction == SignalDirection.BUY else "卖出"
    print(
        f"\n{YELLOW}确认下单: {dir_text} {display.symbol} "
        f"{display.suggested_volume}股 @ {display.suggested_price:.2f} "
        f"(约 {display.required_capital:,.0f})?{RESET} [y/N]: ",
        end="",
    )
    answer = input().strip().lower()
    return answer == "y"


def _print_order_results(results: list[OrderResult]) -> None:
    print(f"\n{BOLD}{'---'}{RESET}")
    for r in results:
        if r.success:
            print(f"{GREEN}  {r.symbol} {r.direction.value} 订单已提交: {r.order_id}{RESET}")
        else:
            print(f"{RED}  {r.symbol} {r.direction.value} 下单失败: {r.error_message}{RESET}")
    print(f"{BOLD}{'---'}{RESET}\n")


if __name__ == "__main__":
    main()
