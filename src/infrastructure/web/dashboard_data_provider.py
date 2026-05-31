import logging
from datetime import datetime

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway
from src.domain.backtest.value_objects.dashboard_snapshot import (
    DashboardSnapshot,
    EquityCurvePoint,
    PositionSnapshot,
    RiskStatus,
    StrategyStatus,
)
from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.market.value_objects.timeframe import Timeframe

logger = logging.getLogger(__name__)


class DashboardDataProvider:
    """Dashboard 数据提供者。

    从各网关聚合数据，构建 DashboardSnapshot。
    """

    def __init__(
        self,
        account_gateway: IAccountGateway,
        market_gateway: IMarketGateway,
        yesterday_asset: float = 0.0,
    ) -> None:
        self._account_gw = account_gateway
        self._market_gw = market_gateway
        self._yesterday_asset = yesterday_asset
        self._equity_history: list[EquityCurvePoint] = []
        self._strategy_statuses: list[StrategyStatus] = []

    def set_yesterday_asset(self, value: float) -> None:
        """设置昨日资产，用于计算当日盈亏。"""
        self._yesterday_asset = value

    def update_strategy_statuses(self, statuses: list[StrategyStatus]) -> None:
        """更新策略运行状态（由应用层注入）。"""
        self._strategy_statuses = list(statuses)

    def get_snapshot(self) -> DashboardSnapshot:
        """获取当前 Dashboard 快照。"""
        asset = self._account_gw.get_asset()
        if asset is None:
            asset = Asset(account_id="unknown")

        positions = self._account_gw.get_positions()
        position_snapshots = self._build_position_snapshots(positions)

        daily_pnl = 0.0
        daily_pnl_ratio = 0.0
        if self._yesterday_asset > 0:
            daily_pnl = asset.total_asset - self._yesterday_asset
            daily_pnl_ratio = daily_pnl / self._yesterday_asset

        total_market_value = sum(ps.market_value for ps in position_snapshots)
        risk_status = self._calc_risk_status(asset, position_snapshots)

        snapshot = DashboardSnapshot(
            timestamp=datetime.now(),
            total_asset=asset.total_asset,
            available_cash=asset.available_cash,
            frozen_cash=asset.frozen_cash,
            daily_pnl=daily_pnl,
            daily_pnl_ratio=daily_pnl_ratio,
            total_market_value=total_market_value,
            positions=position_snapshots,
            risk_status=risk_status,
            strategies=self._strategy_statuses,
        )

        # 记录收益曲线
        self._record_equity_point(asset.total_asset, daily_pnl)

        return snapshot

    def get_equity_curve(self, limit: int = 252) -> list[EquityCurvePoint]:
        """获取收益曲线数据。"""
        return self._equity_history[-limit:]

    def _build_position_snapshots(self, positions: list[Position]) -> list[PositionSnapshot]:
        """构建持仓快照列表。"""
        snapshots: list[PositionSnapshot] = []
        for pos in positions:
            current_price = self._fetch_price(pos.ticker, pos.average_cost)
            market_value = pos.total_volume * current_price
            unrealized_pnl = (current_price - pos.average_cost) * pos.total_volume
            pnl_ratio = 0.0
            if pos.average_cost > 0:
                pnl_ratio = (current_price - pos.average_cost) / pos.average_cost

            snapshots.append(PositionSnapshot(
                ticker=pos.ticker,
                total_volume=pos.total_volume,
                available_volume=pos.available_volume,
                average_cost=pos.average_cost,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                pnl_ratio=pnl_ratio,
            ))
        return snapshots

    def _fetch_price(self, ticker: str, fallback: float) -> float:
        """获取最新价，失败时回退到成本价。"""
        try:
            bars = self._market_gw.get_recent_bars(ticker, Timeframe.DAY_1, limit=1)
            if bars:
                return bars[-1].close
        except Exception:
            logger.debug("Failed to fetch price for %s, using cost", ticker)
        return fallback

    def _calc_risk_status(
        self, asset: Asset, positions: list[PositionSnapshot],
    ) -> RiskStatus:
        """计算风控状态。"""
        total_asset = asset.total_asset
        if total_asset <= 0:
            return RiskStatus(
                total_position_ratio=0.0,
                max_concentration=0.0,
                position_count=len(positions),
            )

        market_value = sum(p.market_value for p in positions)
        total_ratio = market_value / total_asset
        max_single = max((p.market_value for p in positions), default=0.0)
        concentration = max_single / total_asset

        return RiskStatus(
            total_position_ratio=total_ratio,
            max_concentration=concentration,
            position_count=len(positions),
        )

    def _record_equity_point(self, total_asset: float, daily_pnl: float) -> None:
        """记录收益曲线数据点。"""
        initial = self._equity_history[0].total_asset if self._equity_history else total_asset
        cumulative_return = (total_asset - initial) / initial if initial > 0 else 0.0

        self._equity_history.append(EquityCurvePoint(
            date=datetime.now(),
            total_asset=total_asset,
            daily_pnl=daily_pnl,
            cumulative_return=cumulative_return,
        ))
