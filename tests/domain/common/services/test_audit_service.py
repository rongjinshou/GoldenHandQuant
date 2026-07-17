"""审计领域服务测试（纯标准库 mock，无第三方依赖）。"""

from datetime import UTC, datetime, timedelta

from src.domain.common.services.audit_service import AuditService
from src.domain.common.value_objects.audit_log_entry import AuditLogEntry


class InMemoryAuditLogRepository:
    """内存审计日志仓储（测试用）。"""

    def __init__(self) -> None:
        self._entries: list[AuditLogEntry] = []

    def save(self, entry: AuditLogEntry) -> None:
        self._entries.append(entry)

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
        results = self._entries.copy()

        if user_id is not None:
            results = [e for e in results if e.user_id == user_id]
        if action is not None:
            results = [e for e in results if e.action == action]
        if resource_type is not None:
            results = [e for e in results if e.resource_type == resource_type]
        if start_time is not None:
            results = [e for e in results if e.timestamp >= start_time]
        if end_time is not None:
            results = [e for e in results if e.timestamp <= end_time]

        # 按时间倒序
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def count(
        self,
        *,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        return len(
            self.query(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                start_time=start_time,
                end_time=end_time,
                limit=999999,
            )
        )


class TestAuditService:
    def setup_method(self) -> None:
        self.repo = InMemoryAuditLogRepository()
        self.service = AuditService(self.repo)

    def test_log_action_creates_entry(self):
        entry = self.service.log_action(
            user_id="user1",
            action="place_order",
            resource_type="Order",
            resource_id="order-001",
        )
        assert entry.user_id == "user1"
        assert entry.action == "place_order"
        assert entry.resource_type == "Order"
        assert entry.resource_id == "order-001"
        assert entry.log_id  # 非空

    def test_log_action_persists_to_repository(self):
        self.service.log_action(
            user_id="user1",
            action="place_order",
            resource_type="Order",
            resource_id="order-001",
        )
        assert len(self.repo._entries) == 1

    def test_log_action_with_details(self):
        details = {"price": 10.5, "volume": 100}
        entry = self.service.log_action(
            user_id="user1",
            action="place_order",
            resource_type="Order",
            resource_id="order-001",
            details=details,
        )
        assert entry.details == details

    def test_log_action_with_ip_address(self):
        entry = self.service.log_action(
            user_id="user1",
            action="login",
            resource_type="Session",
            resource_id="session-001",
            ip_address="192.168.1.1",
        )
        assert entry.ip_address == "192.168.1.1"

    def test_log_action_with_custom_timestamp(self):
        ts = datetime(2025, 1, 15, 10, 30, 0)
        entry = self.service.log_action(
            user_id="user1",
            action="place_order",
            resource_type="Order",
            resource_id="order-001",
            timestamp=ts,
        )
        assert entry.timestamp == ts

    def test_query_by_user(self):
        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order", resource_id="o1",
        )
        self.service.log_action(
            user_id="user2", action="place_order", resource_type="Order", resource_id="o2",
        )
        self.service.log_action(
            user_id="user1", action="cancel_order", resource_type="Order", resource_id="o1",
        )

        results = self.service.query_by_user("user1")
        assert len(results) == 2
        assert all(e.user_id == "user1" for e in results)

    def test_query_by_action(self):
        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order", resource_id="o1",
        )
        self.service.log_action(
            user_id="user1", action="cancel_order", resource_type="Order", resource_id="o2",
        )
        self.service.log_action(
            user_id="user2", action="place_order", resource_type="Order", resource_id="o3",
        )

        results = self.service.query_by_action("place_order")
        assert len(results) == 2
        assert all(e.action == "place_order" for e in results)

    def test_query_by_date_range(self):
        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)

        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order",
            resource_id="o1", timestamp=last_week,
        )
        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order",
            resource_id="o2", timestamp=yesterday,
        )
        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order",
            resource_id="o3", timestamp=now,
        )

        results = self.service.query_by_date_range(
            start_time=yesterday - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert len(results) == 2

    def test_query_multi_condition(self):
        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order", resource_id="o1",
        )
        self.service.log_action(
            user_id="user1", action="cancel_order", resource_type="Order", resource_id="o2",
        )
        self.service.log_action(
            user_id="user2", action="place_order", resource_type="Order", resource_id="o3",
        )

        results = self.service.query(user_id="user1", action="place_order")
        assert len(results) == 1
        assert results[0].resource_id == "o1"

    def test_query_with_limit(self):
        for i in range(10):
            self.service.log_action(
                user_id="user1", action="place_order", resource_type="Order",
                resource_id=f"o{i}",
            )

        results = self.service.query_by_user("user1", limit=5)
        assert len(results) == 5

    def test_count_all(self):
        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order", resource_id="o1",
        )
        self.service.log_action(
            user_id="user2", action="cancel_order", resource_type="Order", resource_id="o2",
        )
        assert self.service.count() == 2

    def test_count_by_user(self):
        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order", resource_id="o1",
        )
        self.service.log_action(
            user_id="user2", action="place_order", resource_type="Order", resource_id="o2",
        )
        assert self.service.count(user_id="user1") == 1

    def test_count_by_action(self):
        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order", resource_id="o1",
        )
        self.service.log_action(
            user_id="user1", action="cancel_order", resource_type="Order", resource_id="o2",
        )
        assert self.service.count(action="place_order") == 1

    def test_count_by_date_range(self):
        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)

        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order",
            resource_id="o1", timestamp=yesterday,
        )
        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order",
            resource_id="o2", timestamp=now,
        )

        count = self.service.count(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert count == 1

    def test_query_returns_sorted_by_time_desc(self):
        t1 = datetime(2025, 1, 1, 10, 0, 0)
        t2 = datetime(2025, 1, 1, 11, 0, 0)
        t3 = datetime(2025, 1, 1, 12, 0, 0)

        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order",
            resource_id="o1", timestamp=t1,
        )
        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order",
            resource_id="o2", timestamp=t3,
        )
        self.service.log_action(
            user_id="user1", action="place_order", resource_type="Order",
            resource_id="o3", timestamp=t2,
        )

        results = self.service.query_by_user("user1")
        assert results[0].resource_id == "o2"  # t3 (最新)
        assert results[1].resource_id == "o3"  # t2
        assert results[2].resource_id == "o1"  # t1 (最旧)
