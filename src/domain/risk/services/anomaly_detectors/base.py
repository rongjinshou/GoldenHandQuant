from abc import ABC, abstractmethod

from src.domain.risk.value_objects.anomaly_event import AnomalyEvent


class BaseAnomalyDetector(ABC):
    """异常检测器抽象基类。"""

    @abstractmethod
    def detect(self) -> list[AnomalyEvent]:
        """执行异常检测。

        Returns:
            检测到的异常事件列表。
        """
        ...
