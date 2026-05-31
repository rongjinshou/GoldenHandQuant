"""审计日志仓储接口（纯标准库，零第三方依赖）。

定义审计日志的持久化契约，具体实现在 Infrastructure 层。
"""

from datetime import datetime
from typing import Protocol

from src.domain.common.value_objects.audit_log_entry import AuditLogEntry


class AuditLogRepository(Protocol):
    """审计日志仓储接口。

    append-only 设计，仅支持保存和查询，禁止修改/删除。
    """

    def save(self, entry: AuditLogEntry) -> None:
        """保存一条审计日志（append-only）。

        Args:
            entry: 审计日志条目。
        """
        ...

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
        """查询审计日志（支持多条件过滤）。

        Args:
            user_id: 按用户 ID 过滤。
            action: 按操作类型过滤。
            resource_type: 按资源类型过滤。
            start_time: 起始时间（含）。
            end_time: 结束时间（含）。
            limit: 返回条数上限，默认 100。

        Returns:
            符合条件的审计日志列表，按时间倒序排列。
        """
        ...

    def count(
        self,
        *,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """统计符合条件的审计日志数量。

        Args:
            user_id: 按用户 ID 过滤。
            action: 按操作类型过滤。
            resource_type: 按资源类型过滤。
            start_time: 起始时间（含）。
            end_time: 结束时间（含）。

        Returns:
            符合条件的记录总数。
        """
        ...
