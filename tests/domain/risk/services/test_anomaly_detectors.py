from dataclasses import dataclass
from datetime import datetime, timedelta

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.risk.services.anomaly_detectors.data_anomaly import DataAnomalyDetector
from src.domain.risk.services.anomaly_detectors.market_anomaly import MarketAnomalyDetector
from src.domain.risk.services.anomaly_detectors.strategy_anomaly import StrategyAnomalyDetector
from src.domain.risk.value_objects.anomaly_event import AnomalySeverity, AutoAction
from src.domain.trade.interfaces.repositories.trade_history_repo import TradeRecord
from src.domain.trade.value_objects.order_direction import OrderDirection

# --- Helpers ---

@dataclass(slots=True, kw_only=True)
class FakeTradeHistory:
    """Fake TradeHistoryRepository for testing."""
    trades: list[TradeRecord]

    def get_recent_trades(self, strategy_name: str, limit: int) -> list[TradeRecord]:
        return self.trades[-limit:]

    def get_trades_in_range(self, strategy_name: str, start: datetime, end: datetime) -> list[TradeRecord]:
        return self.trades


class FakeMarketGateway:
    """Fake IMarketGateway for testing."""
    def __init__(self, bars: dict[str, list[Bar]] | None = None) -> None:
        self._bars = bars or {}

    def get_recent_bars(self, symbol: str, timeframe: Timeframe, limit: int) -> list[Bar]:
        return self._bars.get(symbol, [])[-limit:]

    def get_stock_snapshots(self, symbols: list[str]) -> list:
        return []


def _make_trade(pnl: float, executed_at: datetime | None = None) -> TradeRecord:
    return TradeRecord(
        order_id="test",
        symbol="600000.SH",
        direction=OrderDirection.BUY,
        price=10.0,
        volume=100,
        strategy_name="test_strategy",
        pnl=pnl,
        executed_at=executed_at or datetime(2026, 1, 1),
    )


def _make_bars(closes: list[float], volumes: list[float] | None = None) -> list[Bar]:
    if volumes is None:
        volumes = [1_000_000] * len(closes)
    base = datetime(2025, 1, 1)
    return [
        Bar(
            symbol="000300.SH",
            timeframe=Timeframe.DAY_1,
            timestamp=base + timedelta(days=i),
            open=c,
            high=c * 1.01,
            low=c * 0.99,
            close=c,
            volume=v,
        )
        for i, (c, v) in enumerate(zip(closes, volumes))
    ]


# --- StrategyAnomalyDetector ---

class TestStrategyAnomalyDetector:
    def test_no_anomaly_with_good_win_rate(self):
        history = FakeTradeHistory(trades=[_make_trade(pnl=100) for _ in range(20)])
        detector = StrategyAnomalyDetector(history, "test_strategy")
        events = detector.detect()
        assert len(events) == 0

    def test_detect_low_win_rate(self):
        trades = [_make_trade(pnl=-100) for _ in range(18)] + [_make_trade(pnl=100) for _ in range(2)]
        history = FakeTradeHistory(trades=trades)
        detector = StrategyAnomalyDetector(history, "test_strategy", min_win_rate=0.45)
        events = detector.detect()
        win_rate_events = [e for e in events if "胜率" in e.message]
        assert len(win_rate_events) == 1
        assert win_rate_events[0].severity == AnomalySeverity.CRITICAL
        assert win_rate_events[0].auto_action == AutoAction.PAUSE_STRATEGY

    def test_detect_consecutive_losses(self):
        trades = [_make_trade(pnl=100)] + [_make_trade(pnl=-100) for _ in range(5)]
        history = FakeTradeHistory(trades=trades)
        detector = StrategyAnomalyDetector(history, "test_strategy", max_consecutive_losses=5)
        events = detector.detect()
        loss_events = [e for e in events if "连续亏损" in e.message]
        assert len(loss_events) == 1
        assert loss_events[0].auto_action == AutoAction.PAUSE_STRATEGY

    def test_no_anomaly_with_insufficient_trades(self):
        history = FakeTradeHistory(trades=[_make_trade(pnl=-100) for _ in range(3)])
        detector = StrategyAnomalyDetector(history, "test_strategy")
        events = detector.detect()
        assert len(events) == 0


# --- DataAnomalyDetector ---

class TestDataAnomalyDetector:
    def test_no_anomaly_normal_data(self):
        bars = _make_bars([10.0, 10.1, 10.2, 10.0, 10.1])
        gateway = FakeMarketGateway(bars={"000300.SH": bars})
        detector = DataAnomalyDetector(gateway, ["000300.SH"])
        events = detector.detect()
        assert len(events) == 0

    def test_detect_missing_data(self):
        gateway = FakeMarketGateway(bars={})
        detector = DataAnomalyDetector(gateway, ["600000.SH"])
        events = detector.detect()
        assert len(events) == 1
        assert "无行情数据" in events[0].message

    def test_detect_price_jump(self):
        bars = _make_bars([10.0, 10.0, 10.0, 10.0, 12.0])  # 20% jump
        gateway = FakeMarketGateway(bars={"000300.SH": bars})
        detector = DataAnomalyDetector(gateway, ["000300.SH"], max_price_jump=0.10)
        events = detector.detect()
        jump_events = [e for e in events if "跳变" in e.message]
        assert len(jump_events) >= 1

    def test_detect_volume_spike(self):
        volumes = [1_000_000] * 4 + [20_000_000]  # 20x spike
        bars = _make_bars([10.0, 10.1, 10.0, 10.1, 10.2], volumes)
        gateway = FakeMarketGateway(bars={"000300.SH": bars})
        detector = DataAnomalyDetector(gateway, ["000300.SH"], volume_spike_ratio=10.0)
        events = detector.detect()
        volume_events = [e for e in events if "成交量" in e.message]
        assert len(volume_events) >= 1


# --- MarketAnomalyDetector ---

class TestMarketAnomalyDetector:
    def test_no_anomaly_normal_market(self):
        bars = _make_bars([100.0, 101.0, 102.0, 101.5, 102.5])
        gateway = FakeMarketGateway(bars={"000300.SH": bars})
        detector = MarketAnomalyDetector(gateway, index_symbol="000300.SH")
        events = detector.detect()
        assert len(events) == 0

    def test_detect_index_crash(self):
        bars = _make_bars([100.0, 101.0, 102.0, 101.0, 96.0])  # ~5% drop
        gateway = FakeMarketGateway(bars={"000300.SH": bars})
        detector = MarketAnomalyDetector(gateway, index_symbol="000300.SH", crash_threshold=-0.03)
        events = detector.detect()
        crash_events = [e for e in events if "暴跌" in e.message]
        assert len(crash_events) == 1
        assert crash_events[0].auto_action == AutoAction.PAUSE_ALL

    def test_detect_consecutive_drops(self):
        bars = _make_bars([110.0, 108.0, 106.0, 104.0, 102.0, 100.0])
        gateway = FakeMarketGateway(bars={"000300.SH": bars})
        detector = MarketAnomalyDetector(gateway, index_symbol="000300.SH", max_consecutive_drops=5)
        events = detector.detect()
        drop_events = [e for e in events if "连续下跌" in e.message]
        assert len(drop_events) == 1
        assert drop_events[0].auto_action == AutoAction.PAUSE_ALL

    def test_no_crash_with_insufficient_data(self):
        bars = _make_bars([100.0])
        gateway = FakeMarketGateway(bars={"000300.SH": bars})
        detector = MarketAnomalyDetector(gateway, index_symbol="000300.SH")
        events = detector.detect()
        assert len(events) == 0
