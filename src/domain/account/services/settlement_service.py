from dataclasses import dataclass

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_status import OrderStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class SettlementConfig:
    """结算费率配置（不可变值对象）。"""
    commission_rate: float = 0.00025       # 佣金费率 (万2.5)
    min_commission: float = 5.0            # 最低佣金 (元)
    transfer_fee_rate: float = 0.00001     # 过户费费率 (十万分之一)


class DailySettlementService:
    """日终结算服务。

    负责处理每日收盘后的账户结算逻辑:
    1. 撤销未成交订单并释放冻结资金。
    2. 执行 T+1 持仓结算 (将冻结持仓转为可用)。
    """

    def __init__(self, config: SettlementConfig | None = None) -> None:
        self._config = config or SettlementConfig()

    # 印花税仅卖出收取，不涉及买入冻结资金的计算
    # 但如果是卖出单被撤销，通常不涉及资金解冻(除非卖出也冻结了资金? A股通常卖出只冻结持仓)
    # 根据 MockTradeGateway 的实现，卖出不冻结资金。

    def process_daily_settlement(
        self,
        orders: list[Order],
        positions: list[Position],
        asset: Asset
    ) -> None:
        """执行日终结算。

        Args:
            orders: 当前所有订单列表。
            positions: 当前所有持仓列表。
            asset: 账户资产实体。
        """
        # 1. 撤销未成交订单并释放冻结资金
        for order in orders:
            if order.status in [OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILLED]:
                self._cancel_and_unfreeze(order, asset)

        # 2. T+1 持仓结算
        for position in positions:
            position.settle_t_plus_1()

    def _cancel_and_unfreeze(self, order: Order, asset: Asset) -> None:
        """撤销订单并解冻资金。"""
        # 计算剩余未成交量
        remaining_volume = order.volume - order.traded_volume

        if remaining_volume <= 0:
            return

        # 仅买入单涉及资金冻结
        if order.direction == OrderDirection.BUY:
            # 计算需要解冻的金额
            # 预估金额 = 剩余数量 * 委托价
            amount = remaining_volume * order.price

            # 预估费用
            cfg = self._config
            commission = max(amount * cfg.commission_rate, cfg.min_commission)
            transfer_fee = amount * cfg.transfer_fee_rate

            # 总冻结金额
            frozen_amount = amount + commission + transfer_fee

            # 尝试解冻 (需确保不超过当前冻结总额)
            to_unfreeze = min(frozen_amount, asset.frozen_cash)

            if to_unfreeze > 0:
                asset.unfreeze_cash(to_unfreeze)

        # 更新订单状态
        order.cancel()
