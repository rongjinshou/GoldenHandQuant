"""因子中性化(正交化)测试。"""

from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.infrastructure.factor_test.neutralizer import FactorNeutralizer


def _snap(symbol: str, market_cap: float, return_20d: float) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name=symbol, list_date=datetime(2020, 1, 1),
        market_cap=market_cap, return_20d=return_20d,
    )


class TestFactorNeutralizer:
    def test_size_clone_has_zero_neutralized_ic(self):
        """因子 = log(market_cap) 本身 → 对市值中性化后残差为0 → 中性化IC≈0。

        即使它对收益"看似有效"(raw IC 高), 中性化后应暴露它只是市值的影子。
        """
        neu = FactorNeutralizer()
        snaps = [_snap(f"S{i}", market_cap=float(10 ** (i + 8)), return_20d=0.01 * i)
                 for i in range(6)]
        snapshots_by_date = {"2024-01-01": snaps, "2024-01-02": snaps}
        # 下期收益与市值正相关 (模拟"看似有效")
        returns_by_date = {"2024-01-02": {f"S{i}": 0.01 * i for i in range(6)}}

        nic = neu.mean_neutralized_ic("log(market_cap)", snapshots_by_date, returns_by_date)
        assert abs(nic) < 1e-6

    def test_independent_factor_retains_ic(self):
        """与市值/反转无关、却真预测收益的因子 → 中性化后仍保留 IC。"""
        neu = FactorNeutralizer()
        # market_cap 全相同(无 size 信号), return_20d 全相同(无 reversal 信号)
        # 用 pe_ratio 作因子, 与下期收益完全正相关
        snaps = []
        for i in range(6):
            s = _snap(f"S{i}", market_cap=1e10, return_20d=0.0)
            s.pe_ratio = float(i)
            snaps.append(s)
        snapshots_by_date = {"2024-01-01": snaps, "2024-01-02": snaps}
        returns_by_date = {"2024-01-02": {f"S{i}": 0.01 * i for i in range(6)}}

        nic = neu.mean_neutralized_ic("pe_ratio", snapshots_by_date, returns_by_date)
        assert nic > 0.8
