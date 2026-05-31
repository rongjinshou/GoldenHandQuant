import json
import tempfile
from datetime import datetime
from pathlib import Path

from src.domain.strategy.value_objects.review_action import ReviewAction
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.strategy.value_objects.signal_review_record import SignalReviewRecord
from src.interfaces.cli.signal_review.review_store import ReviewStore


def _make_record(
    symbol: str = "600000.SH",
    action: ReviewAction = ReviewAction.APPROVED,
    strategy_name: str = "test",
) -> SignalReviewRecord:
    signal = Signal(
        symbol=symbol,
        direction=SignalDirection.BUY,
        confidence_score=0.85,
        strategy_name=strategy_name,
        reason="test reason",
    )
    return SignalReviewRecord(
        record_id="abc123",
        signal=signal,
        action=action,
        reviewed_at=datetime(2026, 5, 31, 9, 15, 0),
        suggested_price=10.50,
        suggested_volume=900,
        risk_score=0.2,
    )


class TestReviewStore:
    def test_load_today_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReviewStore(Path(tmpdir))
            records = store.load_today()
            assert records == []

    def test_append_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReviewStore(Path(tmpdir))
            record = _make_record()
            store.append(record)

            records = store.load_today()
            assert len(records) == 1
            assert records[0].record_id == "abc123"
            assert records[0].signal.symbol == "600000.SH"
            assert records[0].action == ReviewAction.APPROVED

    def test_save_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReviewStore(Path(tmpdir))
            records = [_make_record("A"), _make_record("B")]
            store.save_all(records)

            loaded = store.load_today()
            assert len(loaded) == 2

    def test_json_file_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReviewStore(Path(tmpdir))
            store.append(_make_record())

            # Read the JSON file directly
            today = datetime.now().strftime("%Y-%m-%d")
            path = Path(tmpdir) / f"{today}.json"
            assert path.exists()

            data = json.loads(path.read_text())
            assert data["date"] == today
            assert len(data["reviews"]) == 1
            assert data["reviews"][0]["symbol"] == "600000.SH"
            assert data["summary"]["total_signals"] == 1
            assert data["summary"]["approved"] == 1

    def test_corrupted_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            today = datetime.now().strftime("%Y-%m-%d")
            path = Path(tmpdir) / f"{today}.json"
            path.write_text("not valid json", encoding="utf-8")

            store = ReviewStore(Path(tmpdir))
            records = store.load_today()
            assert records == []

    def test_get_strategy_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReviewStore(Path(tmpdir))
            store.append(_make_record(action=ReviewAction.APPROVED, strategy_name="my_strat"))
            store.append(_make_record(action=ReviewAction.REJECTED, strategy_name="my_strat"))
            store.append(_make_record(action=ReviewAction.APPROVED, strategy_name="other"))

            stats = store.get_strategy_stats("my_strat")
            assert stats["total"] == 2
            assert stats["approved"] == 1
            assert stats["rejected"] == 1
            assert stats["win_rate"] == 0.5

    def test_serialize_deserialize_roundtrip(self):
        record = _make_record()
        serialized = ReviewStore._serialize(record)
        deserialized = ReviewStore._deserialize(serialized)

        assert deserialized.record_id == record.record_id
        assert deserialized.signal.symbol == record.signal.symbol
        assert deserialized.signal.direction == record.signal.direction
        assert deserialized.action == record.action
        assert deserialized.suggested_price == record.suggested_price
