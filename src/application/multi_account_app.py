from dataclasses import dataclass, field

from src.domain.account.entities.account_group import AccountGroup
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.interfaces.account_group_repository import AccountGroupRepository
from src.domain.account.interfaces.account_repository import AccountRepository
from src.domain.account.services.multi_account_service import (
    FundAllocationRule,
    MultiAccountService,
    RiskLimits,
)


@dataclass(slots=True, kw_only=True)
class GlobalSnapshot:
    """全局监控快照。"""

    group_id: str
    group_name: str
    total_asset: float
    available_cash: float
    frozen_cash: float
    position_count: int
    max_concentration: float
    max_concentration_ticker: str
    violations: list[str] = field(default_factory=list)
    account_details: dict[str, dict[str, float]] = field(default_factory=dict)


class MultiAccountAppService:
    """多账户应用服务 -- 编排多账户交易与监控。

    职责:
    - 管理账户组的创建与维护
    - 编排多账户交易循环（全局视角）
    - 生成全局监控快照

    向后兼容: 当只使用单账户时，行为与普通单账户流程一致。
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        group_repo: AccountGroupRepository,
        risk_limits: RiskLimits | None = None,
    ) -> None:
        self._account_repo = account_repo
        self._group_repo = group_repo
        self._multi_service = MultiAccountService(risk_limits=risk_limits)

    def create_group(self, group_id: str, group_name: str, account_ids: list[str]) -> AccountGroup:
        """创建账户组。

        Args:
            group_id: 组 ID。
            group_name: 组名称。
            account_ids: 子账户 ID 列表。

        Returns:
            创建的 AccountGroup。

        Raises:
            ValueError: 如果组 ID 已存在或子账户不存在。
        """
        if self._group_repo.get(group_id) is not None:
            raise ValueError(f"Account group '{group_id}' already exists")

        for account_id in account_ids:
            if self._account_repo.get_asset(account_id) is None:
                raise ValueError(f"Account '{account_id}' does not exist")

        group = AccountGroup(group_id=group_id, group_name=group_name, account_ids=account_ids)
        self._group_repo.save(group)
        return group

    def add_account_to_group(self, group_id: str, account_id: str) -> None:
        """向组中添加账户。"""
        group = self._group_repo.get(group_id)
        if group is None:
            raise ValueError(f"Account group '{group_id}' not found")
        if self._account_repo.get_asset(account_id) is None:
            raise ValueError(f"Account '{account_id}' does not exist")
        group.add_account(account_id)
        self._group_repo.save(group)

    def remove_account_from_group(self, group_id: str, account_id: str) -> None:
        """从组中移除账户。"""
        group = self._group_repo.get(group_id)
        if group is None:
            raise ValueError(f"Account group '{group_id}' not found")
        group.remove_account(account_id)
        self._group_repo.save(group)

    def get_global_snapshot(self, group_id: str, current_prices: dict[str, float] | None = None) -> GlobalSnapshot:
        """生成全局监控快照。

        Args:
            group_id: 账户组 ID。
            current_prices: 当前价格映射。

        Returns:
            GlobalSnapshot 对象。
        """
        group = self._group_repo.get(group_id)
        if group is None:
            raise ValueError(f"Account group '{group_id}' not found")

        # 收集各账户数据
        assets = self._collect_assets(group)
        positions = self._collect_positions(group)

        # 汇总
        agg_assets = group.aggregate_assets(assets)
        agg_positions = group.aggregate_positions(positions)
        concentration = group.compute_concentration(agg_assets, agg_positions, current_prices)

        # 风控检查
        violations = self._multi_service.check_global_risk(
            group, assets, positions, current_prices
        )

        # 各账户明细
        account_details: dict[str, dict[str, float]] = {}
        for asset in assets:
            if asset.account_id in group.account_ids:
                account_details[asset.account_id] = {
                    "total_asset": asset.total_asset,
                    "available_cash": asset.available_cash,
                    "frozen_cash": asset.frozen_cash,
                }

        return GlobalSnapshot(
            group_id=group.group_id,
            group_name=group.group_name,
            total_asset=agg_assets["total_asset"],
            available_cash=agg_assets["available_cash"],
            frozen_cash=agg_assets["frozen_cash"],
            position_count=concentration["position_count"],
            max_concentration=concentration["max_concentration"],
            max_concentration_ticker=concentration["max_concentration_ticker"],
            violations=violations,
            account_details=account_details,
        )

    def compute_fund_allocation(
        self,
        group_id: str,
        rules: list[FundAllocationRule],
        total_transferable: float | None = None,
    ) -> dict[str, float]:
        """计算资金调配方案。

        Args:
            group_id: 账户组 ID。
            rules: 调配规则。
            total_transferable: 可调配总额。

        Returns:
            account_id -> 应调配金额。
        """
        group = self._group_repo.get(group_id)
        if group is None:
            raise ValueError(f"Account group '{group_id}' not found")

        assets = self._collect_assets(group)
        return self._multi_service.compute_allocation(group, assets, rules, total_transferable)

    def run_global_risk_check(
        self,
        group_id: str,
        current_prices: dict[str, float] | None = None,
    ) -> list[str]:
        """对指定账户组执行全局风控检查。

        Returns:
            违规列表，空表示通过。
        """
        group = self._group_repo.get(group_id)
        if group is None:
            raise ValueError(f"Account group '{group_id}' not found")

        assets = self._collect_assets(group)
        positions = self._collect_positions(group)

        return self._multi_service.check_global_risk(group, assets, positions, current_prices)

    def _collect_assets(self, group: AccountGroup) -> list[Asset]:
        """收集组内所有账户资产。"""
        assets: list[Asset] = []
        for account_id in group.account_ids:
            asset = self._account_repo.get_asset(account_id)
            if asset is not None:
                assets.append(asset)
        return assets

    def _collect_positions(self, group: AccountGroup) -> list[Position]:
        """收集组内所有账户持仓。"""
        positions: list[Position] = []
        for account_id in group.account_ids:
            positions.extend(self._account_repo.get_positions(account_id))
        return positions
