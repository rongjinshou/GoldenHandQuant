"""配置变更日志值对象（纯标准库，零第三方依赖）。

记录配置参数的变更历史，用于审计追溯和变更回滚。
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfigChangeLog:
    """配置变更日志值对象。

    不可变设计，记录一次配置参数变更的完整快照，支持审计追溯和回滚。

    Attributes:
        change_id: 全局唯一变更 ID (UUID)。
        config_path: 变更参数的点分路径（如 "costs.commission_rate"）。
        old_value: 变更前的值。
        new_value: 变更后的值。
        timestamp: 变更发生时间（UTC）。
        user_id: 触发变更的用户标识（"system" 表示文件监听触发）。
    """

    change_id: str = field(default_factory=lambda: str(uuid4()))
    config_path: str
    old_value: object
    new_value: object
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    user_id: str = "system"
