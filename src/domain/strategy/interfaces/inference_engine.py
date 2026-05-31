from typing import Any, Protocol


class IInferenceEngine(Protocol):
    """推理引擎接口（Domain 层 Protocol，解除对 infrastructure 的反向依赖）。"""

    def predict_batch(
        self, model_name: str, feature_dict: dict[str, Any]
    ) -> dict[str, float]:
        """批量预测，返回 symbol -> score 映射。"""
        ...
