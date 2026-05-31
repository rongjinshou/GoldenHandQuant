from dataclasses import dataclass, field
from datetime import datetime

from src.domain.account.entities.asset import Asset
from src.domain.account.value_objects.position_detail import PositionDetail
from src.domain.risk.value_objects.alert import Alert
from src.domain.risk.value_objects.risk_metrics import RiskMetrics


@dataclass(slots=True, kw_only=True)
class MonitorSnapshot:
    """监控面板快照 — 聚合账户、持仓、风险的实时状态。"""

    timestamp: datetime
    asset: Asset
    positions: list[PositionDetail] = field(default_factory=list)
    risk_metrics: RiskMetrics = field(default_factory=lambda: RiskMetrics(
        total_position_ratio=0.0, max_concentration=0.0, position_count=0,
    ))
    alerts: list[Alert] = field(default_factory=list)
    yesterday_asset: float = 0.0

    @property
    def today_pnl(self) -> float:
        if self.yesterday_asset <= 0:
            return 0.0
        return self.asset.total_asset - self.yesterday_asset

    @property
    def today_pnl_ratio(self) -> float:
        if self.yesterday_asset <= 0:
            return 0.0
        return self.today_pnl / self.yesterday_asset

    @property
    def total_market_value(self) -> float:
        return sum(p.market_value for p in self.positions)
