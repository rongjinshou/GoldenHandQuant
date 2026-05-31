"""SQLiteUnitOfWork 测试。"""

import sqlite3

from src.infrastructure.persistence.database import Database
from src.infrastructure.persistence.unit_of_work import SQLiteUnitOfWork


class TestSQLiteUnitOfWork:
    def _create_db(self) -> Database:
        db = Database(":memory:")
        db.execute("""
            CREATE TABLE test_data (
                id INTEGER PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        db.commit()
        return db

    def test_commit_on_no_exception(self):
        # Arrange
        db = self._create_db()

        # Act
        with SQLiteUnitOfWork(db):
            db.execute("INSERT INTO test_data (value) VALUES (?)", ("test_value",))

        # Assert
        row = db.execute("SELECT value FROM test_data WHERE id = 1").fetchone()
        assert row["value"] == "test_value"

    def test_rollback_on_exception(self):
        # Arrange
        db = self._create_db()

        # Act
        try:
            with SQLiteUnitOfWork(db):
                db.execute("INSERT INTO test_data (value) VALUES (?)", ("should_rollback",))
                raise ValueError("模拟异常")
        except ValueError:
            pass

        # Assert
        rows = db.execute("SELECT * FROM test_data").fetchall()
        assert len(rows) == 0

    def test_multiple_operations_in_one_transaction(self):
        # Arrange
        db = self._create_db()

        # Act
        with SQLiteUnitOfWork(db):
            db.execute("INSERT INTO test_data (value) VALUES (?)", ("row1",))
            db.execute("INSERT INTO test_data (value) VALUES (?)", ("row2",))
            db.execute("INSERT INTO test_data (value) VALUES (?)", ("row3",))

        # Assert
        rows = db.execute("SELECT * FROM test_data").fetchall()
        assert len(rows) == 3

    def test_rollback_does_not_affect_previous_data(self):
        # Arrange
        db = self._create_db()
        with SQLiteUnitOfWork(db):
            db.execute("INSERT INTO test_data (value) VALUES (?)", ("committed",))

        # Act
        try:
            with SQLiteUnitOfWork(db):
                db.execute("INSERT INTO test_data (value) VALUES (?)", ("will_rollback",))
                raise RuntimeError("rollback!")
        except RuntimeError:
            pass

        # Assert
        rows = db.execute("SELECT * FROM test_data").fetchall()
        assert len(rows) == 1
        assert rows[0]["value"] == "committed"

    def test_manual_commit(self):
        # Arrange
        db = self._create_db()
        uow = SQLiteUnitOfWork(db)

        # Act
        uow.__enter__()
        db.execute("INSERT INTO test_data (value) VALUES (?)", ("manual_commit",))
        uow.commit()
        uow.__exit__(None, None, None)

        # Assert
        row = db.execute("SELECT value FROM test_data WHERE id = 1").fetchone()
        assert row["value"] == "manual_commit"

    def test_manual_rollback(self):
        # Arrange
        db = self._create_db()
        uow = SQLiteUnitOfWork(db)

        # Act
        uow.__enter__()
        db.execute("INSERT INTO test_data (value) VALUES (?)", ("will_rollback",))
        uow.rollback()
        uow.__exit__(None, None, None)

        # Assert
        rows = db.execute("SELECT * FROM test_data").fetchall()
        assert len(rows) == 0
