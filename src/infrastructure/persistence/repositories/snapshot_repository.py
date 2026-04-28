from datetime import datetime

from src.infrastructure.persistence.database import Database
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot


class SnapshotRepository:
    """日终快照持久化仓库（Infrastructure 层）。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, snapshot: DailySnapshot) -> None:
        self._db.execute(
            """INSERT INTO daily_snapshots
               (date, total_asset, available_cash, market_value, pnl, return_rate)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                snapshot.date.strftime("%Y-%m-%d") if isinstance(snapshot.date, datetime) else str(snapshot.date),
                snapshot.total_asset,
                snapshot.available_cash,
                snapshot.market_value,
                snapshot.pnl,
                snapshot.return_rate,
            ),
        )
        self._db.commit()

    def find_all(self) -> list[dict]:
        cursor = self._db.execute(
            "SELECT * FROM daily_snapshots ORDER BY date"
        )
        return [dict(row) for row in cursor.fetchall()]

    def find_by_date_range(self, start_date: str, end_date: str) -> list[dict]:
        cursor = self._db.execute(
            "SELECT * FROM daily_snapshots WHERE date >= ? AND date <= ? ORDER BY date",
            (start_date, end_date),
        )
        return [dict(row) for row in cursor.fetchall()]
