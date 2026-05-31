import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SnapshotStore:
    """账户快照持久化 — 以 JSON 文件存储每日快照。"""

    def __init__(self, snapshot_dir: str = "data/snapshots/") -> None:
        self._dir = Path(snapshot_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, date: datetime, data: dict) -> None:
        """保存快照。"""
        path = self._dir / f"{date.strftime('%Y-%m-%d')}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Snapshot saved: %s", path)

    def load_latest(self) -> dict | None:
        """加载最近一个快照。"""
        files = sorted(self._dir.glob("*.json"), reverse=True)
        if not files:
            return None
        with open(files[0], encoding="utf-8") as f:
            return json.load(f)

    def load_by_date(self, date: datetime) -> dict | None:
        """按日期加载快照。"""
        path = self._dir / f"{date.strftime('%Y-%m-%d')}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)
