import tempfile
import os
from pathlib import Path

from src.infrastructure.persistence.database import Database
from src.infrastructure.persistence.repositories.order_repository import OrderRepository
from src.infrastructure.persistence.repositories.snapshot_repository import SnapshotRepository
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from datetime import datetime


def _setup_db(db_path: str) -> Database:
    db = Database(db_path)
    schema_path = Path("src/infrastructure/persistence/migrations/001_initial_schema.sql")
    schema = schema_path.read_text()
    for stmt in schema.split(";"):
        stmt = stmt.strip()
        if stmt:
            db.execute(stmt)
    db.commit()
    return db


def test_save_and_retrieve_order():
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    db = _setup_db(db_path)

    repo = OrderRepository(db)
    order = Order(
        order_id="TEST_001", account_id="ACC_1", ticker="000001.SZ",
        direction=OrderDirection.BUY, price=10.0, volume=100,
        type=OrderType.LIMIT,
    )
    repo.save(order)

    retrieved = repo.find_by_id("TEST_001")
    assert retrieved is not None
    assert retrieved["ticker"] == "000001.SZ"
    assert retrieved["price"] == 10.0
    assert retrieved["status"] == "CREATED"

    db.close()


def test_update_order_status():
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    db = _setup_db(db_path)

    repo = OrderRepository(db)
    order = Order(
        order_id="TEST_002", account_id="ACC_1", ticker="000002.SZ",
        direction=OrderDirection.SELL, price=20.0, volume=200,
        type=OrderType.LIMIT,
    )
    repo.save(order)
    repo.update_status("TEST_002", "FILLED")

    retrieved = repo.find_by_id("TEST_002")
    assert retrieved is not None
    assert retrieved["status"] == "FILLED"

    db.close()


def test_find_orders_by_account():
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    db = _setup_db(db_path)

    repo = OrderRepository(db)
    o1 = Order(
        order_id="ORD_A1", account_id="ACC_A", ticker="000001.SZ",
        direction=OrderDirection.BUY, price=10.0, volume=100,
        type=OrderType.LIMIT,
    )
    o2 = Order(
        order_id="ORD_A2", account_id="ACC_A", ticker="000002.SZ",
        direction=OrderDirection.SELL, price=20.0, volume=200,
        type=OrderType.LIMIT,
    )
    o3 = Order(
        order_id="ORD_B1", account_id="ACC_B", ticker="000003.SZ",
        direction=OrderDirection.BUY, price=30.0, volume=300,
        type=OrderType.LIMIT,
    )
    repo.save(o1)
    repo.save(o2)
    repo.save(o3)

    acc_a_orders = repo.find_by_account("ACC_A")
    assert len(acc_a_orders) == 2
    tickers = {o["ticker"] for o in acc_a_orders}
    assert tickers == {"000001.SZ", "000002.SZ"}

    db.close()


def test_save_and_retrieve_snapshot():
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    db = _setup_db(db_path)

    repo = SnapshotRepository(db)
    snap = DailySnapshot(
        date=datetime(2024, 1, 4),
        total_asset=100000.0,
        available_cash=50000.0,
        market_value=50000.0,
        pnl=1000.0,
        return_rate=0.01,
    )
    repo.save(snap)

    all_snaps = repo.find_all()
    assert len(all_snaps) == 1
    assert all_snaps[0]["total_asset"] == 100000.0
    assert all_snaps[0]["pnl"] == 1000.0

    db.close()


def test_find_snapshots_by_date_range():
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    db = _setup_db(db_path)

    repo = SnapshotRepository(db)
    for i, d in enumerate([datetime(2024, 1, 4), datetime(2024, 1, 5), datetime(2024, 1, 6)]):
        repo.save(DailySnapshot(
            date=d, total_asset=float(100000 + i * 1000),
            available_cash=50000.0, market_value=50000.0,
        ))

    results = repo.find_by_date_range("2024-01-04", "2024-01-05")
    assert len(results) == 2

    db.close()
