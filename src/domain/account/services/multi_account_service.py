from dataclasses import dataclass

from src.domain.account.entities.account_group import AccountGroup
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.exceptions import AccountError


class CrossAccountRiskError(AccountError):
    """跨账户风控异常。"""

    def __init__(self, rule: str, detail: str) -> None:
        self.rule = rule
        self.detail = detail
        super().__init__(f"Cross-account risk violation [{rule}]: {detail}")


@dataclass(slots=True, kw_only=True)
class RiskLimits:
    """跨账户风控阈值。"""

    max_total_exposure: float = 0.0
    max_single_concentration: float = 0.30
    max_account_count: int = 10


@dataclass(slots=True, kw_only=True)
class FundAllocationRule:
    """资金调配规则。"""

    target_account_id: str
    target_ratio: float


class MultiAccountService:
    """多账户领域服务 -- 提供跨账户的业务逻辑。

    职责:
    - 跨账户持仓汇总
    - 跨账户风控检查
    - 策略间资金自动调配
    """

    def __init__(self, risk_limits: RiskLimits | None = None) -> None:
        self._risk_limits = risk_limits or RiskLimits()

    def check_global_risk(
        self,
        group: AccountGroup,
        assets: list[Asset],
        positions: list[Position],
        current_prices: dict[str, float] | None = None,
    ) -> list[str]:
        """执行跨账户全局风控检查。

        Args:
            group: 账户组。
            assets: 各子账户资产。
            positions: 各子账户持仓。
            current_prices: 当前价格映射。

        Returns:
            违规规则列表，空列表表示全部通过。
        """
        violations: list[str] = []
        limits = self._risk_limits

        # 检查账户数量
        if len(group.account_ids) > limits.max_account_count:
            violations.append(
                f"Account count {len(group.account_ids)} exceeds limit {limits.max_account_count}"
            )

        # 汇总资产
        agg_assets = group.aggregate_assets(assets)
        total_asset = agg_assets["total_asset"]

        # 检查总暴露
        if limits.max_total_exposure > 0 and total_asset > limits.max_total_exposure:
            violations.append(
                f"Total exposure {total_asset:.2f} exceeds limit {limits.max_total_exposure:.2f}"
            )

        # 汇总持仓 & 集中度
        agg_positions = group.aggregate_positions(positions)
        concentration = group.compute_concentration(agg_assets, agg_positions, current_prices)

        if concentration["max_concentration"] > limits.max_single_concentration:
            violations.append(
                f"Concentration of {concentration['max_concentration_ticker']} "
                f"{concentration['max_concentration']:.2%} exceeds limit "
                f"{limits.max_single_concentration:.2%}"
            )

        return violations

    def compute_allocation(
        self,
        group: AccountGroup,
        assets: list[Asset],
        rules: list[FundAllocationRule],
        total_transferable: float | None = None,
    ) -> dict[str, float]:
        """根据调配规则计算各账户应转入/转出金额。

        正值表示应转入，负值表示应转出。

        Args:
            group: 账户组。
            assets: 各子账户资产。
            rules: 调配规则列表（target_ratio 之和应 <= 1.0）。
            total_transferable: 可调配资金总额；为 None 时使用组内总可用资金。

        Returns:
            account_id -> 应调配金额（正转入/负转出）的字典。
        """
        asset_map = {a.account_id: a for a in assets}

        # 计算可用调配总额
        if total_transferable is None:
            total_transferable = sum(
                asset_map[aid].available_cash
                for aid in group.account_ids
                if aid in asset_map
            )

        # 计算各账户目标金额
        targets: dict[str, float] = {}
        for rule in rules:
            if rule.target_account_id in group.account_ids:
                targets[rule.target_account_id] = total_transferable * rule.target_ratio

        # 计算差额
        result: dict[str, float] = {}
        for account_id in group.account_ids:
            current = asset_map[account_id].available_cash if account_id in asset_map else 0.0
            target = targets.get(account_id, current)
            result[account_id] = target - current

        return result

    def merge_positions(
        self,
        group: AccountGroup,
        positions: list[Position],
    ) -> dict[str, Position]:
        """汇总组内持仓（委托 AccountGroup 实体）。"""
        return group.aggregate_positions(positions)
