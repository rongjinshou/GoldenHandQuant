from src.domain.portfolio.interfaces.position_sizer import IPositionSizer
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
import math

class FixedRatioSizer(IPositionSizer):
    """固定比例资金分配策略。"""
    
    def __init__(self, ratio: float = 0.2) -> None:
        self.ratio = ratio

    def calculate_target(
        self, 
        signal: Signal, 
        current_price: float, 
        asset: Asset, 
        position: Position | None
    ) -> int:
        if current_price <= 0:
            return 0
            
        target_volume = 0
        
        if signal.direction == SignalDirection.BUY:
            # 买入逻辑：基于总资产、设定比例和信号置信度计算目标预算
            budget = asset.total_asset * self.ratio * signal.confidence_score
            
            # 且不能超过 asset.available_cash
            budget = min(budget, asset.available_cash)
            
            if budget <= 0:
                return 0

            raw_volume = budget / current_price
            target_volume = (int(raw_volume) // 100) * 100
            
        elif signal.direction == SignalDirection.SELL:
            # 卖出逻辑：如果存在 position 且可用数量 > 0
            if position and position.available_volume > 0:
                raw_volume = position.available_volume * signal.confidence_score
                
                # 如果是全卖 (confidence_score close to 1.0) 则不用整手限制
                if abs(signal.confidence_score - 1.0) < 1e-6:
                     target_volume = int(raw_volume) # Should be equal to available_volume if calculation is precise
                     # Ensure we don't exceed available
                     target_volume = min(target_volume, position.available_volume)
                else:
                     target_volume = (int(raw_volume) // 100) * 100
        
        return target_volume
