"""影子模式服务 — 管理影子模型的信号记录与验证。"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.domain.strategy.pool.value_objects.ml_model_version import MLModelVersion
from src.domain.strategy.value_objects.model_deployment_strategy import (
    ModelDeploymentStrategy,
)
from src.domain.strategy.value_objects.shadow_comparison_log import ShadowComparisonLog

logger = logging.getLogger(__name__)


class ShadowLogRepository(Protocol):
    """影子对比日志仓储接口。"""

    def save(self, log: ShadowComparisonLog) -> None: ...

    def find_by_model_pair(
        self,
        active_version_id: str,
        shadow_version_id: str,
    ) -> list[ShadowComparisonLog]: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class ShadowValidationResult:
    """影子验证结果（值对象）。

    Attributes:
        passed: 是否通过验证。
        agreement_rate: 方向一致率 (0.0 ~ 1.0)。
        avg_confidence_diff: 平均置信度差异 (0.0 ~ 1.0)。
        total_signals: 参与对比的信号总数。
        validated_at: 验证时间。
    """

    passed: bool
    agreement_rate: float
    avg_confidence_diff: float
    total_signals: int
    validated_at: datetime


class ShadowModeService:
    """影子模式领域服务。

    职责:
    1. 记录活跃模型与影子模型的信号对比。
    2. 验证影子模型是否可晋升（方向一致率 + 置信度差异达标）。
    """

    def __init__(
        self,
        active_model: MLModelVersion,
        shadow_model: MLModelVersion,
        log_repository: ShadowLogRepository,
        min_agreement_rate: float = 0.7,
        max_confidence_diff: float = 0.3,
    ) -> None:
        if active_model.deployment == ModelDeploymentStrategy.SHADOW:
            raise ValueError("active_model must not be SHADOW deployment")
        if shadow_model.deployment != ModelDeploymentStrategy.SHADOW:
            raise ValueError("shadow_model must be SHADOW deployment")
        self._active_model = active_model
        self._shadow_model = shadow_model
        self._log_repo = log_repository
        self._min_agreement_rate = min_agreement_rate
        self._max_confidence_diff = max_confidence_diff

    @property
    def active_model(self) -> MLModelVersion:
        return self._active_model

    @property
    def shadow_model(self) -> MLModelVersion:
        return self._shadow_model

    def record_shadow_signals(
        self,
        active_signals: dict[str, tuple[str, float]],
        shadow_signals: dict[str, tuple[str, float]],
    ) -> list[ShadowComparisonLog]:
        """记录活跃模型与影子模型的信号对比。

        Args:
            active_signals: {symbol: (direction, confidence)} 活跃模型信号。
            shadow_signals: {symbol: (direction, confidence)} 影子模型信号。

        Returns:
            本次创建的对比日志列表。
        """
        all_symbols = sorted(set(active_signals) | set(shadow_signals))
        now = datetime.now()
        logs: list[ShadowComparisonLog] = []

        for symbol in all_symbols:
            if symbol in active_signals and symbol in shadow_signals:
                act_dir, act_conf = active_signals[symbol]
                shd_dir, shd_conf = shadow_signals[symbol]
            elif symbol in active_signals:
                act_dir, act_conf = active_signals[symbol]
                shd_dir, shd_conf = "HOLD", 0.0
            else:
                act_dir, act_conf = "HOLD", 0.0
                shd_dir, shd_conf = shadow_signals[symbol]

            directions_match = act_dir == shd_dir
            divergence = ShadowComparisonLog.compute_divergence(
                act_conf, shd_conf, directions_match,
            )

            log = ShadowComparisonLog(
                active_version_id=self._active_model.version_id,
                shadow_version_id=self._shadow_model.version_id,
                symbol=symbol,
                active_direction=act_dir,
                shadow_direction=shd_dir,
                active_confidence=act_conf,
                shadow_confidence=shd_conf,
                match=directions_match,
                divergence=divergence,
                recorded_at=now,
            )
            self._log_repo.save(log)
            logs.append(log)

        logger.info(
            "Recorded %d shadow comparisons: active=%s vs shadow=%s",
            len(logs),
            self._active_model.version_id,
            self._shadow_model.version_id,
        )
        return logs

    def validate_shadow(self) -> ShadowValidationResult:
        """验证影子模型是否可晋升。

        标准:
        - 方向一致率 >= min_agreement_rate
        - 平均置信度差异 <= max_confidence_diff

        Returns:
            ShadowValidationResult 包含验证结论与各项指标。
        """
        logs = self._log_repo.find_by_model_pair(
            self._active_model.version_id,
            self._shadow_model.version_id,
        )
        if not logs:
            return ShadowValidationResult(
                passed=False,
                agreement_rate=0.0,
                avg_confidence_diff=0.0,
                total_signals=0,
                validated_at=datetime.now(),
            )

        matches = sum(1 for log in logs if log.match)
        agreement_rate = matches / len(logs)
        avg_conf_diff = sum(log.divergence for log in logs) / len(logs)

        passed = (
            agreement_rate >= self._min_agreement_rate
            and avg_conf_diff <= self._max_confidence_diff
        )

        logger.info(
            "Shadow validation: active=%s vs shadow=%s, "
            "agreement=%.2f, avg_conf_diff=%.2f, total=%d, passed=%s",
            self._active_model.version_id,
            self._shadow_model.version_id,
            agreement_rate,
            avg_conf_diff,
            len(logs),
            passed,
        )

        return ShadowValidationResult(
            passed=passed,
            agreement_rate=round(agreement_rate, 6),
            avg_confidence_diff=round(avg_conf_diff, 6),
            total_signals=len(logs),
            validated_at=datetime.now(),
        )
