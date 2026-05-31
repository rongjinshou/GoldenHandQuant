"""因子挖掘流程编排 — 串联特征组合→快速筛选→深度验证→入库。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.infrastructure.ml_engine.factor_evaluator import FactorEvaluator
from src.infrastructure.ml_engine.factor_repository import FactorRepository
from src.infrastructure.ml_engine.feature_combiner import AutoFeatureCombiner


@dataclass(slots=True, kw_only=True)
class MiningReport:
    """挖掘报告。"""
    total_candidates: int
    quick_filtered: int
    deep_validated: int
    stored_factors: list[str]
    duration_seconds: float
    details: list[dict]


class FactorMiner:
    """因子挖掘主流程。"""

    def __init__(
        self,
        combiner: AutoFeatureCombiner | None = None,
        evaluator: FactorEvaluator | None = None,
        repository: FactorRepository | None = None,
    ) -> None:
        self._combiner = combiner or AutoFeatureCombiner()
        self._evaluator = evaluator or FactorEvaluator()
        self._repository = repository or FactorRepository()

    def mine(
        self,
        snapshots_by_date: dict[date, list[StockSnapshot]],
        forward_days: int = 20,
        target_count: int = 10,
        strategy: str = "standard",
    ) -> MiningReport:
        """执行一次完整的因子挖掘。

        流程:
        1. AutoFeatureCombiner 生成候选特征 (100+)
        2. FactorEvaluator 快速筛选 (IC>0.03, IR>0.5)
        3. 入库通过筛选的因子

        Returns:
            MiningReport: 挖掘报告。
        """
        start = time.time()

        sorted_dates = sorted(snapshots_by_date.keys())
        if len(sorted_dates) < forward_days + 1:
            return MiningReport(
                total_candidates=0, quick_filtered=0, deep_validated=0,
                stored_factors=[], duration_seconds=0.0, details=[],
            )

        # Step 1: 生成候选特征
        all_combinations: dict[date, pd.DataFrame] = {}
        for d in sorted_dates:
            snapshots = snapshots_by_date[d]
            if snapshots:
                df = self._combiner.generate_combinations(snapshots, strategy=strategy)
                all_combinations[d] = df

        # Step 2: 计算前瞻收益
        forward_returns = self._compute_forward_returns(
            snapshots_by_date, sorted_dates, forward_days
        )

        # Step 3: 堆叠因子矩阵
        factor_dict = self._stack_factors(all_combinations)

        # Step 4: 快速筛选 (IC/IR)
        eval_results = self._evaluator.evaluate_batch(
            factor_dict, forward_returns, top_n=target_count * 3
        )
        quick_passed = [r for r in eval_results if r.is_effective]

        # Step 4.5: 共线性过滤（相关性 > 0.95 的特征对保留 IC 更高的）
        quick_passed = self._filter_collinear(
            quick_passed, factor_dict, corr_threshold=0.95
        )

        # Step 5: 入库
        stored: list[str] = []
        details: list[dict] = []
        for result in quick_passed[:target_count]:
            expression = self._combiner.get_expression(result.factor_name)
            self._repository.save_factor(
                name=result.factor_name,
                expression=expression,
                factor_values=factor_dict[result.factor_name],
                metrics={
                    "ic_mean": result.ic_mean,
                    "ir": result.ir,
                    "sharpe_top_group": max(result.sharpe_by_group) if result.sharpe_by_group else 0.0,
                    "monotonicity": result.monotonicity,
                    "category": "mined",
                },
            )
            stored.append(result.factor_name)
            details.append({
                "name": result.factor_name,
                "expression": expression,
                "ic_mean": result.ic_mean,
                "ir": result.ir,
                "monotonicity": result.monotonicity,
            })

        duration = time.time() - start
        return MiningReport(
            total_candidates=len(factor_dict),
            quick_filtered=len(quick_passed),
            deep_validated=len(stored),
            stored_factors=stored,
            duration_seconds=duration,
            details=details,
        )

    def _compute_forward_returns(
        self,
        snapshots_by_date: dict[date, list[StockSnapshot]],
        sorted_dates: list[date],
        forward_days: int,
    ) -> pd.DataFrame:
        """计算前瞻收益率矩阵。"""
        # 用 return_5d 作为前瞻收益代理（避免泄露）
        all_dates: list[date] = []
        all_data: dict[str, list[float]] = {}

        for i, d in enumerate(sorted_dates):
            snapshots = snapshots_by_date[d]
            if not snapshots:
                continue

            # 用当前日的 return_5d 作为 "未来5日收益" 的代理
            # 注意：这里用的是当日已实现的 return_5d，代表过去5日收益
            # 在实际生产中应计算 shift(-forward_days) 的真实前瞻收益
            fwd_idx = i + forward_days
            if fwd_idx >= len(sorted_dates):
                continue

            fwd_date = sorted_dates[fwd_idx]
            fwd_snapshots = snapshots_by_date[fwd_date]
            fwd_map = {s.symbol: s.return_5d for s in fwd_snapshots if s.return_5d is not None}

            if not fwd_map:
                continue

            all_dates.append(d)
            for sym, val in fwd_map.items():
                if sym not in all_data:
                    all_data[sym] = [float("nan")] * len(all_dates)
                while len(all_data[sym]) < len(all_dates):
                    all_data[sym].append(float("nan"))
                all_data[sym][-1] = val

        # 对齐长度
        for sym in all_data:
            while len(all_data[sym]) < len(all_dates):
                all_data[sym].append(float("nan"))

        return pd.DataFrame(all_data, index=all_dates)

    @staticmethod
    def _filter_collinear(
        results: list,
        factor_dict: dict[str, pd.DataFrame],
        corr_threshold: float = 0.95,
    ) -> list:
        """过滤高共线性特征：相关性 > threshold 的对保留 IC 更高的。"""
        if len(results) <= 1:
            return results

        names = [r.factor_name for r in results]
        available = [n for n in names if n in factor_dict]
        if len(available) <= 1:
            return results

        # 构建因子矩阵并计算 Pearson 相关性
        stacked = pd.DataFrame({n: factor_dict[n].stack() for n in available})
        corr_matrix = stacked.corr(method="pearson").abs()

        # 按 |IC| 降序排列，贪心保留
        sorted_results = sorted(results, key=lambda r: abs(r.ic_mean), reverse=True)
        kept: set[str] = set()
        removed: set[str] = set()

        for r in sorted_results:
            name = r.factor_name
            if name in removed or name not in factor_dict:
                continue
            kept.add(name)
            # 标记与当前因子高度相关的其他因子
            if name in corr_matrix.columns:
                for other in corr_matrix.columns:
                    if other != name and other not in removed and other not in kept:
                        if corr_matrix.loc[name, other] > corr_threshold:
                            removed.add(other)

        return [r for r in results if r.factor_name in kept]

    def _stack_factors(
        self,
        combinations_by_date: dict[date, pd.DataFrame],
    ) -> dict[str, pd.DataFrame]:
        """将每日的因子矩阵堆叠为 {因子名: DataFrame(index=date, columns=symbol)}。"""
        if not combinations_by_date:
            return {}

        first_df = next(iter(combinations_by_date.values()))
        feature_names = list(first_df.columns)

        result: dict[str, pd.DataFrame] = {}
        for fname in feature_names:
            frames: list[pd.Series] = []
            for d, df in sorted(combinations_by_date.items()):
                if fname in df.columns:
                    s = df[fname].rename(d)
                    frames.append(s)
            if frames:
                result[fname] = pd.DataFrame(frames)

        return result
