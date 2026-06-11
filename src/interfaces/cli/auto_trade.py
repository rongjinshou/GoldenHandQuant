"""自动交易 CLI 入口 — 完整接线 (dry-run 默认 / live 三重确认)。

用法:
    quant auto-trade --once --enable          # 单循环 (dry-run)
    quant auto-trade                           # 守护循环 (execution_times 触发)
    quant auto-trade --once --live             # live 还需配置 mode:live + enabled:true
设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md DD-2/DD-7
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

from src.infrastructure.config.settings import AutoTradeSettings, load_trading_config

logger = logging.getLogger(__name__)


def resolve_mode(settings: AutoTradeSettings, *, live_flag: bool) -> str:
    """live 三重确认: 配置 mode=live + 配置 enabled=true + CLI --live。"""
    if settings.mode == "live" and settings.enabled and live_flag:
        return "live"
    if settings.mode == "live" or live_flag:
        logger.warning("live 确认不齐全 (mode=%s enabled=%s --live=%s), 降级 dry_run",
                       settings.mode, settings.enabled, live_flag)
    return "dry_run"


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _build_service(settings, mode: str):
    """组装全部依赖 (需 QMT 客户端在线)。"""
    from src.application.auto_trade_app import AutoTradeAppService, AutoTradeConfig
    from src.application.live_signal_service import LiveSignalService
    from src.domain.common.services.audit_service import AuditService
    from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer
    from src.infrastructure.gateway.dry_run_trade import DryRunTradeGateway
    from src.infrastructure.gateway.qmt_market import QmtMarketGateway
    from src.infrastructure.gateway.qmt_realtime_quote import QmtRealtimeQuoteFetcher
    from src.infrastructure.gateway.qmt_trade import QmtTradeGateway
    from src.infrastructure.persistence.repositories.audit_log_repository import (
        SqliteAuditLogRepository,
    )
    from src.infrastructure.persistence.trading_store import TradingStore
    from src.interfaces.cli.cli_utils import resolve_account_id

    at = settings.auto_trade
    qmt = settings.qmt
    if not qmt.userdata_path:
        raise RuntimeError("QMT 路径未配置 (trading.yaml qmt.userdata_path)")

    account_id = resolve_account_id(qmt, qmt.userdata_path, qmt.session_id)
    real_gateway = QmtTradeGateway(
        path=qmt.userdata_path, session_id=qmt.session_id,
        account_id=account_id, account_type=qmt.account_type,
    )
    trade_gateway = real_gateway if mode == "live" else DryRunTradeGateway(real_gateway)

    store = TradingStore(at.db_path)
    signal_service = LiveSignalService(
        market_gateway=QmtMarketGateway(),
        account_gateway=real_gateway,
        trade_gateway=trade_gateway,
        sizer=FixedRatioSizer(ratio=at.position_ratio),
        bar_lookback=at.bar_lookback,
    )
    config = AutoTradeConfig(
        mode=mode, strategy=at.strategy, symbols=at.symbols,
        min_confidence=at.min_confidence,
        max_orders_per_cycle=at.max_orders_per_cycle,
        per_order_notional_cap=at.per_order_notional_cap,
        daily_notional_cap=at.daily_notional_cap,
        daily_loss_limit_ratio=at.daily_loss_limit_ratio,
        poll_timeout_seconds=at.poll_timeout_seconds,
    )
    return AutoTradeAppService(
        signal_service=signal_service,
        quote_fetcher=QmtRealtimeQuoteFetcher(),
        trade_gateway=trade_gateway,
        account_gateway=real_gateway,
        store=store,
        audit=AuditService(SqliteAuditLogRepository(store.db)),
        config=config,
    )


def main(args: argparse.Namespace | None = None) -> None:
    if args is None:
        parser = argparse.ArgumentParser(description="GoldenHandQuant 自动交易引擎")
        parser.add_argument("--config", default="resources/trading.yaml")
        parser.add_argument("--once", action="store_true", help="仅执行一次循环")
        parser.add_argument("--enable", action="store_true",
                            help="临时启用 (仅 dry-run 生效)")
        parser.add_argument("--live", action="store_true",
                            help="真实下单 (还需配置 mode:live + enabled:true)")
        args = parser.parse_args()

    _setup_logging()
    settings = load_trading_config(args.config)
    at = settings.auto_trade

    if not (at.enabled or args.enable):
        logger.error("自动交易未启用: 请配置 auto_trade.enabled: true 或加 --enable")
        sys.exit(1)

    mode = resolve_mode(at, live_flag=getattr(args, "live", False))
    logger.info("=== 自动交易引擎 === 模式=%s 策略=%s 标的=%s 执行时刻=%s",
                mode.upper(), at.strategy, ",".join(at.symbols), at.execution_times)
    if mode == "live":
        logger.warning(">>> LIVE 模式: 将提交真实订单! 单笔上限 ¥%.0f 日上限 ¥%.0f <<<",
                       at.per_order_notional_cap, at.daily_notional_cap)

    try:
        service = _build_service(settings, mode)
    except RuntimeError as e:
        logger.error("依赖组装失败: %s", e)
        sys.exit(1)

    if args.once:
        s = service.run_cycle()
        print(f"循环 {s.cycle_id} [{s.mode}]: 信号 {s.signals_generated} | "
              f"提交 {s.orders_submitted} | 拒绝 {s.orders_rejected} | "
              f"失败 {s.orders_failed} | 金额 ¥{s.notional_submitted:.2f}"
              + (f" | note: {s.note}" if s.note else ""))
        print(f"留痕: {at.db_path} (驾驶舱实盘页可视)")
        return

    from src.application.trading_scheduler import TradingScheduler
    scheduler = TradingScheduler(
        check_interval_seconds=at.check_interval_seconds,
        execution_times=at.execution_times,
    )
    scheduler.register_cycle_callback(lambda now: service.run_cycle())
    scheduler.start()
    logger.info("守护循环已启动 (Ctrl+C 停止)")

    def _shutdown(signum, frame):
        logger.info("收到停止信号, 正在关闭...")
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
