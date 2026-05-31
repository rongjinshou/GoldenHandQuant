from typing import Protocol


class IFactorRepository(Protocol):
    """因子仓库接口（Domain 层 Protocol，解除对 infrastructure 的反向依赖）。"""

    def list_factors(self, status: str = "active", min_ir: float = 0.0) -> list[dict]:
        """列出符合条件的因子。"""
        ...

    def to_domain_factor(self, name: str) -> object:
        """将存储的因子转换为 domain MinedFactor 实例。"""
        ...
