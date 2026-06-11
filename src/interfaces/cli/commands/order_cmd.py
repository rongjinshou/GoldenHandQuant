"""quant order 子命令 — 受控单笔下单（实盘）。

设计: docs/feat/0611-realtime-order/2026-06-11-realtime-order-design.md
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

_TRADE_LOG_DIR = Path("data/trade_logs")


def run_order(args: argparse.Namespace) -> None:
    match args.order_action:
        case "buy":
            _run_buy(args)


def _mask(account_id: str) -> str:
    if len(account_id) <= 4:
        return "****"
    return account_id[:2] + "*" * (len(account_id) - 4) + account_id[-2:]


def _resolve_account_id(qmt_settings, userdata_path: str, session_id: int) -> str:
    """账号解析: env → 配置(非占位) → 交易端枚举(仅一个时直用)。"""
    env_id = os.environ.get("QMT_ACCOUNT_ID", "").strip()
    if env_id:
        return env_id

    cfg_id = (qmt_settings.account_id or "").strip()
    if cfg_id and not cfg_id.startswith("${"):
        return cfg_id

    from src.infrastructure.gateway.xtquant_client import XtQuantTrader

    trader = XtQuantTrader(userdata_path, session_id + 1)
    trader.start()
    try:
        if trader.connect() != 0:
            raise RuntimeError(
                "交易端连接失败 (connect != 0): 请确认 QMT 以极简模式登录"
            )
        accounts = trader.query_account_infos() or []
    finally:
        trader.stop()

    stock_accounts = [a for a in accounts if getattr(a, "account_type", None) in (2, "STOCK")] or accounts
    if len(stock_accounts) == 1:
        aid = stock_accounts[0].account_id
        print(f"账号自动解析: {_mask(aid)} (交易端枚举)")
        return aid
    raise RuntimeError(
        f"无法唯一确定资金账号 (枚举到 {len(stock_accounts)} 个); "
        "请设置环境变量 QMT_ACCOUNT_ID 或在 trading.yaml 配置 qmt.account_id"
    )


def _run_buy(args: argparse.Namespace) -> None:
    from src.application.order_ticket_app import OrderTicketAppService
    from src.infrastructure.config.settings import load_trading_config
    from src.infrastructure.gateway.qmt_realtime_quote import QmtRealtimeQuoteFetcher
    from src.infrastructure.gateway.qmt_trade import QmtTradeGateway

    settings = load_trading_config(args.config)
    qmt = settings.qmt
    if not qmt.userdata_path:
        print(f"错误: QMT 路径未配置 ({args.config} qmt.userdata_path)")
        return

    print("=== 受控单笔买入 ===")
    print(f"标的: {args.symbol}  手数: {args.lots}  金额上限: {args.max_notional}")

    try:
        account_id = _resolve_account_id(qmt, qmt.userdata_path, qmt.session_id)
    except RuntimeError as e:
        print(f"错误: {e}")
        return

    gateway = QmtTradeGateway(
        path=qmt.userdata_path,
        session_id=qmt.session_id,
        account_id=account_id,
        account_type=qmt.account_type,
    )
    service = OrderTicketAppService(
        quote_fetcher=QmtRealtimeQuoteFetcher(),
        trade_gateway=gateway,
        account_gateway=gateway,
        max_notional=args.max_notional,
    )

    # 预览报价并确认
    if not args.yes:
        preview = QmtRealtimeQuoteFetcher().get_quotes([args.symbol]).get(args.symbol)
        if preview:
            print(f"当前报价: last={preview.last} ask1={preview.ask1} 前收={preview.prev_close}")
        answer = input(f"确认实盘买入 {args.symbol} {args.lots} 手? 输入 yes 继续: ")
        if answer.strip().lower() != "yes":
            print("已取消。")
            return

    result = service.buy_lots(args.symbol, lots=args.lots, poll_timeout=args.poll_timeout)

    # 审计落盘 (脱敏)
    audit = dict(result.ticket)
    audit["account_id"] = _mask(account_id)
    audit["accepted"] = result.accepted
    audit["final_status"] = result.final_status
    _TRADE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = _TRADE_LOG_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{args.symbol}.json"
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)

    print(f"\n{'-' * 60}")
    if not result.accepted:
        print(f"❌ 拒单: {result.reject_reason}")
    else:
        t = result.ticket
        print(f"✅ 已提交: 委托号 {result.order_id}")
        print(f"   限价 {t['price']} × {t['volume']} 股 = ¥{t['notional']:.2f}")
        print(f"   状态轨迹: {[s['status'] for s in t.get('status_trail', [])] or ['(未变化)']}")
        print(f"   终态: {result.final_status}")
        if result.final_status in ("ALIVE", "PARTIAL", "TIMEOUT"):
            print("   ⚠ 未全成: 限价单贴卖一, 通常稍后即成; 收盘未成自动失效。"
                  "如需撤单请在 QMT 客户端操作。")
    print(f"审计: {audit_path}")
