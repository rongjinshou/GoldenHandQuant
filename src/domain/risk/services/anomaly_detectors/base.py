from typing import Protocol, runtime_checkable

from src.domain.risk.value_objects.anomaly_event import AnomalyEvent


@runtime_checkable
class BaseAnomalyDetector(Protocol):
    """异常检测器接口。"""

    def detect(self) -> list[AnomalyEvent]:
        """执行异常检测。

        Returns:
            检测到的异常事件列表。
        """
        ...
