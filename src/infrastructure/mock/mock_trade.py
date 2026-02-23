from datetime import datetime
from src.domain.trade.interfaces.gateways.trade_gateway import ITradeGateway
from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_status import OrderStatus
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.domain.backtest.value_objects.trade_record import TradeRecord
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway

class MockTradeGateway(ITradeGateway, IAccountGateway):
    """基于内存的模拟交易网关 (包含账户功能)。
    
    遵循 A 股交易规则:
    1. T+1 结算。
    2. 交易成本: 佣金(万2.5, Min 5), 印花税(卖出千0.5), 过户费(十万1)。
    3. 滑点: 买入上浮 0.1%, 卖出下浮 0.1%。
    4. 成交量限制: 单笔不超过 K 线成交量的 10%。
    """

    # 费率常量
    COMMISSION_RATE = 0.00025
    MIN_COMMISSION = 5.0
    STAMP_DUTY_RATE = 0.0005  # 卖出收取
    TRANSFER_FEE_RATE = 0.00001
    
    # 滑点常量
    SLIPPAGE_BUY = 0.001
    SLIPPAGE_SELL = 0.001  # 向下浮动

    # 流动性限制
    CAPACITY_LIMIT_RATIO = 0.1

    def __init__(self, market_gateway: IMarketGateway, initial_capital: float = 1_000_000.0) -> None:
        """初始化模拟账户。

        Args:
            market_gateway: 行情网关，用于获取当前价格和成交量。
            initial_capital: 初始资金。
        """
        self.market_gateway = market_gateway
        self.asset = Asset(
            account_id="MOCK_ACCOUNT",
            total_asset=initial_capital,
            available_cash=initial_capital,
            frozen_cash=0.0
        )
        self.positions: dict[str, Position] = {}  # key: ticker
        self.trade_records: list[TradeRecord] = []
        self.orders: dict[str, Order] = {}

    def get_asset(self) -> Asset | None:
        """获取账户资金。"""
        # 返回当前资金状态对象
        return self.asset

    def get_positions(self) -> list[Position]:
        """获取所有持仓。"""
        return list(self.positions.values())

    def get_position(self, ticker: str) -> Position | None:
        """获取单个持仓。"""
        return self.positions.get(ticker)

    def place_order(self, order: Order) -> str:
        """模拟下单并根据规则撮合。

        Args:
            order: 订单实体。

        Returns:
            str: 订单 ID。

        Raises:
            OrderSubmitError: 如果提交失败 (如资金不足、无行情等)。
        """
        # 1. 基础验证
        if order.volume <= 0:
            raise OrderSubmitError("Volume must be positive")
        
        # 2. 获取当前行情
        bars = self.market_gateway.get_recent_bars(order.ticker, "1d", 1)
        if not bars:
            raise OrderSubmitError(f"No market data for {order.ticker}")
        bar = bars[0]
        
        # 3. 计算成交价格 (含滑点)
        ref_price = bar.close
        if order.direction == OrderDirection.BUY:
            exec_price = ref_price * (1 + self.SLIPPAGE_BUY)
        else:
            exec_price = ref_price * (1 - self.SLIPPAGE_SELL)
            
        # 4. 计算成交数量 (流动性限制)
        max_vol = int(bar.volume * self.CAPACITY_LIMIT_RATIO)
        # 向下取整到 100 整数倍 (假设 order.volume 已经是 100 倍数，这里再次确保)
        max_vol = (max_vol // 100) * 100
        
        fill_volume = min(order.volume, max_vol)
        if fill_volume < 100:
            # 如果流动性不足以成交一手，则拒绝或全撤 (这里选择废单)
            order.status = OrderStatus.REJECTED
            raise OrderSubmitError(f"Insufficient liquidity: max volume {max_vol} < 100")

        # 5. 预估成本与资金/持仓检查
        total_cost, commission, tax, transfer_fee = self._calculate_costs(exec_price, fill_volume, order.direction)
        
        if order.direction == OrderDirection.BUY:
            # 买入: 需有足够资金支付 (成交金额 + 所有费用)
            # 注意: 这里的 cost 是正数，表示总支出
            if self.asset.available_cash < total_cost:
                order.status = OrderStatus.REJECTED
                raise OrderSubmitError(f"Insufficient funds: need {total_cost:.2f}, have {self.asset.available_cash:.2f}")
        
        elif order.direction == OrderDirection.SELL:
            # 卖出: 需有足够可用持仓
            position = self.positions.get(order.ticker)
            if not position or position.available_volume < fill_volume:
                order.status = OrderStatus.REJECTED
                raise OrderSubmitError(f"Insufficient position: need {fill_volume}, have {position.available_volume if position else 0}")

        # 6. 提交成功，开始撮合
        order.submit()
        self.orders[order.order_id] = order
        
        # 7. 冻结资金 (严格遵循: SUBMITTED -> Freeze)
        # 买入冻结预估金额，卖出不冻结资金
        frozen_amount = 0.0
        if order.direction == OrderDirection.BUY:
            frozen_amount = total_cost
            self.asset.freeze_cash(frozen_amount)
            
        # 8. 执行成交 (Atomic fill for backtest)
        try:
            self._simulate_fill(order, exec_price, fill_volume, commission, tax, transfer_fee, frozen_amount)
        except Exception as e:
            # 回滚冻结 (理论上不应发生，但为了健壮性)
            if frozen_amount > 0:
                self.asset.deduct_frozen_cash(frozen_amount) # 错误回滚需特殊处理，这里简单解冻
                self.asset.available_cash += frozen_amount
            raise e
            
        return order.order_id

    def _calculate_costs(self, price: float, volume: int, direction: OrderDirection) -> tuple[float, float, float, float]:
        """计算交易成本。
        
        Returns:
            (total_impact, commission, tax, transfer_fee)
            total_impact: 
                - Buy: amount + fees (positive, amount to deduct)
                - Sell: amount - fees (positive, amount to add) -- Wait, let's keep it consistent.
                Let's return (cash_change_amount, ...)
                - Buy: cost (>0)
                - Sell: income (>0)
        """
        amount = price * volume
        commission = max(amount * self.COMMISSION_RATE, self.MIN_COMMISSION)
        transfer_fee = amount * self.TRANSFER_FEE_RATE
        tax = amount * self.STAMP_DUTY_RATE if direction == OrderDirection.SELL else 0.0
        
        total_fees = commission + transfer_fee + tax
        
        if direction == OrderDirection.BUY:
            return amount + total_fees, commission, tax, transfer_fee
        else:
            return amount - total_fees, commission, tax, transfer_fee

    def _simulate_fill(self, order: Order, price: float, volume: int, 
                      commission: float, tax: float, transfer_fee: float, 
                      frozen_amount: float) -> None:
        """执行成交并更新状态。"""
        
        # 1. 资金结算
        if order.direction == OrderDirection.BUY:
            # 解冻
            self.asset.deduct_frozen_cash(frozen_amount)
            # 扣除实际成本 (在 _calculate_costs 中已包含本金+费用)
            actual_cost = price * volume + commission + tax + transfer_fee
            
            # 这里有个细节: frozen_amount 等于 actual_cost (因为我们是用 exec_price 估算的)
            # 如果是限价单，冻结可能按限价算，成交按市价算，会有差额。
            # 但这里简化为直接扣除 actual_cost
            self.asset.available_cash -= (actual_cost - frozen_amount) # 修正差额 (此处为0)
            self.asset.total_asset -= (commission + tax + transfer_fee) # 资产减少费用
            
        elif order.direction == OrderDirection.SELL:
            income = price * volume - commission - tax - transfer_fee
            self.asset.available_cash += income
            self.asset.total_asset -= (commission + tax + transfer_fee)

        # 2. 持仓更新
        position = self.positions.get(order.ticker)
        if not position:
            position = Position(account_id=self.asset.account_id, ticker=order.ticker)
            self.positions[order.ticker] = position

        realized_pnl = 0.0
        if order.direction == OrderDirection.BUY:
            position.on_buy_filled(volume, price)
        elif order.direction == OrderDirection.SELL:
            # 计算平仓盈亏 (仅价差，不含费? 或者含费? 通常 Realized PnL 含费)
            # 成本价
            cost = position.average_cost
            # 卖出收入 (净额) - 成本价值
            # realized_pnl = income - (cost * volume)
            # income = price * volume - fees
            # so pnl = (price - cost) * volume - fees
            fees = commission + tax + transfer_fee
            realized_pnl = (price - cost) * volume - fees
            
            position.on_sell_filled(volume, price)

        # 清理空持仓
        if position.total_volume == 0:
            del self.positions[order.ticker]

        # 3. 订单状态更新
        # 调用 Order 实体的更新方法
        order.on_fill(volume, price)

        # 如果是部分成交且剩余撤销
        if volume < order.volume:
             # 手动修正状态为 PARTIAL_CANCELED (如果 on_fill 没处理的话)
             # Order.on_fill 通常会将状态设为 PARTIAL_FILLED 或 FILLED
             if order.status == OrderStatus.PARTIAL_FILLED:
                 order.status = OrderStatus.PARTIAL_CANCELED

        # 4. 记录交易
        record = TradeRecord(
            symbol=order.ticker,
            direction=order.direction,
            execute_at=order.created_at,
            price=price,
            volume=volume,
            commission=commission + tax + transfer_fee, # 汇总费用
            realized_pnl=realized_pnl,
            remark=f"Slippage: {self.SLIPPAGE_BUY if order.direction==OrderDirection.BUY else self.SLIPPAGE_SELL:.1%}"
        )
        self.trade_records.append(record)

    def cancel_all_open_orders(self) -> None:
        """撤销所有未成交订单 (用于收盘清算)。"""
        for order in self.orders.values():
            if order.status in [OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILLED]:
                 # 模拟回测中通常是立即成交，但在 limit 单或部分成交场景下会有残留
                 # 这里主要是配合架构规范 4.4
                 order.status = OrderStatus.CANCELED
                 # 如果有冻结资金需解冻 (本实现中买入立即成交或拒绝，不存在挂单，但为了接口完整性)
                 pass 

    def daily_settlement(self) -> None:
        """日终结算: T+1 持仓可用化。"""
        self.cancel_all_open_orders()
        for pos in self.positions.values():
            pos.settle_t_plus_1()
