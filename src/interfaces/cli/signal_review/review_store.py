import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from src.domain.strategy.value_objects.review_action import ReviewAction
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.strategy.value_objects.signal_review_record import SignalReviewRecord

logger = logging.getLogger(__name__)


class ReviewStore:
    """审核记录 JSON 持久化。"""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or Path("resources/signal_reviews")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _today_path(self) -> Path:
        return self.storage_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"

    def load_today(self) -> list[SignalReviewRecord]:
        """加载当日审核记录。文件不存在或损坏则返回空列表。"""
        path = self._today_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [self._deserialize(r) for r in data.get("reviews", [])]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("审核记录文件损坏，将新建: %s (%s)", path, e)
            return []

    def append(self, record: SignalReviewRecord) -> None:
        """追加一条记录并写入文件。"""
        records = self.load_today()
        records.append(record)
        self.save_all(records)

    def save_all(self, records: list[SignalReviewRecord]) -> None:
        """批量写入审核记录。"""
        path = self._today_path()
        data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "reviews": [self._serialize(r) for r in records],
            "summary": self._build_summary(records),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_strategy_stats(self, strategy_name: str, lookback_days: int = 30) -> dict:
        """查询策略历史统计。"""
        approved = 0
        rejected = 0
        total = 0

        for i in range(lookback_days):
            date = datetime.now() - timedelta(days=i)
            path = self.storage_dir / f"{date.strftime('%Y-%m-%d')}.json"
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for r in data.get("reviews", []):
                    if r.get("strategy_name") == strategy_name:
                        total += 1
                        if r.get("action") == ReviewAction.APPROVED:
                            approved += 1
                        elif r.get("action") == ReviewAction.REJECTED:
                            rejected += 1
            except (json.JSONDecodeError, KeyError):
                continue

        win_rate = approved / total if total > 0 else 0.0
        return {
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "win_rate": win_rate,
        }

    @staticmethod
    def _serialize(record: SignalReviewRecord) -> dict:
        return {
            "record_id": record.record_id,
            "symbol": record.signal.symbol,
            "direction": record.signal.direction.value,
            "strategy_name": record.signal.strategy_name,
            "action": record.action.value,
            "reviewed_at": record.reviewed_at.isoformat(),
            "reviewer_note": record.reviewer_note,
            "order_id": record.order_id,
            "suggested_price": record.suggested_price,
            "suggested_volume": record.suggested_volume,
            "risk_score": record.risk_score,
            "ml_confidence": record.ml_confidence,
            "signal_age_hours": record.signal_age_hours,
            "reason": record.signal.reason,
            "confidence_score": record.signal.confidence_score,
        }

    @staticmethod
    def _deserialize(data: dict) -> SignalReviewRecord:
        signal = Signal(
            symbol=data["symbol"],
            direction=SignalDirection(data["direction"]),
            strategy_name=data.get("strategy_name", ""),
            reason=data.get("reason", ""),
            confidence_score=data.get("confidence_score", 1.0),
        )
        return SignalReviewRecord(
            record_id=data["record_id"],
            signal=signal,
            action=ReviewAction(data["action"]),
            reviewed_at=datetime.fromisoformat(data["reviewed_at"]),
            reviewer_note=data.get("reviewer_note", ""),
            order_id=data.get("order_id", ""),
            suggested_price=data.get("suggested_price", 0.0),
            suggested_volume=data.get("suggested_volume", 0),
            risk_score=data.get("risk_score", 0.0),
            ml_confidence=data.get("ml_confidence", 0.0),
            signal_age_hours=data.get("signal_age_hours", 0.0),
        )

    @staticmethod
    def _build_summary(records: list[SignalReviewRecord]) -> dict:
        approved = sum(1 for r in records if r.action == ReviewAction.APPROVED)
        rejected = sum(1 for r in records if r.action == ReviewAction.REJECTED)
        skipped = sum(1 for r in records if r.action == ReviewAction.SKIPPED)
        capital = sum(
            r.suggested_price * r.suggested_volume
            for r in records
            if r.action == ReviewAction.APPROVED
        )
        return {
            "total_signals": len(records),
            "approved": approved,
            "rejected": rejected,
            "skipped": skipped,
            "total_capital_deployed": round(capital, 2),
        }
