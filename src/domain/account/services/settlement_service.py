from dataclasses import dataclass
from src.domain.trade.entities.order import Order
from src.domain.account.entities.position import Position
from src.domain.account.entities.asset import Asset
from src.domain.trade.value_objects.order_status import OrderStatus
from src.domain.trade.value_objects.order_direction import OrderDirection

class DailySettlementService:
    """日终结算服务。
    
    负责处理每日收盘后的账户结算逻辑:
    1. 撤销未成交订单并释放冻结资金。
    2. 执行 T+1 持仓结算 (将冻结持仓转为可用)。
    """

    # 费率常量 (用于计算释放冻结资金)
    COMMISSION_RATE = 0.00025
    MIN_COMMISSION = 5.0
    TRANSFER_FEE_RATE = 0.00001
    
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
            commission = max(amount * self.COMMISSION_RATE, self.MIN_COMMISSION)
            transfer_fee = amount * self.TRANSFER_FEE_RATE
            
            # 总冻结金额
            frozen_amount = amount + commission + transfer_fee
            
            # 尝试解冻 (需确保不超过当前冻结总额)
            to_unfreeze = min(frozen_amount, asset.frozen_cash)
            
            if to_unfreeze > 0:
                asset.unfreeze_cash(to_unfreeze)

        # 更新订单状态
        order.cancel()
