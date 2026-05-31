import logging
from typing import Protocol

from src.domain.risk.services.anomaly_detectors.base import BaseAnomalyDetector
from src.domain.risk.value_objects.anomaly_event import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyType,
    AutoAction,
)

logger = logging.getLogger(__name__)


class PredictionLogRepository(Protocol):
    """预测日志仓储接口。"""

    def get_recent_ic(self, lookback_days: int = 20) -> float:
        """获取最近 N 天的平均 IC。"""
        ...


class FeatureDistributionRepository(Protocol):
    """特征分布仓储接口。"""

    def get_drift_score(self) -> float:
        """获取特征漂移分数 (PSI)。"""
        ...


class MlModelAnomalyDetector(BaseAnomalyDetector):
    """ML 模型健康检测器。

    检测维度:
    1. 预测准确率下降: 近期预测 IC < 阈值
    2. 特征漂移: 输入特征分布与训练时差异 > 阈值
    """

    def __init__(
        self,
        prediction_log: PredictionLogRepository,
        feature_distribution: FeatureDistributionRepository,
        min_ic: float = 0.03,
        max_drift_score: float = 0.3,
    ) -> None:
        self._prediction_log = prediction_log
        self._feature_distribution = feature_distribution
        self._min_ic = min_ic
        self._max_drift_score = max_drift_score

    def detect(self) -> list[AnomalyEvent]:
        events: list[AnomalyEvent] = []

        events.extend(self._check_ic_decline())
        events.extend(self._check_feature_drift())

        return events

    def _check_ic_decline(self) -> list[AnomalyEvent]:
        """检测 IC 下降。"""
        events: list[AnomalyEvent] = []
        ic = self._prediction_log.get_recent_ic()

        if ic < self._min_ic:
            events.append(AnomalyEvent(
                anomaly_type=AnomalyType.ML_MODEL,
                severity=AnomalySeverity.CRITICAL,
                source="ml_model",
                message=(
                    f"ML 模型 IC 下降: {ic:.4f} < {self._min_ic:.4f}"
                ),
                metric_value=ic,
                threshold=self._min_ic,
                auto_action=AutoAction.PAUSE_STRATEGY,
            ))

        return events

    def _check_feature_drift(self) -> list[AnomalyEvent]:
        """检测特征漂移。"""
        events: list[AnomalyEvent] = []
        drift = self._feature_distribution.get_drift_score()

        if drift > self._max_drift_score:
            events.append(AnomalyEvent(
                anomaly_type=AnomalyType.ML_MODEL,
                severity=AnomalySeverity.WARNING,
                source="ml_model",
                message=(
                    f"ML 模型特征漂移: PSI={drift:.4f} > {self._max_drift_score:.4f}"
                ),
                metric_value=drift,
                threshold=self._max_drift_score,
                auto_action=AutoAction.NONE,
            ))

        return events
