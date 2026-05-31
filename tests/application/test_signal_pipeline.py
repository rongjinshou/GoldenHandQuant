from datetime import datetime

from src.application.signal_pipeline import SignalPipeline
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.trade.value_objects.order_direction import OrderDirection


def _make_signal(
    symbol: str = "600000.SH",
    direction: SignalDirection = SignalDirection.BUY,
    confidence: float = 0.8,
    strategy: str = "test",
) -> Signal:
    return Signal(
        symbol=symbol,
        direction=direction,
        confidence_score=confidence,
        strategy_name=strategy,
    )


class TestSignalPipeline:
    def test_deduplicate_keeps_highest_confidence(self):
        pipeline = SignalPipeline()
        signals = [
            _make_signal(confidence=0.6, strategy="a"),
            _make_signal(confidence=0.9, strategy="b"),
            _make_signal(confidence=0.7, strategy="c"),
        ]
        result = pipeline.deduplicate(signals)
        assert len(result) == 1
        assert result[0].confidence_score == 0.9
        assert result[0].strategy_name == "b"

    def test_deduplicate_different_symbols(self):
        pipeline = SignalPipeline()
        signals = [
            _make_signal(symbol="600000.SH", confidence=0.8),
            _make_signal(symbol="000001.SZ", confidence=0.7),
        ]
        result = pipeline.deduplicate(signals)
        assert len(result) == 2

    def test_filter_by_confidence(self):
        pipeline = SignalPipeline(min_confidence=0.7)
        signals = [
            _make_signal(confidence=0.6),
            _make_signal(confidence=0.8),
            _make_signal(confidence=0.9),
        ]
        result = pipeline.filter_by_confidence(signals)
        assert len(result) == 2
        assert all(s.confidence_score >= 0.7 for s in result)

    def test_resolve_conflicts_sell_wins(self):
        pipeline = SignalPipeline()
        signals = [
            _make_signal(direction=SignalDirection.BUY, confidence=0.9),
            _make_signal(direction=SignalDirection.SELL, confidence=0.7),
        ]
        result = pipeline.resolve_conflicts(signals)
        assert len(result) == 1
        assert result[0].direction == SignalDirection.SELL

    def test_resolve_conflicts_no_conflict(self):
        pipeline = SignalPipeline()
        signals = [
            _make_signal(symbol="600000.SH", direction=SignalDirection.BUY),
            _make_signal(symbol="000001.SZ", direction=SignalDirection.SELL),
        ]
        result = pipeline.resolve_conflicts(signals)
        assert len(result) == 2

    def test_signals_to_targets(self):
        pipeline = SignalPipeline()
        signals = [_make_signal(symbol="600000.SH", direction=SignalDirection.BUY)]
        prices = {"600000.SH": 10.0}
        targets = pipeline.signals_to_targets(signals, prices)
        assert len(targets) == 1
        assert targets[0].symbol == "600000.SH"
        assert targets[0].direction == OrderDirection.BUY
        assert targets[0].price == 10.0

    def test_signals_to_targets_skips_missing_price(self):
        pipeline = SignalPipeline()
        signals = [_make_signal(symbol="600000.SH")]
        targets = pipeline.signals_to_targets(signals, prices={})
        assert len(targets) == 0

    def test_process_full_pipeline(self):
        pipeline = SignalPipeline(min_confidence=0.7)
        signals = [
            _make_signal(symbol="600000.SH", confidence=0.9, direction=SignalDirection.BUY),
            _make_signal(symbol="600000.SH", confidence=0.5, direction=SignalDirection.BUY),  # low conf
            _make_signal(symbol="000001.SZ", confidence=0.8, direction=SignalDirection.SELL),
        ]
        prices = {"600000.SH": 10.0, "000001.SZ": 20.0}
        targets = pipeline.process(signals, prices)
        assert len(targets) == 2
