from src.domain.portfolio.interfaces.position_sizer import IPositionSizer
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
import math


class FixedRatioSizer(IPositionSizer):
    """固定比例/风险百分比资金分配策略。

    支持两种模式:
    1. ratio 模式 (默认): 以总资产的固定比例分配每笔交易预算。
       budget = total_asset * ratio * confidence_score

    2. risk_per_trade 模式: 以总资产的风险百分比决定单笔头寸规模。
       止损幅度由 ATR 或固定百分比提供（默认 2% 价格止损）。
       volume = (total_asset * risk_pct) / (price * stop_loss_pct)
    """

    def __init__(
        self,
        ratio: float = 0.2,
        mode: str = "ratio",
        risk_pct: float = 0.01,
        stop_loss_pct: float = 0.02,
    ) -> None:
        """
        Args:
            ratio: 固定比例模式下的资金分配比例 (0.0 - 1.0)。
            mode: 仓位计算模式，"ratio" 或 "risk_per_trade"。
            risk_pct: 风险百分比模式下，单笔最大亏损占总资产比例 (默认 1%)。
            stop_loss_pct: 风险百分比模式下，止损幅度占入场价比例 (默认 2%)。
        """
        if not 0.0 < ratio <= 1.0:
            raise ValueError(f"ratio must be in (0.0, 1.0], got {ratio}")
        if mode not in ("ratio", "risk_per_trade"):
            raise ValueError(f"mode must be 'ratio' or 'risk_per_trade', got {mode}")
        if not 0.0 < risk_pct <= 0.05:
            raise ValueError(f"risk_pct must be in (0.0, 0.05], got {risk_pct}")
        if not 0.0 < stop_loss_pct <= 0.20:
            raise ValueError(f"stop_loss_pct must be in (0.0, 0.20], got {stop_loss_pct}")

        self.ratio = ratio
        self.mode = mode
        self.risk_pct = risk_pct
        self.stop_loss_pct = stop_loss_pct

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
            if self.mode == "risk_per_trade":
                target_volume = self._calc_risk_based_buy(current_price, asset, signal)
            else:
                target_volume = self._calc_ratio_based_buy(current_price, asset, signal)

        elif signal.direction == SignalDirection.SELL:
            if position and position.available_volume > 0:
                raw_volume = position.available_volume * signal.confidence_score
                if abs(signal.confidence_score - 1.0) < 1e-6:
                    target_volume = min(int(raw_volume), position.available_volume)
                else:
                    target_volume = (int(raw_volume) // 100) * 100

        return target_volume

    def _calc_ratio_based_buy(
        self, current_price: float, asset: Asset, signal: Signal
    ) -> int:
        """固定比例模式：总资产 * ratio * confidence / price。"""
        budget = asset.total_asset * self.ratio * signal.confidence_score
        budget = min(budget, asset.available_cash)
        if budget <= 0:
            return 0
        raw_volume = budget / current_price
        return (int(raw_volume) // 100) * 100

    def _calc_risk_based_buy(
        self, current_price: float, asset: Asset, signal: Signal
    ) -> int:
        """风险百分比模式：volume = (总资产 * risk_pct) / (price * stop_loss_pct)。"""
        risk_amount = asset.total_asset * self.risk_pct * signal.confidence_score
        stop_loss_amount = current_price * self.stop_loss_pct
        if stop_loss_amount <= 0:
            return 0
        raw_volume = risk_amount / stop_loss_amount
        target_volume = (int(raw_volume) // 100) * 100
        # 资金约束
        max_affordable = int(asset.available_cash / current_price) // 100 * 100
        return min(target_volume, max_affordable)
