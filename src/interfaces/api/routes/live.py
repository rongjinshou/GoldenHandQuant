"""实盘留痕只读端点 — 读 data/trading.db (SQLite, 与交易进程 WAL 并发安全)。

驾驶舱实盘页消费; 不触 QMT、不做写操作。库文件不存在时显式空态。
设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md DD-6
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends

router = APIRouter()


def get_trading_db_path() -> str:
    return os.environ.get("GHQ_TRADING_DB", "data/trading.db")


def _connect_ro(path: str) -> sqlite3.Connection | None:
    if not Path(path).exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


@router.get("/overview")
async def overview(db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"db_exists": False, "latest_account": None, "cycles_today": 0,
                "executions_today": 0}
    try:
        today = date.today().isoformat()
        acct = _rows(conn, "SELECT * FROM account_snapshots "
                           "ORDER BY snapshot_time DESC LIMIT 1")
        cycles = conn.execute(
            "SELECT COUNT(*) FROM trading_cycles WHERE date(cycle_time)=?",
            (today,)).fetchone()[0]
        execs = conn.execute(
            "SELECT COUNT(*) FROM execution_records WHERE date(submitted_at)=?",
            (today,)).fetchone()[0]
        return {"db_exists": True, "latest_account": acct[0] if acct else None,
                "cycles_today": cycles, "executions_today": execs}
    finally:
        conn.close()


@router.get("/cycles")
async def cycles(limit: int = 50, db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"cycles": []}
    try:
        return {"cycles": _rows(
            conn, "SELECT * FROM trading_cycles ORDER BY cycle_time DESC LIMIT ?",
            (min(limit, 500),))}
    finally:
        conn.close()


@router.get("/executions")
async def executions(limit: int = 200,
                     db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"executions": []}
    try:
        return {"executions": _rows(
            conn, "SELECT * FROM execution_records "
                  "ORDER BY submitted_at DESC LIMIT ?", (min(limit, 1000),))}
    finally:
        conn.close()


@router.get("/positions")
async def positions(db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"positions": [], "snapshot_time": None}
    try:
        rows = _rows(conn, """SELECT * FROM position_snapshots WHERE snapshot_time=(
                                SELECT MAX(snapshot_time) FROM position_snapshots)
                              ORDER BY symbol""")
        return {"positions": rows,
                "snapshot_time": rows[0]["snapshot_time"] if rows else None}
    finally:
        conn.close()


@router.get("/equity")
async def equity(limit: int = 500,
                 db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"series": []}
    try:
        rows = _rows(conn, """SELECT * FROM (
                                SELECT * FROM account_snapshots
                                ORDER BY snapshot_time DESC LIMIT ?
                              ) ORDER BY snapshot_time ASC""", (min(limit, 2000),))
        return {"series": rows}
    finally:
        conn.close()
