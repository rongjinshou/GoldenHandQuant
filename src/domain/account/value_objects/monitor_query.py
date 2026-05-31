"""监控查询 DTO。

应用层通过 MonitorQuery 向监控子域传递查询意图，
避免 MonitorService 直接暴露领域实体给接口层。
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class MonitorQuery:
    """监控查询参数。

    Attributes:
        account_id: 账户 ID，None 表示全部账户。
        include_positions: 是否包含持仓信息。
        include_risk: 是否包含风控状态。
        include_alerts: 是否包含活跃告警。
    """

    account_id: str | None = None
    include_positions: bool = True
    include_risk: bool = True
    include_alerts: bool = False
