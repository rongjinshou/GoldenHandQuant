"""审计领域服务（纯标准库，零第三方依赖）。

协调审计日志的记录和查询，封装审计相关的业务规则。
"""

import logging
from datetime import datetime

from src.domain.common.interfaces.repositories.audit_log_repository import (
    AuditLogRepository,
)
from src.domain.common.value_objects.audit_log_entry import AuditLogEntry

logger = logging.getLogger(__name__)


class AuditService:
    """审计领域服务。

    职责:
    - 记录谁在什么时间执行了什么操作
    - 支持按日期/操作类型/用户查询
    - 确保审计日志的完整性
    """

    def __init__(self, repository: AuditLogRepository) -> None:
        self._repository = repository

    def log_action(
        self,
        *,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, object] | None = None,
        ip_address: str = "",
        timestamp: datetime | None = None,
    ) -> AuditLogEntry:
        """记录一条审计日志。

        Args:
            user_id: 执行操作的用户标识。
            action: 操作类型（如 "place_order"、"cancel_order"）。
            resource_type: 资源类型（如 "Order"、"Strategy"）。
            resource_id: 资源标识。
            details: 操作附加详情。
            ip_address: 操作来源 IP。
            timestamp: 操作时间，默认为当前 UTC 时间。

        Returns:
            创建的审计日志条目。
        """
        entry = AuditLogEntry(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            timestamp=timestamp or datetime.now(),  # noqa: DTZ005
        )
        self._repository.save(entry)
        logger.debug(
            "审计日志: user=%s action=%s resource=%s/%s",
            user_id,
            action,
            resource_type,
            resource_id,
        )
        return entry

    def query_by_user(
        self, user_id: str, limit: int = 100,
    ) -> list[AuditLogEntry]:
        """查询指定用户的审计日志。

        Args:
            user_id: 用户标识。
            limit: 返回条数上限。

        Returns:
            该用户的审计日志列表（时间倒序）。
        """
        return self._repository.query(user_id=user_id, limit=limit)

    def query_by_action(
        self, action: str, limit: int = 100,
    ) -> list[AuditLogEntry]:
        """查询指定操作类型的审计日志。

        Args:
            action: 操作类型。
            limit: 返回条数上限。

        Returns:
            该操作类型的审计日志列表（时间倒序）。
        """
        return self._repository.query(action=action, limit=limit)

    def query_by_date_range(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        """查询指定时间范围内的审计日志。

        Args:
            start_time: 起始时间（含）。
            end_time: 结束时间（含）。
            limit: 返回条数上限。

        Returns:
            该时间范围内的审计日志列表（时间倒序）。
        """
        return self._repository.query(
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

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
        """多条件组合查询审计日志。

        Args:
            user_id: 按用户 ID 过滤。
            action: 按操作类型过滤。
            resource_type: 按资源类型过滤。
            start_time: 起始时间（含）。
            end_time: 结束时间（含）。
            limit: 返回条数上限。

        Returns:
            符合条件的审计日志列表（时间倒序）。
        """
        return self._repository.query(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

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
        return self._repository.count(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            start_time=start_time,
            end_time=end_time,
        )
