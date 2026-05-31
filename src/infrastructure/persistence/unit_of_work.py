"""SQLite 工作单元实现（infrastructure 层）。

基于 sqlite3 的事务管理，确保下单→冻结资金→撮合→扣款的原子性。
"""

import logging
from typing import Self

from src.domain.common.unit_of_work import UnitOfWork
from src.infrastructure.persistence.database import Database

logger = logging.getLogger(__name__)


class SQLiteUnitOfWork(UnitOfWork):
    """基于 SQLite 的事务工作单元。

    使用示例：
        db = Database("data/backtest.db")
        with SQLiteUnitOfWork(db) as uow:
            # 下单
            trade_gateway.place_order(order)
            # 冻结资金
            asset.freeze_cash(amount)
            # 记录快照
            snapshot_repo.save(snapshot)
            # 任何一步异常，自动回滚

    注意：SQLite 默认 autocommit，这里显式使用 BEGIN/COMMIT/ROLLBACK。
    """

    def __init__(self, db: Database) -> None:
        self._db = db
        self._in_transaction = False

    def __enter__(self) -> Self:
        self._db.execute("BEGIN TRANSACTION")
        self._in_transaction = True
        logger.debug("事务已开启")
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        if not self._in_transaction:
            return

        if exc_type is None:
            self.commit()
        else:
            self.rollback()
            logger.warning("事务回滚，原因: %s", exc_val)

    def commit(self) -> None:
        if self._in_transaction:
            self._db.commit()
            self._in_transaction = False
            logger.debug("事务已提交")

    def rollback(self) -> None:
        if self._in_transaction:
            self._db.execute("ROLLBACK")
            self._in_transaction = False
            logger.debug("事务已回滚")
