"""审计日志仓储 SQLite 实现（Infrastructure 层）。

append-only 设计，禁止修改/删除。
"""

import json
from datetime import UTC, datetime

from src.domain.common.value_objects.audit_log_entry import AuditLogEntry
from src.infrastructure.persistence.database import Database


class SqliteAuditLogRepository:
    """审计日志仓储 SQLite 实现。"""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        """创建审计日志表（如果不存在）。"""
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS audit_logs (
                log_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '{}',
                ip_address TEXT NOT NULL DEFAULT ''
            )"""
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs (user_id)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp)"
        )
        self._db.commit()

    def save(self, entry: AuditLogEntry) -> None:
        """保存一条审计日志（append-only）。"""
        self._db.execute(
            """INSERT INTO audit_logs
               (log_id, user_id, action, resource_type, resource_id,
                timestamp, details, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.log_id,
                entry.user_id,
                entry.action,
                entry.resource_type,
                entry.resource_id,
                entry.timestamp.isoformat(),
                json.dumps(entry.details, ensure_ascii=False),
                entry.ip_address,
            ),
        )
        self._db.commit()

    def query(
        self,
        *,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        """查询审计日志（支持多条件过滤）。"""
        sql = "SELECT * FROM audit_logs WHERE 1=1"
        params: list[object] = []

        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        if action is not None:
            sql += " AND action = ?"
            params.append(action)
        if resource_type is not None:
            sql += " AND resource_type = ?"
            params.append(resource_type)
        if start_time is not None:
            sql += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time is not None:
            sql += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = self._db.execute(sql, tuple(params))
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def count(
        self,
        *,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """统计符合条件的审计日志数量。"""
        sql = "SELECT COUNT(*) FROM audit_logs WHERE 1=1"
        params: list[object] = []

        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        if action is not None:
            sql += " AND action = ?"
            params.append(action)
        if resource_type is not None:
            sql += " AND resource_type = ?"
            params.append(resource_type)
        if start_time is not None:
            sql += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time is not None:
            sql += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        cursor = self._db.execute(sql, tuple(params))
        row = cursor.fetchone()
        return row[0] if row else 0

    @staticmethod
    def _row_to_entry(row: object) -> AuditLogEntry:
        """将数据库行转换为 AuditLogEntry 值对象。"""
        return AuditLogEntry(
            log_id=row["log_id"],
            user_id=row["user_id"],
            action=row["action"],
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]).replace(
                tzinfo=UTC
            ),
            details=json.loads(row["details"]),
            ip_address=row["ip_address"],
        )
