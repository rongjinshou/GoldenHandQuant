"""离线重放 auto-trade 真实流水, 为驾驶舱实盘页种入「纸面前向(dry_run)」数据。

不触 QMT、不下真单: 用 data/market.duckdb 历史日线驱动 *真正的*
``AutoTradeAppService.run_cycle()`` —— 信号扫描 / 盘前安全闸 / 资金与持仓校验 /
日级预算 / 留痕入库, 全部走生产代码路径。区别只在三个离线替身:

* ``PaperFillGateway`` —— ``is_dry_run=True`` (装配口径一致), 但下单经
  ``MockTradeGateway`` 按当日历史 bar 真实撮合 (A 股成本/滑点/流动性/涨跌停);
  ``get_asset`` 对持仓做盯市(MTM), 让权益曲线真实反映行情, 而非只扣手续费。
* ``BarQuoteFetcher`` —— 用当日收盘构造 ``Quote`` (时间戳=重放时刻, 不过期)。
* 注入的 ``clock`` —— 把"当前时刻"钉在重放交易日 14:50 (连续竞价时段内)。

产物写 data/trading.db (与实盘进程同一只读口径), 全部 mode=dry_run。
这是开发/演示用的种子工具, 与生产 auto-trade CLI 完全隔离 (从不导入 xtquant)。

用法:
    $WIN_PYTHON scripts/seed_paper_trading.py            # 默认两年日频重放
    $WIN_PYTHON scripts/seed_paper_trading.py --start 2025-01-01 --capital 60000
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.getcwd())

from src.application.auto_trade_app import AutoTradeAppService, AutoTradeConfig
from src.application.live_signal_service import LiveSignalService
from src.domain.account.entities.asset import Asset
from src.domain.common.services.audit_service import AuditService
from src.domain.market.value_objects.quote import Quote
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer
from src.infrastructure.gateway.duckdb_history_data import DuckDBHistoryDataFetcher
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway
from src.infrastructure.persistence.repositories.audit_log_repository import (
    SqliteAuditLogRepository,
)
from src.infrastructure.persistence.trading_store import TradingStore

# 低价主板标的(沪 60xxxx / 深 000xxx, 过盘前 symbol_scope 闸); 价低 → 单笔
# 100 股就远低于 ¥5000 硬顶, 重放能真实成交而非全数被金额闸拒。
DEFAULT_SYMBOLS = [
    "601988.SH",  # 中国银行 ~5
    "601398.SH",  # 工商银行 ~6
    "601006.SH",  # 大秦铁路 ~6
    "000002.SZ",  # 万科A ~7
    "600000.SH",  # 浦发银行 ~10
    "000001.SZ",  # 平安银行 ~11
    "000021.SZ",  # 深科技 ~20
    "600096.SH",  # 云天化 ~23
    "600585.SH",  # 海螺水泥 ~23
    "600030.SH",  # 中信证券 ~24
]


class PaperFillGateway:
    """纸面前向(离线重放)交易+账户网关。

    撮合透传 MockTradeGateway (原子成交, 失败抛 OrderSubmitError → 上层记 FAILED);
    账户读取在现金基础上叠加持仓盯市市值, 使权益曲线真实跟随行情。
    """

    is_dry_run = True  # 与 config.mode=dry_run 配对, 通过装配一致性校验

    def __init__(self, mock: MockTradeGateway, market: MockMarketGateway) -> None:
        self._mock = mock
        self._market = market

    # ---- ITradeGateway ----
    def place_order(self, order):
        return self._mock.place_order(order)

    def query_order_status(self, order_id: str) -> str:
        # MockTradeGateway 原子撮合: 走到这里即已成交 (拒单已在 place_order 抛出)
        return "FILLED"

    def cancel_order(self, order_id: str) -> bool:
        return True

    # ---- IAccountGateway (盯市) ----
    def get_asset(self, account_id: str | None = None) -> Asset | None:
        base = self._mock.get_asset(account_id)
        if base is None:
            return None
        market_value = 0.0
        for pos in self._mock.get_positions(account_id):
            bars = self._market.get_recent_bars(pos.ticker, Timeframe.DAY_1, 1)
            px = bars[-1].close if bars else pos.average_cost
            market_value += pos.total_volume * px
        return Asset(
            account_id=base.account_id,
            total_asset=round(base.available_cash + base.frozen_cash + market_value, 2),
            available_cash=base.available_cash,
            frozen_cash=base.frozen_cash,
        )

    def get_positions(self, account_id: str | None = None):
        return self._mock.get_positions(account_id)


class BarQuoteFetcher:
    """离线报价源: 当日 bar 收盘 → Quote, 时间戳钉在重放时刻 (保证不过期)。"""

    def __init__(self, market: MockMarketGateway) -> None:
        self._market = market
        self._now = datetime.now()

    def set_now(self, now: datetime) -> None:
        self._now = now

    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        out: dict[str, Quote] = {}
        for s in symbols:
            q = self.subscribe_first_tick(s)
            if q is not None:
                out[s] = q
        return out

    def subscribe_first_tick(self, symbol: str, timeout: float = 3.0) -> Quote | None:
        bars = self._market.get_recent_bars(symbol, Timeframe.DAY_1, 1)
        if not bars:
            return None
        bar = bars[-1]
        last = bar.close
        prev = getattr(bar, "prev_close", 0.0) or bar.open
        if last <= 0 or prev <= 0:
            return None
        return Quote(
            symbol=symbol,
            last=last,
            bid1=round(last * 0.999, 2),
            ask1=round(last * 1.001, 2),
            prev_close=prev,
            timestamp=self._now,
        )


def _reset_db(db_path: str) -> None:
    for suffix in ("", "-wal", "-shm"):
        p = Path(db_path + suffix)
        if p.exists():
            p.unlink()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="实盘页纸面前向数据种子(离线重放)")
    p.add_argument("--db", default="data/trading.db")
    p.add_argument("--market-db", default=os.environ.get("GHQ_MARKET_DB",
                                                         "data/market.duckdb"))
    p.add_argument("--start", default="2024-06-13", help="重放开始(交易日)")
    p.add_argument("--end", default="2026-06-11", help="重放结束(交易日)")
    p.add_argument("--capital", type=float, default=80000.0, help="纸面账户初始资金")
    p.add_argument("--ratio", type=float, default=0.05, help="单笔资金比例(FixedRatioSizer)")
    p.add_argument("--strategy", default="dual_ma")
    p.add_argument("--symbols", default="", help="逗号分隔; 留空用内置低价主板组合")
    p.add_argument("--no-reset", action="store_true", help="不清空既有 trading.db")
    p.add_argument("--yes", action="store_true",
                   help="目标是生产留痕库 data/trading.db 且要清空时, 必须显式确认")
    return p.parse_args()


PRODUCTION_DB = "data/trading.db"


def main() -> None:
    args = parse_args()

    # 清空生产实盘留痕库(审计/execution_records)不可恢复, 必须显式确认;
    # 置于装载数据之前, 尽早失败
    will_reset_production = (
        not args.no_reset
        and Path(args.db).resolve() == Path(PRODUCTION_DB).resolve()
    )
    if will_reset_production and not args.yes:
        print("✗ 默认目标是生产实盘留痕库 data/trading.db, 清空它需要显式 --yes;\n"
              "  或用 --db 指向演示库, 或 --no-reset 保留现有数据。")
        sys.exit(2)

    symbols = ([s.strip() for s in args.symbols.split(",") if s.strip()]
               or DEFAULT_SYMBOLS)

    print(f"=== 纸面前向重放 === 策略={args.strategy} 标的={len(symbols)} "
          f"资金=¥{args.capital:,.0f} 区间={args.start}~{args.end}")

    # 1) 装载历史 bar (多留 ~1 年前置, 让均线类策略有足够回看窗口)
    load_start = (datetime.strptime(args.start, "%Y-%m-%d").replace(
        year=datetime.strptime(args.start, "%Y-%m-%d").year - 1).strftime("%Y-%m-%d"))
    market = MockMarketGateway()
    fetcher = DuckDBHistoryDataFetcher(args.market_db, fallback=None)
    loaded = 0
    try:
        for s in symbols:
            bars = fetcher.fetch_history_bars(s, Timeframe.DAY_1, load_start, args.end)
            if bars:
                market.load_bars(bars)
                loaded += 1
    finally:
        fetcher.close()
    if loaded == 0:
        print("✗ 行情库无任何标的数据, 终止。请先 data refresh。")
        sys.exit(1)
    print(f"已装载 {loaded}/{len(symbols)} 标的历史日线 (前置自 {load_start})")

    # 2) 离线替身 + 真实应用服务装配
    if not args.no_reset:
        _reset_db(args.db)
    from src.infrastructure.persistence.status_registry_loader import (
        build_status_registry_from_db,
    )
    status_registry = build_status_registry_from_db(
        start=args.start, end=datetime.now().strftime("%Y-%m-%d"))
    mock = MockTradeGateway(market_gateway=market, initial_capital=args.capital,
                            stock_status_registry=status_registry)
    gateway = PaperFillGateway(mock, market)
    quotes = BarQuoteFetcher(market)
    signal_service = LiveSignalService(
        market_gateway=market, account_gateway=gateway, trade_gateway=gateway,
        sizer=FixedRatioSizer(ratio=args.ratio), bar_lookback=120,
    )
    store = TradingStore(args.db)
    audit = AuditService(SqliteAuditLogRepository(store.db))

    clock = {"now": datetime.now()}
    config = AutoTradeConfig(
        mode="dry_run", strategy=args.strategy, symbols=symbols,
        min_confidence=0.0, max_orders_per_cycle=3,
        per_order_notional_cap=5000.0, daily_notional_cap=20000.0,
        daily_loss_limit_ratio=0.05, poll_timeout_seconds=1.0,
    )
    service = AutoTradeAppService(
        signal_service=signal_service, quote_fetcher=quotes,
        trade_gateway=gateway, account_gateway=gateway, store=store, audit=audit,
        config=config, clock=lambda: clock["now"], sleep=lambda *_: None,
    )

    # 3) 逐交易日重放
    cs = datetime.strptime(args.start, "%Y-%m-%d")
    ce = datetime.strptime(args.end, "%Y-%m-%d")
    dates = [t for t in market.get_all_timestamps(Timeframe.DAY_1) if cs <= t <= ce]
    print(f"重放交易日 {len(dates)} 天 ...")

    n_sub = n_rej = n_fail = 0
    for d in dates:
        market.set_current_time(d.replace(hour=15, minute=0))  # 当日 bar 可见
        clock["now"] = d.replace(hour=14, minute=50)           # 连续竞价时段内
        quotes.set_now(clock["now"])
        s = service.run_cycle()
        n_sub += s.orders_submitted
        n_rej += s.orders_rejected
        n_fail += s.orders_failed
        mock.daily_settlement()  # 释放 T+1, 次日方可卖出

    final = gateway.get_asset()
    store.close()
    print(f"✓ 完成: 提交 {n_sub} · 拒绝 {n_rej} · 失败 {n_fail} | "
          f"终值 ¥{final.total_asset:,.2f} (本金 ¥{args.capital:,.0f})")
    print(f"留痕: {args.db} —— 驾驶舱实盘页轮询可见 (全部 dry_run)")


if __name__ == "__main__":
    main()
