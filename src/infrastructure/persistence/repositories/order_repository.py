from datetime import datetime

from src.infrastructure.persistence.database import Database
from src.domain.trade.entities.order import Order


class OrderRepository:
    """订单持久化仓库（Infrastructure 层）。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, order: Order) -> None:
        self._db.execute(
            """INSERT OR REPLACE INTO orders
               (order_id, account_id, ticker, direction, price, volume,
                filled_volume, order_type, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                order.order_id, order.account_id, order.ticker,
                order.direction.value, order.price, order.volume,
                order.traded_volume, order.type.value, order.status.value,
                order.created_at.isoformat() if order.created_at else None,
            ),
        )
        self._db.commit()

    def find_by_id(self, order_id: str) -> dict | None:
        cursor = self._db.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def find_by_account(self, account_id: str) -> list[dict]:
        cursor = self._db.execute(
            "SELECT * FROM orders WHERE account_id = ? ORDER BY created_at",
            (account_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_status(self, order_id: str, status: str) -> None:
        self._db.execute(
            "UPDATE orders SET status = ?, updated_at = datetime('now') WHERE order_id = ?",
            (status, order_id),
        )
        self._db.commit()
