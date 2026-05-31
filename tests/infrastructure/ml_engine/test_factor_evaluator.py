"""FactorEvaluator 单元测试。"""

import numpy as np
import pandas as pd

from src.infrastructure.ml_engine.factor_evaluator import FactorEvaluator, FactorEvalResult


def _make_factor_and_returns(
    n_dates: int = 100,
    n_symbols: int = 50,
    correlation: float = 0.1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """构造具有指定相关性的因子值和前瞻收益。"""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2023-01-01", periods=n_dates, freq="B")
    symbols = [f"{i:06d}" for i in range(n_symbols)]

    # 因子值
    factor_data = rng.standard_normal((n_dates, n_symbols))
    factor = pd.DataFrame(factor_data, index=dates, columns=symbols)

    # 前瞻收益 = correlation * factor + noise
    noise = rng.standard_normal((n_dates, n_symbols))
    returns_data = correlation * factor_data + (1 - correlation**2) ** 0.5 * noise
    returns = pd.DataFrame(returns_data, index=dates, columns=symbols)

    return factor, returns


class TestFactorEvaluator:
    def test_compute_ic_series_returns_series(self):
        evaluator = FactorEvaluator()
        factor, returns = _make_factor_and_returns()
        ic_series = evaluator.compute_ic_series(factor, returns)
        assert isinstance(ic_series, pd.Series)
        assert len(ic_series) > 0

    def test_ic_positive_for_correlated_data(self):
        evaluator = FactorEvaluator()
        factor, returns = _make_factor_and_returns(correlation=0.3)
        ic_series = evaluator.compute_ic_series(factor, returns)
        assert ic_series.mean() > 0.01

    def test_ic_near_zero_for_uncorrelated_data(self):
        evaluator = FactorEvaluator()
        factor, returns = _make_factor_and_returns(correlation=0.0)
        ic_series = evaluator.compute_ic_series(factor, returns)
        assert abs(ic_series.mean()) < 0.05

    def test_evaluate_single_returns_result(self):
        evaluator = FactorEvaluator()
        factor, returns = _make_factor_and_returns(correlation=0.2)
        result = evaluator.evaluate_single(factor, returns, factor_name="test")
        assert isinstance(result, FactorEvalResult)
        assert result.factor_name == "test"
        assert isinstance(result.ic_mean, float)
        assert isinstance(result.ir, float)
        assert isinstance(result.monotonicity, float)
        assert len(result.sharpe_by_group) == 5
        assert len(result.annual_return_by_group) == 5

    def test_evaluate_batch_returns_sorted(self):
        evaluator = FactorEvaluator()
        _, returns = _make_factor_and_returns()

        factor_dict = {}
        for corr in [0.1, 0.3, 0.05]:
            f, _ = _make_factor_and_returns(correlation=corr)
            factor_dict[f"factor_{corr}"] = f

        results = evaluator.evaluate_batch(factor_dict, returns, top_n=3)
        assert len(results) <= 3
        # 按 |IR| 降序
        for i in range(len(results) - 1):
            assert abs(results[i].ir) >= abs(results[i + 1].ir)

    def test_empty_factor_returns_ineffective(self):
        evaluator = FactorEvaluator()
        empty_factor = pd.DataFrame()
        returns = pd.DataFrame({"A": [1.0]})
        result = evaluator.evaluate_single(empty_factor, returns)
        assert not result.is_effective
        assert result.ic_mean == 0.0

    def test_few_symbols_skips_dates(self):
        evaluator = FactorEvaluator()
        # 只有 5 只股票，低于 30 的阈值
        factor, returns = _make_factor_and_returns(n_symbols=5)
        ic_series = evaluator.compute_ic_series(factor, returns)
        assert len(ic_series) == 0  # 被跳过

    def test_monotonicity_perfect(self):
        evaluator = FactorEvaluator()
        # 构造完美单调数据
        group_returns = pd.DataFrame({
            "group_0": [-0.01] * 20,
            "group_1": [0.0] * 20,
            "group_2": [0.01] * 20,
            "group_3": [0.02] * 20,
            "group_4": [0.03] * 20,
        })
        mono = evaluator._compute_monotonicity(group_returns)
        assert mono == 1.0

    def test_monotonicity_non_monotone(self):
        evaluator = FactorEvaluator()
        group_returns = pd.DataFrame({
            "group_0": [0.03] * 20,
            "group_1": [0.01] * 20,
            "group_2": [0.05] * 20,
            "group_3": [0.00] * 20,
            "group_4": [0.04] * 20,
        })
        mono = evaluator._compute_monotonicity(group_returns)
        assert mono < 0.5

    def test_sharpe_by_group(self):
        evaluator = FactorEvaluator()
        # 使用有波动的收益序列（常数序列 std=0 导致 sharpe=0）
        rng = np.random.default_rng(42)
        group_returns = pd.DataFrame({
            "group_0": rng.normal(0.0005, 0.01, 252),
            "group_4": rng.normal(0.002, 0.01, 252),
        })
        sharpes = evaluator._compute_sharpe_by_group(group_returns)
        assert len(sharpes) == 2
        assert sharpes[1] > sharpes[0]  # group_4 均值更高

    def test_effective_threshold(self):
        evaluator = FactorEvaluator()
        assert evaluator._check_effective(0.05, 0.6, 0.6)
        assert not evaluator._check_effective(0.01, 0.6, 0.6)  # IC too low
        assert not evaluator._check_effective(0.05, 0.3, 0.6)  # IR too low
        assert not evaluator._check_effective(0.05, 0.6, 0.4)  # positive ratio too low
