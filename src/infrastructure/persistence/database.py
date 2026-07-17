import sqlite3
from pathlib import Path


class Database:
    """SQLite 连接管理（使用 sqlite3 标准库，Domain 层零依赖）。"""

    def __init__(self, db_path: str = "data/backtest.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: 守护模式下连接在主线程创建、由调度线程串行使用
        # (单写者顺序访问, 无并发竞争); 默认 True 会让调度线程每次写入即抛错。
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        # WAL 下 NORMAL 仅在断电时丢最后事务、不损坏库; /mnt/c 上 FULL 的逐次 fsync 代价过高
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        # 跨进程写者(守护 auto-trade / sync_live_account --watch / 手动 --once)并存,
        # 无等待窗时第二写者立即 'database is locked' 且上层 save_* 无重试
        self._conn.execute("PRAGMA busy_timeout=5000")

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        return self._conn.executemany(sql, params_list)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
