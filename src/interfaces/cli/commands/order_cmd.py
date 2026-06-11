"""quant order 子命令 — 受控单笔下单（实盘）。

设计: docs/feat/0611-realtime-order/2026-06-11-realtime-order-design.md
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.interfaces.cli.cli_utils import mask_account_id, resolve_account_id

_TRADE_LOG_DIR = Path("data/trade_logs")


def run_order(args: argparse.Namespace) -> None:
    match args.order_action:
        case "buy":
            _run_buy(args)


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
        account_id = resolve_account_id(qmt, qmt.userdata_path, qmt.session_id)
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
    audit["account_id"] = mask_account_id(account_id)
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
