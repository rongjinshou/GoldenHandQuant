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


def _build_notification_hub(settings):
    """装配 NotificationHub — 接线所有配置的通知渠道。"""
    from src.application.notification_hub import NotificationHub
    from src.infrastructure.notification.factory import create_notification_gateway

    gw = create_notification_gateway(settings.risk.notification)
    if gw is None:
        return None
    return NotificationHub(gateways=[gw])


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
    from src.domain.common.services.audit_service import AuditService
    from src.infrastructure.gateway.dry_run_trade import DryRunTradeGateway
    from src.infrastructure.gateway.qmt_market import QmtMarketGateway
    from src.infrastructure.gateway.qmt_realtime_quote import QmtRealtimeQuoteFetcher
    from src.infrastructure.gateway.qmt_trade import QmtTradeGateway
    from src.infrastructure.persistence.repositories.audit_log_repository import (
        SqliteAuditLogRepository,
    )
    from src.infrastructure.persistence.trading_store import TradingStore
    from src.interfaces.cli._auto_trade_wiring import build_live_signal_service
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

    # 行情探针 fail-fast(0626 阶段1 DD-4): xtdata 断连时不做后续 TradingStore/DuckDB
    # 装配; RuntimeError(含探针诊断指引)由 main 的 except RuntimeError 优雅退出。
    market_gateway = QmtMarketGateway()
    market_gateway.ensure_ready()

    store = TradingStore(at.db_path)
    signal_service, symbols = build_live_signal_service(
        at,
        market_gateway=market_gateway,
        account_gateway=real_gateway,
        trade_gateway=trade_gateway,
    )
    config = AutoTradeConfig(
        mode=mode, strategy=at.strategy, symbols=symbols,
        min_confidence=at.min_confidence,
        max_orders_per_cycle=at.max_orders_per_cycle,
        per_order_notional_cap=at.per_order_notional_cap,
        per_order_notional_ceiling=at.per_order_notional_ceiling,
        daily_notional_cap=at.daily_notional_cap,
        daily_loss_limit_ratio=at.daily_loss_limit_ratio,
        poll_timeout_seconds=at.poll_timeout_seconds,
        max_position_ratio=at.max_position_ratio,
        max_total_position_ratio=at.max_total_position_ratio,
    )
    return AutoTradeAppService(
        signal_service=signal_service,
        quote_fetcher=QmtRealtimeQuoteFetcher(),
        trade_gateway=trade_gateway,
        account_gateway=real_gateway,
        store=store,
        audit=AuditService(SqliteAuditLogRepository(store.db)),
        config=config,
        notification_hub=_build_notification_hub(settings),
        calendar=_build_trading_calendar(),
        circuit_breaker=_build_circuit_breaker(at),
    )


def _build_circuit_breaker(at):
    """T6: 熔断器装配(状态由 service 经 TradingStore 跨进程存续)。"""
    if not at.breaker_enabled:
        logger.warning("熔断器已按配置禁用(breaker_enabled: false)")
        return None
    from src.domain.risk.services.circuit_breaker import CircuitBreaker

    return CircuitBreaker(
        max_daily_loss=at.breaker_max_daily_loss,
        max_total_drawdown=at.breaker_max_total_drawdown,
    )


def _build_trading_calendar():
    """M7: 交易日历装配。优先交易所日历表(trade_calendar, 含未来节假日,
    0711 tushare 沉淀·兑现①); 表空回退 bars 推导; 库不可用降级 None(仅告警)。"""
    from src.domain.trade.services.trading_calendar import TradingCalendar

    try:
        from src.infrastructure.persistence.market_data_store import MarketDataStore

        store = MarketDataStore(read_only=True)
        try:
            exchange_cal = store.load_trade_calendar()
            if exchange_cal is not None:
                open_days, known_until = exchange_cal
                calendar = TradingCalendar(trading_days=open_days, known_until=known_until)
            else:
                calendar = TradingCalendar.from_dates(store.trading_dates())
        finally:
            store.close()
        if calendar is not None:
            logger.info("交易日历已装配(%s): %d 个交易日, 已知至 %s",
                        "交易所日历" if exchange_cal is not None else "bars推导",
                        len(calendar.trading_days), calendar.known_until)
        return calendar
    except Exception as e:
        logger.warning("交易日历装配失败(降级为无日历, 时段闸退回周末判定): %s", e)
        return None


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
    try:
        settings = load_trading_config(args.config)
    except Exception as e:
        logger.error("加载配置失败 (%s): %s", args.config, e)
        sys.exit(1)
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
        calendar=_build_trading_calendar(),
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
