"""SqliteAuditLogRepository 测试 — 临时库文件，覆盖建表/写入/查询/统计。"""
from datetime import datetime, timedelta

from src.domain.common.value_objects.audit_log_entry import AuditLogEntry
from src.infrastructure.persistence.database import Database
from src.infrastructure.persistence.repositories.audit_log_repository import (
    SqliteAuditLogRepository,
)


def _entry(action: str = "place_order", ts: datetime | None = None) -> AuditLogEntry:
    return AuditLogEntry(
        user_id="auto-trade",
        action=action,
        resource_type="Order",
        resource_id="ord-1",
        timestamp=ts or datetime(2026, 6, 10, 9, 35),
        details={"price": 5.05},
    )


class TestSqliteAuditLogRepository:
    def test_save_then_query_roundtrip(self, tmp_path):
        repo = SqliteAuditLogRepository(Database(str(tmp_path / "t.db")))
        repo.save(_entry())

        rows = repo.query()

        assert len(rows) == 1
        assert rows[0].action == "place_order"
        assert rows[0].details == {"price": 5.05}

    def test_query_filters_by_action(self, tmp_path):
        repo = SqliteAuditLogRepository(Database(str(tmp_path / "t.db")))
        repo.save(_entry("place_order"))
        repo.save(_entry("cancel_order"))

        rows = repo.query(action="cancel_order")

        assert [r.action for r in rows] == ["cancel_order"]

    def test_count_by_time_window(self, tmp_path):
        repo = SqliteAuditLogRepository(Database(str(tmp_path / "t.db")))
        base = datetime(2026, 6, 10, 9, 0)
        repo.save(_entry(ts=base))
        repo.save(_entry(ts=base + timedelta(days=1)))

        assert repo.count(start_time=base, end_time=base + timedelta(hours=1)) == 1
