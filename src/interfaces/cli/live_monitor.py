"""
实盘监控面板。

使用方式:
    python -m src.interfaces.cli.live_monitor
    python -m src.interfaces.cli.live_monitor --interval 5
    python -m src.interfaces.cli.live_monitor --no-alert
"""

import argparse
import signal
import sys
import time
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.application.monitor_service import MonitorService
from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.infrastructure.config.settings import load_trading_config
from src.infrastructure.snapshot.snapshot_store import SnapshotStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GoldenHandQuant 实盘监控面板")
    parser.add_argument(
        "--config", type=str, default="resources/trading.yaml",
        help="配置文件路径",
    )
    parser.add_argument(
        "--interval", "-i", type=int, default=None,
        help="刷新间隔（秒），默认从配置读取",
    )
    parser.add_argument(
        "--yesterday-asset", type=float, default=None,
        help="昨日总资产（不读快照文件时使用）",
    )
    parser.add_argument(
        "--no-alert", action="store_true",
        help="禁用告警检查",
    )
    return parser.parse_args()


def _pnl_text(value: float, ratio: float = 0.0, show_ratio: bool = True) -> Text:
    """格式化盈亏文本，带颜色。"""
    color = "green" if value > 0 else ("red" if value < 0 else "white")
    sign = "+" if value > 0 else ""
    text = Text(f"{sign}{value:,.0f}", style=color)
    if show_ratio:
        text.append(f"  ({sign}{ratio:.2%})", style=color)
    return text


def _build_header() -> Panel:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return Panel(
        Text(f"GoldenHandQuant 实盘监控    {now}", style="bold cyan"),
        style="cyan",
    )


def _build_overview(snapshot: MonitorSnapshot) -> Panel:
    """构建账户概览面板。"""
    table = Table(show_header=True, header_style="bold", expand=True, box=None)
    table.add_column("总资产", justify="right")
    table.add_column("可用资金", justify="right")
    table.add_column("持仓市值", justify="right")
    table.add_column("今日盈亏", justify="right")

    pnl_val = snapshot.today_pnl
    pnl_ratio = snapshot.today_pnl_ratio
    pnl = _pnl_text(pnl_val, pnl_ratio)

    table.add_row(
        f"{snapshot.asset.total_asset:,.0f}",
        f"{snapshot.asset.available_cash:,.0f}",
        f"{snapshot.total_market_value:,.0f}",
        pnl,
    )
    return Panel(table, title="账户概览", border_style="cyan")


def _build_positions(snapshot: MonitorSnapshot) -> Panel:
    """构建持仓明细面板。"""
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("标的", style="cyan")
    table.add_column("数量", justify="right")
    table.add_column("可用", justify="right")
    table.add_column("成本价", justify="right")
    table.add_column("现价", justify="right")
    table.add_column("市值", justify="right")
    table.add_column("浮动盈亏", justify="right")
    table.add_column("盈亏%", justify="right")

    if not snapshot.positions:
        table.add_row("[dim]无持仓[/dim]", "", "", "", "", "", "", "")
    else:
        for pos in snapshot.positions:
            pnl_style = "green" if pos.unrealized_pnl > 0 else (
                "red" if pos.unrealized_pnl < 0 else "white"
            )
            sign = "+" if pos.unrealized_pnl > 0 else ""
            table.add_row(
                pos.ticker,
                f"{pos.total_volume:,}",
                f"{pos.available_volume:,}",
                f"{pos.average_cost:.2f}",
                f"{pos.current_price:.2f}",
                f"{pos.market_value:,.0f}",
                Text(f"{sign}{pos.unrealized_pnl:,.0f}", style=pnl_style),
                Text(f"{sign}{pos.pnl_ratio:.2%}", style=pnl_style),
            )

    return Panel(table, title="持仓明细", border_style="cyan")


def _build_risk(snapshot: MonitorSnapshot) -> Panel:
    """构建风险指标面板。"""
    rm = snapshot.risk_metrics
    table = Table(show_header=True, header_style="bold", expand=True, box=None)
    table.add_column("指标")
    table.add_column("数值", justify="right")

    table.add_row("总仓位", f"{rm.total_position_ratio:.1%}")
    table.add_row("最大集中度", f"{rm.max_concentration:.1%}")
    table.add_row("持仓数量", str(rm.position_count))
    if snapshot.yesterday_asset > 0:
        table.add_row("当日回撤", f"{snapshot.today_pnl_ratio:.2%}")

    return Panel(table, title="风险指标", border_style="yellow")


def _build_alerts(snapshot: MonitorSnapshot) -> Panel | None:
    """构建告警面板。"""
    if not snapshot.alerts:
        return None

    table = Table(show_header=False, expand=True, box=None)
    for alert in snapshot.alerts:
        style = "bold red" if alert.level == "CRITICAL" else "yellow"
        table.add_row(Text(f"[{alert.level}] {alert.message}", style=style))

    return Panel(table, title="告警", border_style="red")


def build_dashboard(snapshot: MonitorSnapshot, interval: int = 3) -> Layout:
    """构建完整监控面板布局。"""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_column(
        Layout(name="overview", size=7),
        Layout(name="positions"),
        Layout(name="bottom"),
    )
    layout["bottom"].split_row(
        Layout(name="risk", ratio=1),
        Layout(name="alerts", ratio=1),
    )

    layout["header"].update(_build_header())
    layout["overview"].update(_build_overview(snapshot))
    layout["positions"].update(_build_positions(snapshot))
    layout["risk"].update(_build_risk(snapshot))

    alert_panel = _build_alerts(snapshot)
    if alert_panel:
        layout["alerts"].update(alert_panel)
    else:
        layout["alerts"].update(Panel("[dim]无告警[/dim]", title="告警", border_style="green"))

    now = datetime.now().strftime("%H:%M:%S")
    layout["footer"].update(
        Panel(
            Text(f"刷新间隔: {interval}s  |  按 Ctrl+C 退出  |  最后更新: {now}"),
            style="dim",
        )
    )

    return layout


def _load_yesterday_asset(args, snapshot_store: SnapshotStore) -> float:
    """加载昨日总资产。"""
    if args.yesterday_asset is not None:
        return args.yesterday_asset

    data = snapshot_store.load_latest()
    if data and "total_asset" in data:
        return data["total_asset"]

    return 0.0


def main() -> None:
    args = parse_args()

    try:
        settings = load_trading_config(args.config)
    except FileNotFoundError:
        print(f"配置文件未找到: {args.config}")
        sys.exit(1)

    monitor_cfg = settings.monitor
    interval = args.interval or monitor_cfg.refresh_interval

    # 初始化基础设施
    from src.infrastructure.gateway.qmt_market import QmtMarketGateway
    from src.infrastructure.gateway.qmt_trade import QmtTradeGateway

    qmt = settings.qmt
    if not qmt.userdata_path:
        print("QMT 路径未配置。请在配置文件中设置 qmt.userdata_path。")
        sys.exit(1)

    print("连接 QMT...")
    try:
        market_gw = QmtMarketGateway()
        trade_gw = QmtTradeGateway(
            path=qmt.userdata_path,
            session_id=qmt.session_id,
            account_id=qmt.account_id,
            account_type=qmt.account_type,
        )
    except Exception as e:
        print(f"QMT 连接失败: {e}")
        sys.exit(1)

    # 初始化告警引擎
    from src.domain.risk.services.alert_engine import AlertEngine
    from src.domain.risk.services.alert_rules.concentration_rule import ConcentrationRule
    from src.domain.risk.services.alert_rules.daily_loss_rule import DailyLossRule
    from src.domain.risk.services.alert_rules.position_ratio_rule import PositionRatioRule
    from src.domain.risk.services.alert_rules.stock_loss_rule import StockLossRule

    alert_engine: AlertEngine
    if args.no_alert:
        alert_engine = AlertEngine(rules=[])
    else:
        acfg = monitor_cfg.alerts
        alert_engine = AlertEngine(rules=[
            DailyLossRule(threshold=acfg.daily_loss_threshold),
            StockLossRule(threshold=acfg.stock_loss_threshold),
            PositionRatioRule(max_ratio=acfg.position_ratio_max, min_ratio=acfg.position_ratio_min),
            ConcentrationRule(threshold=acfg.concentration_max),
        ])

    # 加载昨日资产
    snapshot_store = SnapshotStore(snapshot_dir=monitor_cfg.snapshot_dir)
    yesterday_asset = _load_yesterday_asset(args, snapshot_store)

    # 初始化监控服务
    service = MonitorService(
        account_gateway=trade_gw,
        market_gateway=market_gw,
        alert_engine=alert_engine,
        yesterday_asset=yesterday_asset,
    )

    # 优雅退出
    running = True

    def _stop(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    # 首次快照
    snapshot = service.take_snapshot()

    console = Console()
    with Live(build_dashboard(snapshot, interval), console=console, refresh_per_second=1) as live:
        while running:
            try:
                snapshot = service.take_snapshot()
                live.update(build_dashboard(snapshot, interval))
            except Exception as e:
                console.print(f"[red]刷新失败: {e}[/red]")
            time.sleep(interval)

    # 退出时保存快照
    try:
        snapshot_store.save(datetime.now(), {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_asset": snapshot.asset.total_asset,
            "available_cash": snapshot.asset.available_cash,
            "market_value": snapshot.total_market_value,
            "positions": [
                {"ticker": p.ticker, "volume": p.total_volume,
                 "average_cost": p.average_cost, "close_price": p.current_price}
                for p in snapshot.positions
            ],
        })
    except Exception:
        pass

    print("监控已退出。")


if __name__ == "__main__":
    main()
