import logging
import time
from datetime import datetime

logger = logging.getLogger("quantflow.backtest")


def setup_backtest_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(handler)
    logger.setLevel(level)


class BacktestProgress:
    """回测进度追踪器。"""

    def __init__(self, total_steps: int) -> None:
        self.total = total_steps
        self.current = 0
        self.start_time = time.time()
        self._milestone_pct = 0

    def update(self, current_date: datetime) -> None:
        self.current += 1
        pct = int(self.current / self.total * 100)
        if pct >= self._milestone_pct + 10:
            self._milestone_pct = (pct // 10) * 10
            elapsed = time.time() - self.start_time
            eta = elapsed / self.current * (self.total - self.current) if self.current > 0 else 0
            logger.info(
                f"Progress: {self.current}/{self.total} ({pct}%) | "
                f"Date: {current_date.strftime('%Y-%m-%d')} | "
                f"Elapsed: {elapsed:.0f}s | ETA: {eta:.0f}s"
            )
