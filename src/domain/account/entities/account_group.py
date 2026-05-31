from dataclasses import dataclass, field
from datetime import datetime

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position


@dataclass(slots=True, kw_only=True)
class AccountGroup:
    """账户组实体 -- 将多个交易账户组织为一个逻辑单元。

    提供跨账户的全局视角:
    - 汇总各子账户资产
    - 汇总各子账户持仓（按 ticker 合并）
    - 全局风控指标（总资产、总持仓市值、集中度等）

    Attributes:
        group_id: 账户组唯一标识。
        group_name: 账户组名称（展示用）。
        account_ids: 组内子账户 ID 列表。
        created_at: 创建时间。
    """

    group_id: str
    group_name: str
    account_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def add_account(self, account_id: str) -> None:
        """添加子账户。

        Args:
            account_id: 子账户 ID。

        Raises:
            ValueError: 如果账户已存在于组中。
        """
        if account_id in self.account_ids:
            raise ValueError(f"Account '{account_id}' already in group '{self.group_id}'")
        self.account_ids.append(account_id)

    def remove_account(self, account_id: str) -> None:
        """移除子账户。

        Args:
            account_id: 子账户 ID。

        Raises:
            ValueError: 如果账户不在组中。
        """
        if account_id not in self.account_ids:
            raise ValueError(f"Account '{account_id}' not in group '{self.group_id}'")
        self.account_ids.remove(account_id)

    def aggregate_assets(self, assets: list[Asset]) -> dict[str, float]:
        """汇总组内所有账户资产。

        Args:
            assets: 各子账户的 Asset 列表（需包含 group 内所有 account_id）。

        Returns:
            包含 total_asset, available_cash, frozen_cash 的汇总字典。
        """
        asset_map = {a.account_id: a for a in assets}
        total_asset = 0.0
        available_cash = 0.0
        frozen_cash = 0.0

        for account_id in self.account_ids:
            asset = asset_map.get(account_id)
            if asset is not None:
                total_asset += asset.total_asset
                available_cash += asset.available_cash
                frozen_cash += asset.frozen_cash

        return {
            "total_asset": total_asset,
            "available_cash": available_cash,
            "frozen_cash": frozen_cash,
        }

    def aggregate_positions(self, positions: list[Position]) -> dict[str, Position]:
        """按 ticker 汇总组内所有账户持仓。

        返回的 Position 使用 group_id 作为 account_id，volume 为各账户之和，
        average_cost 为加权平均成本。

        Args:
            positions: 各子账户的 Position 列表。

        Returns:
            ticker -> 合并后 Position 的字典。
        """
        merged: dict[str, dict[str, float]] = {}
        # merged[ticker] = {"total_volume": ..., "cost_sum": ..., "available_volume": ...}

        for pos in positions:
            if pos.account_id not in self.account_ids:
                continue
            ticker = pos.ticker
            if ticker not in merged:
                merged[ticker] = {
                    "total_volume": 0,
                    "cost_sum": 0.0,
                    "available_volume": 0,
                }
            merged[ticker]["total_volume"] += pos.total_volume
            merged[ticker]["cost_sum"] += pos.total_volume * pos.average_cost
            merged[ticker]["available_volume"] += pos.available_volume

        result: dict[str, Position] = {}
        for ticker, data in merged.items():
            total_vol = int(data["total_volume"])
            avg_cost = data["cost_sum"] / total_vol if total_vol > 0 else 0.0
            result[ticker] = Position(
                account_id=self.group_id,
                ticker=ticker,
                total_volume=total_vol,
                available_volume=int(data["available_volume"]),
                average_cost=avg_cost,
            )

        return result

    def compute_concentration(
        self,
        aggregated_assets: dict[str, float],
        aggregated_positions: dict[str, Position],
        current_prices: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """计算全局集中度指标。

        Args:
            aggregated_assets: aggregate_assets() 的返回值。
            aggregated_positions: aggregate_positions() 的返回值。
            current_prices: ticker -> 当前价格映射；为 None 时使用 average_cost 近似。

        Returns:
            包含 max_concentration, max_concentration_ticker, position_count 的字典。
        """
        total_asset = aggregated_assets.get("total_asset", 0.0)
        if total_asset <= 0:
            return {
                "max_concentration": 0.0,
                "max_concentration_ticker": "",
                "position_count": 0,
            }

        max_ratio = 0.0
        max_ticker = ""

        for ticker, pos in aggregated_positions.items():
            if current_prices and ticker in current_prices:
                mv = pos.total_volume * current_prices[ticker]
            else:
                mv = pos.total_volume * pos.average_cost

            ratio = mv / total_asset
            if ratio > max_ratio:
                max_ratio = ratio
                max_ticker = ticker

        return {
            "max_concentration": max_ratio,
            "max_concentration_ticker": max_ticker,
            "position_count": len(aggregated_positions),
        }
