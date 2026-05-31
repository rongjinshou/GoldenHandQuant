"""ML 模型灰度发布应用服务。

编排 流漂移检测 → 自动重训练 → SHADOW → CANARY → FULL_ROLLOUT 灰度发布流水线。
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.domain.strategy.pool.value_objects.ml_model_version import MLModelVersion
from src.domain.strategy.services.shadow_mode_service import (
    ShadowModeService,
    ShadowValidationResult,
)
from src.domain.strategy.value_objects.model_deployment_strategy import (
    ModelDeploymentStrategy,
)

logger = logging.getLogger(__name__)


class DriftDetector(Protocol):
    """漂移检测器接口。"""

    def check_drift(self) -> bool:
        """检测模型是否发生漂移，返回 True 表示需要重训练。"""
        ...


class RetrainCallback(Protocol):
    """重训练回调接口。"""

    def retrain(self) -> MLModelVersion:
        """触发重训练，返回新模型版本。"""
        ...


@dataclass(slots=True, kw_only=True)
class ModelDeploymentState:
    """单个模型的部署状态。"""

    model: MLModelVersion
    deployed_at: datetime
    validated: bool = False
    validation_result: ShadowValidationResult | None = None


class MLDeploymentAppService:
    """ML 模型灰度发布应用服务。

    职责:
    1. 漂移检测 → 自动触发重训练。
    2. 新模型以 SHADOW 模式部署，与活跃模型对比。
    3. 影子验证通过后晋升为 CANARY，再晋升为 FULL_ROLLOUT。
    """

    def __init__(
        self,
        drift_detector: DriftDetector,
        retrain_callback: RetrainCallback,
        shadow_log_repository: object | None = None,
        min_agreement_rate: float = 0.7,
        max_confidence_diff: float = 0.3,
        canary_traffic_percentage: float = 0.2,
    ) -> None:
        self._drift_detector = drift_detector
        self._retrain_callback = retrain_callback
        self._shadow_log_repo = shadow_log_repository
        self._min_agreement_rate = min_agreement_rate
        self._max_confidence_diff = max_confidence_diff
        self._canary_traffic = canary_traffic_percentage
        self._deployments: dict[str, ModelDeploymentState] = {}
        self._shadow_service: ShadowModeService | None = None

    def deploy_shadow(self, model: MLModelVersion) -> MLModelVersion:
        """以 SHADOW 模式部署新模型。

        Args:
            model: 待部署的模型版本。

        Returns:
            更新部署策略后的模型版本。
        """
        shadow_model = model.with_deployment(
            ModelDeploymentStrategy.SHADOW,
            traffic_percentage=0.0,
        )
        self._deployments[shadow_model.version_id] = ModelDeploymentState(
            model=shadow_model,
            deployed_at=datetime.now(),
        )
        logger.info(
            "Deployed model %s as SHADOW",
            shadow_model.version_id,
        )
        return shadow_model

    def setup_shadow_comparison(
        self,
        active_model: MLModelVersion,
        shadow_model: MLModelVersion,
    ) -> ShadowModeService:
        """设置影子对比环境。

        Args:
            active_model: 当前活跃模型。
            shadow_model: 影子模型。

        Returns:
            配置好的 ShadowModeService 实例。
        """
        service = ShadowModeService(
            active_model=active_model,
            shadow_model=shadow_model,
            log_repository=self._shadow_log_repo,  # type: ignore[arg-type]
            min_agreement_rate=self._min_agreement_rate,
            max_confidence_diff=self._max_confidence_diff,
        )
        self._shadow_service = service
        return service

    def validate_shadow(self, shadow_version_id: str) -> ShadowValidationResult:
        """验证影子模型是否可晋升。

        Args:
            shadow_version_id: 影子模型版本 ID。

        Returns:
            ShadowValidationResult 包含验证结论与各项指标。

        Raises:
            ValueError: 如果影子服务未设置或版本 ID 不匹配。
        """
        if self._shadow_service is None:
            raise ValueError("Shadow comparison not set up, call setup_shadow_comparison first")
        if self._shadow_service.shadow_model.version_id != shadow_version_id:
            raise ValueError(
                f"Shadow version mismatch: expected "
                f"{self._shadow_service.shadow_model.version_id}, got {shadow_version_id}"
            )

        result = self._shadow_service.validate_shadow()

        # 更新部署状态
        if shadow_version_id in self._deployments:
            state = self._deployments[shadow_version_id]
            state.validated = result.passed
            state.validation_result = result

        logger.info(
            "Shadow validation for %s: passed=%s, agreement=%.2f",
            shadow_version_id,
            result.passed,
            result.agreement_rate,
        )
        return result

    def promote_to_canary(self, model_version_id: str) -> MLModelVersion:
        """将模型从 SHADOW 晋升为 CANARY。

        Args:
            model_version_id: 模型版本 ID。

        Returns:
            更新后的模型版本。

        Raises:
            ValueError: 如果模型未经影子验证通过。
        """
        state = self._deployments.get(model_version_id)
        if state is None:
            raise ValueError(f"Model {model_version_id} not found in deployments")
        if not state.validated:
            raise ValueError(
                f"Model {model_version_id} has not passed shadow validation"
            )

        canary_model = state.model.with_deployment(
            ModelDeploymentStrategy.CANARY,
            traffic_percentage=self._canary_traffic,
        )
        state.model = canary_model
        logger.info(
            "Promoted model %s to CANARY (traffic=%.0f%%)",
            model_version_id,
            self._canary_traffic * 100,
        )
        return canary_model

    def promote_to_full_rollout(self, model_version_id: str) -> MLModelVersion:
        """将模型从 CANARY 晋升为 FULL_ROLLOUT。

        Args:
            model_version_id: 模型版本 ID。

        Returns:
            更新后的模型版本。

        Raises:
            ValueError: 如果模型当前不是 CANARY 部署。
        """
        state = self._deployments.get(model_version_id)
        if state is None:
            raise ValueError(f"Model {model_version_id} not found in deployments")
        if state.model.deployment != ModelDeploymentStrategy.CANARY:
            raise ValueError(
                f"Model {model_version_id} is not in CANARY state, "
                f"current: {state.model.deployment.value}"
            )

        full_model = state.model.with_deployment(
            ModelDeploymentStrategy.FULL_ROLLOUT,
            traffic_percentage=1.0,
        )
        state.model = full_model
        logger.info(
            "Promoted model %s to FULL_ROLLOUT",
            model_version_id,
        )
        return full_model

    def run_health_check(self) -> MLModelVersion | None:
        """运行健康检查：漂移检测 → 自动重训练 → SHADOW 部署。

        Returns:
            如果触发重训练，返回新部署的影子模型版本；否则返回 None。
        """
        if not self._drift_detector.check_drift():
            logger.debug("No drift detected, skipping retrain")
            return None

        logger.warning("Drift detected, triggering retrain")
        new_model = self._retrain_callback.retrain()
        shadow_model = self.deploy_shadow(new_model)
        return shadow_model

    def get_deployment_state(self, model_version_id: str) -> ModelDeploymentState | None:
        """获取指定模型的部署状态。"""
        return self._deployments.get(model_version_id)

    def get_all_deployments(self) -> dict[str, ModelDeploymentState]:
        """获取所有模型部署状态。"""
        return dict(self._deployments)
