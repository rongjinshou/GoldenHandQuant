"""审计日志条目值对象（纯标准库，零第三方依赖）。

记录系统中所有关键操作的不可变审计轨迹。
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class AuditLogEntry:
    """审计日志条目值对象。

    记录谁在什么时间执行了什么操作，用于安全审计和操作追溯。
    不可变设计，一旦创建不可修改。

    Attributes:
        log_id: 全局唯一日志 ID (UUID)。
        user_id: 执行操作的用户标识。
        action: 操作类型（如 "place_order"、"cancel_order"、"modify_strategy"）。
        resource_type: 资源类型（如 "Order"、"Position"、"Strategy"）。
        resource_id: 资源标识（如 order_id、strategy_name）。
        timestamp: 操作发生时间（UTC）。
        details: 操作附加详情（不可变字典）。
        ip_address: 操作来源 IP 地址。
    """

    log_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, object] = field(default_factory=dict)
    ip_address: str = ""
