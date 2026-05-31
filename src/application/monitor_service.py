import logging
from datetime import datetime

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway
from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.account.value_objects.position_detail import PositionDetail
from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.risk.services.alert_engine import AlertEngine
from src.domain.risk.value_objects.risk_metrics import RiskMetrics

logger = logging.getLogger(__name__)


class MonitorService:
    """实盘监控编排服务。

    流程: 获取数据 → 计算盈亏 → 计算风险 → 触发告警 → 产出 MonitorSnapshot。
    """

    def __init__(
        self,
        account_gateway: IAccountGateway,
        market_gateway: IMarketGateway,
        alert_engine: AlertEngine | None = None,
        yesterday_asset: float = 0.0,
    ) -> None:
        self._account_gw = account_gateway
        self._market_gw = market_gateway
        self._alert_engine = alert_engine or AlertEngine()
        self._yesterday_asset = yesterday_asset

    def take_snapshot(self) -> MonitorSnapshot:
        """获取一次完整的监控快照。"""
        asset = self._account_gw.get_asset()
        if asset is None:
            asset = Asset(account_id="unknown")

        positions = self._account_gw.get_positions()
        position_details = self._build_position_details(positions)
        risk_metrics = self._calc_risk_metrics(asset, position_details)

        snapshot = MonitorSnapshot(
            timestamp=datetime.now(),
            asset=asset,
            positions=position_details,
            risk_metrics=risk_metrics,
            yesterday_asset=self._yesterday_asset,
        )

        snapshot.alerts = self._alert_engine.check(snapshot)
        return snapshot

    def _build_position_details(self, positions: list[Position]) -> list[PositionDetail]:
        """构建持仓明细，获取实时行情。"""
        details: list[PositionDetail] = []
        for pos in positions:
            current_price = self._fetch_price(pos.ticker, pos.average_cost)
            details.append(PositionDetail(
                ticker=pos.ticker,
                total_volume=pos.total_volume,
                available_volume=pos.available_volume,
                average_cost=pos.average_cost,
                current_price=current_price,
            ))
        return details

    def _fetch_price(self, ticker: str, fallback: float) -> float:
        """获取最新价，失败时回退到成本价。"""
        try:
            bars = self._market_gw.get_recent_bars(ticker, Timeframe.DAY_1, limit=1)
            if bars:
                return bars[-1].close
        except Exception:
            logger.debug("Failed to fetch price for %s, using cost", ticker)
        return fallback

    def _calc_risk_metrics(
        self, asset: Asset, positions: list[PositionDetail],
    ) -> RiskMetrics:
        """计算风险指标。"""
        total_asset = asset.total_asset
        if total_asset <= 0:
            return RiskMetrics(
                total_position_ratio=0.0, max_concentration=0.0,
                position_count=len(positions),
            )

        market_value = sum(p.market_value for p in positions)
        total_ratio = market_value / total_asset

        max_single = max((p.market_value for p in positions), default=0.0)
        concentration = max_single / total_asset

        return RiskMetrics(
            total_position_ratio=total_ratio,
            max_concentration=concentration,
            position_count=len(positions),
        )
