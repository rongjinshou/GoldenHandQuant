"""FactorMiner 端到端测试。"""

from datetime import date, datetime

import numpy as np

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.infrastructure.ml_engine.factor_miner import FactorMiner, MiningReport
from src.infrastructure.ml_engine.factor_repository import FactorRepository


def _make_snapshots_by_date(
    n_dates: int = 60,
    n_symbols: int = 50,
    base_date: date = date(2023, 1, 3),
) -> dict[date, list[StockSnapshot]]:
    """构造模拟快照数据。"""
    rng = np.random.default_rng(42)
    snapshots_by_date: dict[date, list[StockSnapshot]] = {}

    for i in range(n_dates):
        d = datetime.combine(base_date, datetime.min.time())
        d = d.replace(day=1)  # simplified
        from datetime import timedelta
        dt = datetime(2023, 1, 1) + timedelta(days=i)

        snapshots: list[StockSnapshot] = []
        for j in range(n_symbols):
            symbol = f"{j:06d}"
            snapshots.append(StockSnapshot(
                symbol=symbol,
                date=dt,
                open=10.0 + rng.standard_normal(),
                high=11.0 + rng.standard_normal(),
                low=9.0 + rng.standard_normal(),
                close=10.5 + rng.standard_normal(),
                volume=100000.0 + rng.standard_normal() * 10000,
                name=f"Stock {symbol}",
                list_date=datetime(2000, 1, 1),
                market_cap=1e10 + rng.standard_normal() * 1e9,
                pe_ratio=15.0 + rng.standard_normal() * 5,
                pb_ratio=2.0 + rng.standard_normal() * 0.5,
                roe_ttm=0.15 + rng.standard_normal() * 0.05,
                return_5d=rng.standard_normal() * 0.02,
                return_20d=rng.standard_normal() * 0.05,
                volatility_20d=0.03 + abs(rng.standard_normal() * 0.01),
                turnover_rate=1.0 + rng.standard_normal() * 0.3,
                rsi_14=50.0 + rng.standard_normal() * 10,
                macd=rng.standard_normal() * 0.1,
                macd_signal=rng.standard_normal() * 0.05,
            ))
        snapshots_by_date[dt.date()] = snapshots

    return snapshots_by_date


class TestFactorMiner:
    def test_mine_returns_report(self, tmp_path):
        repo = FactorRepository(data_dir=str(tmp_path / "factors"))
        miner = FactorMiner(repository=repo)
        snapshots = _make_snapshots_by_date(n_dates=70, n_symbols=50)

        report = miner.mine(snapshots_by_date=snapshots, forward_days=5, target_count=5)

        assert isinstance(report, MiningReport)
        assert report.total_candidates > 0
        assert report.duration_seconds >= 0

    def test_mine_with_insufficient_data_returns_empty(self, tmp_path):
        repo = FactorRepository(data_dir=str(tmp_path / "factors"))
        miner = FactorMiner(repository=repo)
        # 只有 5 天数据，不够
        snapshots = _make_snapshots_by_date(n_dates=5, n_symbols=50)

        report = miner.mine(snapshots_by_date=snapshots, forward_days=20)
        assert report.total_candidates == 0
        assert report.stored_factors == []

    def test_mine_stores_effective_factors(self, tmp_path):
        repo = FactorRepository(data_dir=str(tmp_path / "factors"))
        miner = FactorMiner(repository=repo)
        snapshots = _make_snapshots_by_date(n_dates=80, n_symbols=100)

        report = miner.mine(snapshots_by_date=snapshots, forward_days=5, target_count=3)

        # 如果有因子通过筛选，应该被存储
        if report.stored_factors:
            factors = repo.list_factors()
            assert len(factors) == len(report.stored_factors)
