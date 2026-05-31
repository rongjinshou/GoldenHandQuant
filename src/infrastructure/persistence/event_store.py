"""SQLite 事件存储实现。

基于 SQLite 的 append-only 事件持久化，实现 domain 层 EventStore 接口。
支持按 aggregate_id / event_type / 时间范围查询。
"""

import json
from datetime import datetime

from src.domain.common.domain_event import DomainEvent
from src.domain.common.event_store import EventStore
from src.infrastructure.persistence.database import Database


class SQLiteEventStore(EventStore):
    """SQLite 事件存储。

    使用独立的 events 表存储领域事件，append-only 设计。

    Args:
        db: Database 实例或 SQLite 数据库文件路径。
    """

    def __init__(self, db: Database | str) -> None:
        if isinstance(db, str):
            self._db = Database(db)
        else:
            self._db = db
        self._init_table()

    def _init_table(self) -> None:
        """初始化事件表和索引。"""
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS domain_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                aggregate_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_aggregate
            ON domain_events(aggregate_id, aggregate_type)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type
            ON domain_events(event_type)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_timestamp
            ON domain_events(timestamp)
        """)
        self._db.commit()

    def append(self, event: DomainEvent) -> None:
        """追加一条领域事件。"""
        self._db.execute(
            """
            INSERT INTO domain_events
                (event_id, event_type, aggregate_id, aggregate_type, timestamp, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.event_type,
                event.aggregate_id,
                event.aggregate_type,
                event.timestamp.isoformat(),
                json.dumps(event.payload, ensure_ascii=False),
            ),
        )
        self._db.commit()

    def append_batch(self, events: list[DomainEvent]) -> None:
        """批量追加领域事件（事务性）。"""
        if not events:
            return
        self._db.executemany(
            """
            INSERT INTO domain_events
                (event_id, event_type, aggregate_id, aggregate_type, timestamp, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    e.event_id,
                    e.event_type,
                    e.aggregate_id,
                    e.aggregate_type,
                    e.timestamp.isoformat(),
                    json.dumps(e.payload, ensure_ascii=False),
                )
                for e in events
            ],
        )
        self._db.commit()

    def get_events(
        self,
        aggregate_id: str | None = None,
        event_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[DomainEvent]:
        """查询领域事件。"""
        conditions: list[str] = []
        params: list[object] = []

        if aggregate_id is not None:
            conditions.append("aggregate_id = ?")
            params.append(aggregate_id)
        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)
        if start_time is not None:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())
        if end_time is not None:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT event_id, event_type, aggregate_id, aggregate_type, timestamp, payload
            FROM domain_events
            WHERE {where_clause}
            ORDER BY timestamp ASC
            LIMIT ?
        """
        params.append(limit)

        rows = self._db.execute(query, tuple(params)).fetchall()
        return [self._row_to_event(row) for row in rows]

    def get_events_by_aggregate(self, aggregate_id: str) -> list[DomainEvent]:
        """获取指定聚合根的全部事件（按时间升序）。"""
        rows = self._db.execute(
            """
            SELECT event_id, event_type, aggregate_id, aggregate_type, timestamp, payload
            FROM domain_events
            WHERE aggregate_id = ?
            ORDER BY timestamp ASC
            """,
            (aggregate_id,),
        ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def count(self, aggregate_id: str | None = None) -> int:
        """统计事件数量。"""
        if aggregate_id is not None:
            row = self._db.execute(
                "SELECT COUNT(*) FROM domain_events WHERE aggregate_id = ?",
                (aggregate_id,),
            ).fetchone()
        else:
            row = self._db.execute("SELECT COUNT(*) FROM domain_events").fetchone()
        return row[0] if row else 0

    @staticmethod
    def _row_to_event(row: tuple[str, str, str, str, str, str]) -> DomainEvent:
        """将数据库行转换为 DomainEvent。"""
        event_id, event_type, aggregate_id, aggregate_type, ts_str, payload_str = row
        return DomainEvent(
            event_id=event_id,
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            timestamp=datetime.fromisoformat(ts_str),
            payload=json.loads(payload_str),
        )
