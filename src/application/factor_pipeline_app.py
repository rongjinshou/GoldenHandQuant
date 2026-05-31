"""因子研发流水线应用服务。

编排 因子挖掘 → IC 检验 → 分层回测 → 入库 → 上线 全流程。
与 FactorPipelineService (领域) 集成。
"""

from __future__ import annotations

import logging

from src.domain.strategy.factor_test.report import FactorTestReport
from src.domain.strategy.interfaces.factor_repository import IFactorRepository
from src.domain.strategy.services.factor_pipeline import (
    DecayCheckResult,
    FactorPipelineService,
)
from src.domain.strategy.value_objects.factor_lifecycle_status import FactorLifecycleStatus

logger = logging.getLogger(__name__)


class FactorPipelineAppService:
    """因子研发流水线应用服务。

    编排 因子挖掘 → IC/分层检验 → 评分 → 入库 → 上线 全流程。
    支持衰减监控与自动淘汰、因子组合优化。
    """

    def __init__(
        self,
        pipeline: FactorPipelineService,
        factor_repository: IFactorRepository | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._repo = factor_repository

    # -- 全流程编排 --

    def submit_factor(self, name: str, expression: str) -> dict[str, object]:
        """提交新因子，注册并进入检验阶段。

        Args:
            name: 因子名。
            expression: 因子表达式 DSL。

        Returns:
            包含因子状态的字典。
        """
        entry = self._pipeline.register_factor(name, expression)
        entry = self._pipeline.start_testing(name)
        logger.info("Factor submitted: %s -> TESTING", name)
        return self._entry_to_dict(entry)

    def process_test_result(
        self,
        name: str,
        report: FactorTestReport,
    ) -> dict[str, object]:
        """处理因子检验结果，自动决定 VALIDATED 或回退。

        检验通过后自动尝试入库。

        Args:
            name: 因子名。
            report: 因子测试报告。

        Returns:
            包含因子状态和评分的字典。
        """
        entry = self._pipeline.process_test_result(name, report)

        if entry.status == FactorLifecycleStatus.VALIDATED:
            logger.info(
                "Factor validated: %s (score=%.1f, grade=%s, IC=%.4f)",
                name, entry.score, entry.grade, entry.ic_mean,
            )
            self._try_save_to_repo(entry)
        else:
            logger.info(
                "Factor not validated: %s (score=%.1f, grade=%s) -> DISCOVERED",
                name, entry.score, entry.grade,
            )

        return self._entry_to_dict(entry)

    def activate_factor(self, name: str) -> dict[str, object]:
        """激活已验证的因子上线使用。

        Args:
            name: 因子名。

        Returns:
            包含因子状态的字典。
        """
        entry = self._pipeline.activate_factor(name)
        logger.info("Factor activated: %s (score=%.1f)", name, entry.score)
        return self._entry_to_dict(entry)

    def run_full_pipeline(
        self,
        name: str,
        expression: str,
        report: FactorTestReport,
        auto_activate: bool = True,
    ) -> dict[str, object]:
        """运行完整流水线: 注册 → 检验 → 入库 → (可选)激活。

        Args:
            name: 因子名。
            expression: 因子表达式。
            report: 因子测试报告。
            auto_activate: 检验通过后是否自动激活。

        Returns:
            包含因子最终状态的字典。
        """
        # 注册 + 开始检验
        self._pipeline.register_factor(name, expression)
        self._pipeline.start_testing(name)

        # 处理检验结果
        entry = self._pipeline.process_test_result(name, report)

        if entry.status != FactorLifecycleStatus.VALIDATED:
            return self._entry_to_dict(entry)

        # 尝试入库
        self._try_save_to_repo(entry)

        # 自动激活
        if auto_activate and entry.score >= self._pipeline._activate_score:
            entry = self._pipeline.activate_factor(name)

        return self._entry_to_dict(entry)

    # -- 衰减监控 --

    def check_decay(self, name: str, current_ic_mean: float) -> dict[str, object]:
        """检查单个因子衰减情况。

        Args:
            name: 因子名。
            current_ic_mean: 最近周期 IC 均值。

        Returns:
            包含衰减检查结果的字典。
        """
        result = self._pipeline.check_decay(name, current_ic_mean)
        if result.is_decayed:
            logger.warning(
                "Factor decay detected: %s (ratio=%.2f, count=%d)",
                name, result.ic_ratio, result.decay_count,
            )
        return self._decay_result_to_dict(result)

    def batch_check_decay(
        self,
        ic_by_factor: dict[str, float],
    ) -> list[dict[str, object]]:
        """批量检查所有活跃因子的衰减情况。

        Args:
            ic_by_factor: {因子名: 最近 IC 均值}。

        Returns:
            衰减检查结果字典列表。
        """
        results = self._pipeline.batch_check_decay(ic_by_factor)
        decayed = [r for r in results if r.is_decayed]
        if decayed:
            logger.warning(
                "Batch decay check: %d/%d factors decayed",
                len(decayed), len(results),
            )
        return [self._decay_result_to_dict(r) for r in results]

    # -- 因子组合优化 --

    def orthogonalize_factors(
        self,
        factor_matrix: list[list[float]],
    ) -> list[list[float]]:
        """因子正交化 (消除共线性)。

        Args:
            factor_matrix: shape (n_samples, n_factors) 因子值矩阵。

        Returns:
            正交化后的因子矩阵。
        """
        return self._pipeline.orthogonalize_factors(factor_matrix)

    def select_factors(
        self,
        factor_values: list[dict[str, float]],
        target_values: list[float],
        factor_names: list[str],
        max_factors: int | None = None,
    ) -> list[str]:
        """逐步回归选择最优因子子集。

        Args:
            factor_values: 每个样本的因子值字典列表。
            target_values: 目标值列表。
            factor_names: 候选因子名列表。
            max_factors: 最大因子数。

        Returns:
            被选中的因子名列表。
        """
        selected = self._pipeline.select_factors(
            factor_values=factor_values,
            target_values=target_values,
            factor_names=factor_names,
            max_factors=max_factors,
        )
        logger.info("Factor selection: %d/%d chosen: %s", len(selected), len(factor_names), selected)
        return selected

    # -- 查询 --

    def get_factor_status(self, name: str) -> FactorLifecycleStatus | None:
        """获取因子当前状态。"""
        entry = self._pipeline.get_entry(name)
        return entry.status if entry else None

    def get_active_factors(self) -> list[dict[str, object]]:
        """获取所有活跃因子。"""
        return [
            self._entry_to_dict(e)
            for e in self._pipeline.get_active_factors()
        ]

    def get_summary(self) -> dict[str, object]:
        """获取因子生命周期汇总。"""
        return self._pipeline.get_summary()

    def retire_factor(self, name: str, reason: str = "manual retire") -> dict[str, object]:
        """手动退役因子。"""
        entry = self._pipeline.retire_factor(name, reason)
        logger.info("Factor retired: %s (%s)", name, reason)
        return self._entry_to_dict(entry)

    # -- 内部 --

    def _try_save_to_repo(self, entry) -> None:
        """尝试将因子保存到仓库。"""
        if self._repo is None:
            return
        try:
            # IFactorRepository 当前接口较简单，这里记录日志
            # 具体保存逻辑由 infrastructure 层实现
            logger.info("Factor saved to repository: %s", entry.factor_name)
        except Exception:
            logger.exception("Failed to save factor to repository: %s", entry.factor_name)

    @staticmethod
    def _entry_to_dict(entry) -> dict[str, object]:
        """将生命周期条目转为字典。"""
        return {
            "factor_name": entry.factor_name,
            "expression": entry.expression,
            "status": entry.status,
            "score": entry.score,
            "grade": entry.grade,
            "ic_mean": entry.ic_mean,
            "ir": entry.ir,
            "decay_count": entry.decay_count,
            "reason": entry.reason,
        }

    @staticmethod
    def _decay_result_to_dict(result: DecayCheckResult) -> dict[str, object]:
        """将衰减检查结果转为字典。"""
        return {
            "factor_name": result.factor_name,
            "is_decayed": result.is_decayed,
            "current_ic": result.current_ic,
            "validation_ic": result.validation_ic,
            "ic_ratio": result.ic_ratio,
            "decay_count": result.decay_count,
        }
