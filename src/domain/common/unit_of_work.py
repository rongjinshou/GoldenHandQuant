"""工作单元协议（domain 层接口，纯标准库）。

事务边界保证：确保下单→冻结资金→撮合→扣款的原子性。
"""

from abc import ABC, abstractmethod
from typing import Self


class UnitOfWork(ABC):
    """事务工作单元协议。

    使用上下文管理器模式：
        with uow:
            # 多步操作
        # 自动提交或回滚

    任何一步异常，自动回滚全部操作。
    """

    @abstractmethod
    def __enter__(self) -> Self:
        """开启事务。"""
        ...

    @abstractmethod
    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """提交或回滚事务。

        Args:
            exc_type: 异常类型（无异常时为 None）。
            exc_val: 异常值。
            exc_tb: 异常 traceback。
        """
        ...

    @abstractmethod
    def commit(self) -> None:
        """手动提交事务。"""
        ...

    @abstractmethod
    def rollback(self) -> None:
        """手动回滚事务。"""
        ...
