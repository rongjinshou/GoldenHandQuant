"""把 QMT 真实账户的资产/持仓快照 *只读* 写入 data/trading.db，供驾驶舱实盘页显示真账户。

与回测/纸面种子无关: 这里读的是你 QMT 交易端里的**真实**资金账户。
只做两件事——查资产、查持仓，然后落一条 account_snapshot + 一批 position_snapshots
(mode=live)。**绝不下单、绝不撤单、不跑任何交易循环**。

前置(必须):
  1. QMT 交易端以「极简模式」登录 (否则 XtQuantTrader.connect() 失败, 读不到账户);
  2. 账号来源: 环境变量 QMT_ACCOUNT_ID > trading.yaml qmt.account_id > 交易端自动枚举(唯一时)。

用法 (Windows Python; QMT 客户端需在线):
  $WIN_PYTHON scripts/sync_live_account.py
  $WIN_PYTHON scripts/sync_live_account.py --watch 30   # 每 30s 落一条, 攒成实盘权益曲线

实盘页是只读的 (Web 永不碰 xtquant); 真账户由本脚本在 Windows 侧落盘, 网页再读 trading.db。
设计: docs/feat/0612-interactive-dashboard/2026-06-12-interactive-dashboard-design.md §12
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.getcwd())

from src.infrastructure.config.settings import load_trading_config
from src.infrastructure.persistence.trading_store import TradingStore
from src.interfaces.cli.cli_utils import mask_account_id, resolve_account_id


def _fetch_last_prices(symbols: list[str]) -> dict[str, float]:
    """实时快照取最新价填 position_snapshots.last_price (失败则留空, 不阻断)。"""
    if not symbols:
        return {}
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata
        ticks = xtdata.get_full_tick(symbols) or {}
    except Exception as e:  # noqa: BLE001 — 行情读不到不影响账户快照
        print(f"  (取最新价失败, last_price 留空: {e!r})")
        return {}
    out: dict[str, float] = {}
    for s in symbols:
        tick = ticks.get(s) or {}
        px = float(tick.get("lastPrice") or 0)
        if px > 0:
            out[s] = px
    return out


def sync_once(db_path: str, config_path: str) -> bool:
    """读真实账户 → 落一条快照。返回是否成功。"""
    settings = load_trading_config(config_path)
    qmt = settings.qmt
    if not qmt.userdata_path:
        print("✗ trading.yaml 未配置 qmt.userdata_path")
        return False

    try:
        account_id = resolve_account_id(qmt, qmt.userdata_path, qmt.session_id)
    except Exception as e:  # noqa: BLE001
        print(f"✗ 账号解析失败: {e}")
        print("  → 请确认 QMT 交易端已以「极简模式」登录; 或设置环境变量 QMT_ACCOUNT_ID。")
        return False

    from src.infrastructure.gateway.qmt_trade import QmtTradeGateway
    gw = QmtTradeGateway(
        path=qmt.userdata_path, session_id=qmt.session_id,
        account_id=account_id, account_type=qmt.account_type,
    )
    asset = gw.get_asset()
    if asset is None:
        print(f"✗ 读不到账户 {mask_account_id(account_id)} 的资产 "
              "(交易端未登录极简模式 / 账号不匹配?)")
        return False
    positions = gw.get_positions()

    now = datetime.now().isoformat()
    market_value = asset.total_asset - asset.available_cash - asset.frozen_cash
    last_px = _fetch_last_prices([p.ticker for p in positions])

    store = TradingStore(db_path)
    try:
        store.save_account_snapshot(
            snapshot_time=now, mode="live",
            total_asset=asset.total_asset, available_cash=asset.available_cash,
            frozen_cash=asset.frozen_cash, market_value=market_value,
        )
        if positions:
            store.save_position_snapshots(
                snapshot_time=now, mode="live",
                rows=[{"symbol": p.ticker, "total_volume": p.total_volume,
                       "available_volume": p.available_volume,
                       "average_cost": p.average_cost,
                       "last_price": last_px.get(p.ticker)} for p in positions],
            )
    finally:
        store.close()

    print(f"✓ {now[:19]} 账户 {mask_account_id(account_id)}: "
          f"总资产 ¥{asset.total_asset:,.2f} · 可用 ¥{asset.available_cash:,.2f} · "
          f"持仓市值 ¥{market_value:,.2f} · {len(positions)} 只持仓 → {db_path}")
    return True


def main() -> None:
    p = argparse.ArgumentParser(description="QMT 真实账户快照 → trading.db (只读)")
    p.add_argument("--config", default="resources/trading.yaml")
    p.add_argument("--db", default="data/trading.db")
    p.add_argument("--watch", type=int, default=0,
                   help="秒; >0 时循环落快照攒权益曲线 (Ctrl+C 停)")
    args = p.parse_args()

    if args.watch <= 0:
        ok = sync_once(args.db, args.config)
        sys.exit(0 if ok else 1)

    print(f"=== 实盘账户快照守护 === 每 {args.watch}s 落一条 (Ctrl+C 停)")
    try:
        while True:
            sync_once(args.db, args.config)
            time.sleep(args.watch)
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
