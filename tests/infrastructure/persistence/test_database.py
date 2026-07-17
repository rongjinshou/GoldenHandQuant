from src.infrastructure.persistence.database import Database


class TestDatabase:
    def test_connection_sets_busy_timeout(self, tmp_path):
        """confirmed-gap(2026-07-10 六西格玛体检 M8): trading.db 有 3 类跨进程写入方
        (auto-trade 守护 / sync_live_account --watch / 手动 --once), 未设 busy_timeout
        时并发写立即抛 'database is locked' 且各 save_* 无重试。设 5s 等待窗。"""
        db = Database(str(tmp_path / "t.db"))

        timeout_ms = db.execute("PRAGMA busy_timeout").fetchone()[0]

        assert timeout_ms == 5000
        db.close()

    def test_connection_keeps_wal_and_foreign_keys(self, tmp_path):
        db = Database(str(tmp_path / "t.db"))

        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        db.close()
