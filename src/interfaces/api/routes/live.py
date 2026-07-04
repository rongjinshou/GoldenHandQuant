"""实盘留痕只读端点 — 读 data/trading.db (SQLite, 与交易进程 WAL 并发安全)。

驾驶舱实盘页消费; 不触 QMT、不做写操作。库文件不存在时显式空态。
处理器为同步 def: FastAPI 自动丢线程池执行, sqlite I/O 不阻塞事件循环。
除 trading.db 外现还只读 trading.yaml（auto_trade 段摘要，经 _load_auto_trade_section
提取白名单键）与 data/trade_logs/*.json（ticket 留痕文件）。
设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md DD-6
     docs/feat/0612-interactive-dashboard/2026-06-12-interactive-dashboard-design.md §3.4
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, Query

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
def overview(db_path: str = Depends(get_trading_db_path)) -> dict:
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
def cycles(limit: int = Query(default=50, ge=1, le=500),
           db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"cycles": []}
    try:
        return {"cycles": _rows(
            conn, "SELECT * FROM trading_cycles ORDER BY cycle_time DESC LIMIT ?",
            (limit,))}
    finally:
        conn.close()


@router.get("/executions")
def executions(limit: int = Query(default=200, ge=1, le=1000),
               db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"executions": []}
    try:
        return {"executions": _rows(
            conn, "SELECT * FROM execution_records "
                  "ORDER BY submitted_at DESC LIMIT ?", (limit,))}
    finally:
        conn.close()


@router.get("/positions")
def positions(mode: str = "", db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"positions": [], "snapshot_time": None}
    try:
        if mode:
            rows = _rows(conn, """SELECT * FROM position_snapshots
                                  WHERE mode=? AND snapshot_time=(
                                    SELECT MAX(snapshot_time) FROM position_snapshots
                                    WHERE mode=?)
                                  ORDER BY symbol""", (mode, mode))
        else:
            rows = _rows(conn, """SELECT * FROM position_snapshots WHERE snapshot_time=(
                                    SELECT MAX(snapshot_time) FROM position_snapshots)
                                  ORDER BY symbol""")
        return {"positions": rows,
                "snapshot_time": rows[0]["snapshot_time"] if rows else None}
    finally:
        conn.close()


@router.get("/equity")
def equity(limit: int = Query(default=500, ge=1, le=2000), mode: str = "",
           db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"series": []}
    try:
        if mode:
            rows = _rows(conn, """SELECT * FROM (
                                    SELECT * FROM account_snapshots WHERE mode=?
                                    ORDER BY snapshot_time DESC LIMIT ?
                                  ) ORDER BY snapshot_time ASC""",
                         (mode, limit))
        else:
            rows = _rows(conn, """SELECT * FROM (
                                    SELECT * FROM account_snapshots
                                    ORDER BY snapshot_time DESC LIMIT ?
                                  ) ORDER BY snapshot_time ASC""", (limit,))
        return {"series": rows}
    finally:
        conn.close()


# ---- 交互驾驶舱扩展: 审计/预算/配置只读视角（设计 0612 §3.4）----

# 镜像 src/infrastructure/persistence/trading_store.py::_BUDGET_STATUSES —
# 预算口径跨 mode 统计(dry/live 同一真实账户), REJECTED/FAILED 不计
_BUDGET_STATUSES = ("DRY_RUN", "SUBMITTED", "FILLED", "PARTIAL", "CANCELED",
                    "TIMEOUT_CANCELED", "TIMEOUT_UNCANCELED", "ALIVE")


def get_trading_config_path() -> str:
    return os.environ.get("GHQ_TRADING_CONFIG", "resources/trading.yaml")


def get_trade_logs_dir() -> str:
    return os.environ.get("GHQ_TRADE_LOGS_DIR", "data/trade_logs")


def _load_auto_trade_section(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}
    section = data.get("auto_trade") or {}
    if not isinstance(section, dict):
        return {}
    keys = ("enabled", "mode", "strategy", "symbols", "execution_times",
            "min_confidence", "max_orders_per_cycle", "per_order_notional_cap",
            "daily_notional_cap", "daily_loss_limit_ratio")
    return {k: section[k] for k in keys if k in section}


@router.get("/audit")
def audit(limit: int = Query(default=100, ge=1, le=500), action: str = "",
          db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"logs": []}
    try:
        sql = "SELECT * FROM audit_logs"
        params: tuple = ()
        if action:
            sql += " WHERE action=?"
            params = (action,)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        try:
            return {"logs": _rows(conn, sql, (*params, limit))}
        except sqlite3.OperationalError:  # 旧库无 audit_logs 表
            return {"logs": []}
    finally:
        conn.close()


@router.get("/budget")
def budget(db_path: str = Depends(get_trading_db_path),
           cfg_path: str = Depends(get_trading_config_path)) -> dict:
    cfg = _load_auto_trade_section(cfg_path)
    today = date.today().isoformat()
    submitted = 0.0
    conn = _connect_ro(db_path)
    if conn is not None:
        try:
            placeholders = ", ".join("?" for _ in _BUDGET_STATUSES)
            try:
                # 与执行期防线同口径: 按 mode 隔离(0704 真单前置 DD-1), 展示当前配置 mode 的消耗
                cur = conn.execute(
                    f"SELECT COALESCE(SUM(notional), 0) FROM execution_records "
                    f"WHERE date(submitted_at)=? AND mode=? AND status IN ({placeholders})",
                    (today, str(cfg.get("mode", "dry_run")), *_BUDGET_STATUSES))
                submitted = float(cur.fetchone()[0])
            except sqlite3.OperationalError:
                pass
        finally:
            conn.close()
    daily_cap = cfg.get("daily_notional_cap")
    remaining = (float(daily_cap) - submitted
                 if isinstance(daily_cap, (int, float)) else None)
    return {"date": today, "submitted_notional": submitted,
            "daily_notional_cap": daily_cap,
            "per_order_notional_cap": cfg.get("per_order_notional_cap"),
            "remaining": remaining}


@router.get("/config")
def config(db_path: str = Depends(get_trading_db_path),
           cfg_path: str = Depends(get_trading_config_path)) -> dict:
    cfg = _load_auto_trade_section(cfg_path)
    cycles_today = 0
    conn = _connect_ro(db_path)
    if conn is not None:
        try:
            try:
                cycles_today = conn.execute(
                    "SELECT COUNT(*) FROM trading_cycles WHERE date(cycle_time)=?",
                    (date.today().isoformat(),)).fetchone()[0]
            except sqlite3.OperationalError:
                pass
        finally:
            conn.close()
    return {"config_exists": bool(cfg), "auto_trade": cfg,
            "today": {"expected_slots": cfg.get("execution_times") or [],
                      "cycles_today": cycles_today}}


@router.get("/cycles/{cycle_id}/executions")
def cycle_executions(cycle_id: str,
                     db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"executions": []}
    try:
        return {"executions": _rows(
            conn, "SELECT * FROM execution_records WHERE cycle_id=? "
                  "ORDER BY submitted_at", (cycle_id,))}
    finally:
        conn.close()


@router.get("/tickets")
def tickets(limit: int = Query(default=50, ge=1, le=200),
            logs_dir: str = Depends(get_trade_logs_dir)) -> dict:
    root = Path(logs_dir)
    if not root.is_dir():
        return {"tickets": []}
    out = []
    for fp in sorted(root.glob("*.json"), reverse=True)[:limit]:
        try:
            content = json.loads(fp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            content = None
        out.append({"file": fp.name, "content": content})
    return {"tickets": out}
