"""quant live 子命令实现。"""

import argparse
import sys
from datetime import datetime

from src.application.live_signal_service import LiveSignalService, SignalDisplay
from src.domain.strategy.registry import get_strategy, list_strategies
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.infrastructure.config.settings import load_trading_config

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _print_header() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print()
    print(f"{BOLD}{CYAN}{'=' * 80}{RESET}")
    print(f"{BOLD}{CYAN}  GoldenHandQuant 半自动交易信号{' ' * 40}{now}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 80}{RESET}")


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


def run_live(args: argparse.Namespace) -> None:
    """执行半自动交易。参数由 quant.py 统一解析后传入。"""
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

    _print_header()
    print(f"\n{BOLD}加载策略:{RESET} {config.description}")
    print(f"{BOLD}标的列表:{RESET} {', '.join(symbols)}")
    print(f"{BOLD}策略类型:{RESET} {config.strategy_type}")

    if config.strategy_type == "cross_section":
        print(f"\n{YELLOW}截面策略需要全市场基本面数据，半自动模式暂不支持。{RESET}")
        print(f"{YELLOW}请使用 bar 类型策略（如 dual_ma）。{RESET}")
        sys.exit(0)

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

    # rich 审核台(T1: 自 live_trade.py 旧入口迁入后该入口退役): 扫描/审核/下单/
    # ReviewStore 留痕一体; 盘前闸输入与 plain 路径同源(M6)
    if getattr(args, "review_mode", "plain") == "rich":
        from src.infrastructure.gateway.qmt_realtime_quote import (
            QmtRealtimeQuoteFetcher,
        )
        from src.interfaces.cli.signal_review.review_store import ReviewStore
        from src.interfaces.cli.signal_review.review_ui import SignalReviewUI

        ui = SignalReviewUI(
            service=service, store=ReviewStore(),
            quote_fetcher=QmtRealtimeQuoteFetcher(),
            max_notional=settings.auto_trade.per_order_notional_cap,
            notional_ceiling=settings.auto_trade.per_order_notional_ceiling,
        )
        ui.run(strategy_name, symbols)
        return

    asset = account_gw.get_asset()
    positions = account_gw.get_positions()

    print(f"\n{BOLD}正在扫描信号...{RESET}")
    displays = service.scan(strategy_name=strategy_name, symbols=symbols)

    _print_signal_table(displays)

    if displays:
        strategy_label = displays[0].strategy_name if displays else "-"
        available_cash = asset.available_cash if asset else 0
        print(
            f"{CYAN}策略: {strategy_label}  |  "
            f"可用资金: {available_cash:,.0f}  |  "
            f"当前持仓: {len(positions)} 只{RESET}"
        )

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
        dir_text = "买入" if d.direction == SignalDirection.BUY else "卖出"
        print(
            f"\n{YELLOW}确认下单: {dir_text} {d.symbol} "
            f"{d.suggested_volume}股 @ {d.suggested_price:.2f} "
            f"(约 {d.required_capital:,.0f})?{RESET} [y/N]: ",
            end="",
        )
        answer = input().strip().lower()
        if answer == "y":
            confirmed.append(d)

    if not confirmed:
        print(f"{YELLOW}未确认任何订单。{RESET}")
        return

    print(f"\n{BOLD}正在下单...{RESET}")
    # M6: 与 auto-trade/ticket 统一盘前闸(时段/新鲜度/价格带/金额/ST/资金持仓)
    from src.infrastructure.gateway.qmt_realtime_quote import QmtRealtimeQuoteFetcher
    results = service.place_confirmed_orders(
        confirmed,
        quote_fetcher=QmtRealtimeQuoteFetcher(),
        max_notional=settings.auto_trade.per_order_notional_cap,
        notional_ceiling=settings.auto_trade.per_order_notional_ceiling,
    )
    print(f"\n{BOLD}{'─' * 40}{RESET}")
    for r in results:
        if r.success:
            print(f"{GREEN}{r.symbol} {r.direction.value} 订单已提交: {r.order_id}{RESET}")
        else:
            print(f"{RED}{r.symbol} {r.direction.value} 下单失败: {r.error_message}{RESET}")
    print(f"{BOLD}{'─' * 40}{RESET}\n")
