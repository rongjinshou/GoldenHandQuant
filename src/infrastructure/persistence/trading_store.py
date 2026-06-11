"""交易留痕库 (SQLite WAL) — 循环/执行记录/账户与持仓快照。

独立于 market.duckdb(研究资产): 交易进程长驻写、驾驶舱只读轮询。
设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md DD-4
"""

from __future__ import annotations

from src.infrastructure.persistence.database import Database

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS trading_cycles (
        cycle_id TEXT PRIMARY KEY, cycle_time TEXT NOT NULL, mode TEXT NOT NULL,
        strategy TEXT NOT NULL, signals_generated INTEGER DEFAULT 0,
        orders_submitted INTEGER DEFAULT 0, orders_rejected INTEGER DEFAULT 0,
        orders_failed INTEGER DEFAULT 0, notional_submitted REAL DEFAULT 0,
        note TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now', 'localtime'))
    )""",
    """CREATE TABLE IF NOT EXISTS execution_records (
        order_id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL, mode TEXT NOT NULL,
        symbol TEXT NOT NULL, direction TEXT NOT NULL,
        signal_price REAL, exec_price REAL, volume INTEGER, notional REAL,
        status TEXT NOT NULL, reject_reason TEXT, strategy_name TEXT,
        confidence REAL, submitted_at TEXT NOT NULL, final_status_at TEXT,
        status_trail TEXT DEFAULT '[]'
    )""",
    """CREATE TABLE IF NOT EXISTS account_snapshots (
        snapshot_time TEXT NOT NULL, mode TEXT NOT NULL, total_asset REAL,
        available_cash REAL, frozen_cash REAL, market_value REAL
    )""",
    """CREATE TABLE IF NOT EXISTS position_snapshots (
        snapshot_time TEXT NOT NULL, mode TEXT NOT NULL, symbol TEXT NOT NULL,
        total_volume INTEGER, available_volume INTEGER,
        average_cost REAL, last_price REAL
    )""",
]

# 占用预算的状态(意向已发出): 拒单/失败不占。
# CANCELED 必须占: QMT 部成部撤(ORDER_PART_CANCEL)也映射为 CANCELED,
# 已成交部分是真实敞口, 不占预算会导致同日重复追单突破日上限。
_BUDGET_STATUSES = ("DRY_RUN", "SUBMITTED", "FILLED", "PARTIAL", "CANCELED",
                    "TIMEOUT_CANCELED", "TIMEOUT_UNCANCELED", "ALIVE")


class TradingStore:
    """交易留痕统一入口。execution_records 即订单全生命周期账本(单一来源)。"""

    def __init__(self, db_path: str = "data/trading.db") -> None:
        self._db = Database(db_path)
        for ddl in _SCHEMA:
            self._db.execute(ddl)
        self._db.commit()

    @property
    def db(self) -> Database:
        """供审计仓储共用同一连接/文件。"""
        return self._db

    def close(self) -> None:
        self._db.close()

    # ------------------------------------------------------------- cycles
    def save_cycle_start(self, *, cycle_id: str, cycle_time: str, mode: str,
                         strategy: str) -> None:
        self._db.execute(
            "INSERT INTO trading_cycles (cycle_id, cycle_time, mode, strategy) "
            "VALUES (?, ?, ?, ?)",
            (cycle_id, cycle_time, mode, strategy),
        )
        self._db.commit()

    def finalize_cycle(self, *, cycle_id: str, signals_generated: int,
                       orders_submitted: int, orders_rejected: int,
                       orders_failed: int, notional_submitted: float,
                       note: str = "") -> None:
        self._db.execute(
            """UPDATE trading_cycles SET signals_generated=?, orders_submitted=?,
               orders_rejected=?, orders_failed=?, notional_submitted=?, note=?
               WHERE cycle_id=?""",
            (signals_generated, orders_submitted, orders_rejected,
             orders_failed, notional_submitted, note, cycle_id),
        )
        self._db.commit()

    def load_cycles(self, limit: int = 50) -> list[dict]:
        cur = self._db.execute(
            "SELECT * FROM trading_cycles ORDER BY cycle_time DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in cur.fetchall()]

    # --------------------------------------------------------- executions
    def save_execution(self, row: dict) -> None:
        cols = ("order_id", "cycle_id", "mode", "symbol", "direction",
                "signal_price", "exec_price", "volume", "notional", "status",
                "reject_reason", "strategy_name", "confidence", "submitted_at",
                "final_status_at", "status_trail")
        self._db.execute(
            f"INSERT OR REPLACE INTO execution_records ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})",
            tuple(row.get(c) for c in cols),
        )
        self._db.commit()

    def load_executions(self, limit: int = 200) -> list[dict]:
        cur = self._db.execute(
            "SELECT * FROM execution_records ORDER BY submitted_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

    def today_submitted_notional(self, *, today: str) -> float:
        """当日已提交金额——跨 mode 统计: dry_run/live 背后是同一真实账户,
        切换模式不得重置日级预算防线。"""
        cur = self._db.execute(
            f"""SELECT COALESCE(SUM(notional), 0) FROM execution_records
                WHERE date(submitted_at)=?
                  AND status IN ({', '.join('?' for _ in _BUDGET_STATUSES)})""",
            (today, *_BUDGET_STATUSES),
        )
        return float(cur.fetchone()[0])

    def today_traded_keys(self, *, today: str) -> set[str]:
        """当日已交易 symbol:direction——同样跨 mode, 防模式切换后重复下单。"""
        cur = self._db.execute(
            f"""SELECT DISTINCT symbol || ':' || direction FROM execution_records
                WHERE date(submitted_at)=?
                  AND status IN ({', '.join('?' for _ in _BUDGET_STATUSES)})""",
            (today, *_BUDGET_STATUSES),
        )
        return {r[0] for r in cur.fetchall()}

    # ---------------------------------------------------------- snapshots
    def save_account_snapshot(self, *, snapshot_time: str, mode: str,
                              total_asset: float, available_cash: float,
                              frozen_cash: float, market_value: float) -> None:
        self._db.execute(
            "INSERT INTO account_snapshots VALUES (?, ?, ?, ?, ?, ?)",
            (snapshot_time, mode, total_asset, available_cash, frozen_cash,
             market_value),
        )
        self._db.commit()

    def day_start_equity(self, *, today: str) -> float | None:
        """当日首个权益快照——跨 mode: 同一真实账户只有一条权益曲线。"""
        cur = self._db.execute(
            """SELECT total_asset FROM account_snapshots
               WHERE date(snapshot_time)=?
               ORDER BY snapshot_time ASC LIMIT 1""",
            (today,),
        )
        row = cur.fetchone()
        return float(row[0]) if row else None

    def load_account_series(self, *, mode: str, limit: int = 500) -> list[dict]:
        cur = self._db.execute(
            """SELECT * FROM account_snapshots WHERE mode=?
               ORDER BY snapshot_time DESC LIMIT ?""",
            (mode, limit),
        )
        return [dict(r) for r in reversed(cur.fetchall())]

    def save_position_snapshots(self, *, snapshot_time: str, mode: str,
                                rows: list[dict]) -> None:
        self._db.executemany(
            "INSERT INTO position_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(snapshot_time, mode, r["symbol"], r["total_volume"],
              r["available_volume"], r["average_cost"], r.get("last_price"))
             for r in rows],
        )
        self._db.commit()

    def load_latest_positions(self, *, mode: str) -> list[dict]:
        cur = self._db.execute(
            """SELECT * FROM position_snapshots WHERE mode=? AND snapshot_time=(
                 SELECT MAX(snapshot_time) FROM position_snapshots WHERE mode=?
               ) ORDER BY symbol""",
            (mode, mode),
        )
        return [dict(r) for r in cur.fetchall()]
