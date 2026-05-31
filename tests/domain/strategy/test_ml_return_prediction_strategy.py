"""测试 ML 收益预测策略。"""

from datetime import datetime

import numpy as np

from src.domain.account.entities.position import Position
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.services.strategies.ml_return_prediction_strategy import (
    MLReturnPredictionStrategy,
)
from src.domain.strategy.value_objects.signal_direction import SignalDirection


class FakeInferenceEngine:
    """Fake 推理引擎，用于替换 MagicMock。"""

    def __init__(self, predictions: dict[str, float]) -> None:
        self._predictions = predictions
        self.last_model_name: str | None = None
        self.last_feature_dict: dict[str, np.ndarray] | None = None

    def predict_batch(
        self, model_name: str, feature_dict: dict[str, np.ndarray]
    ) -> dict[str, float]:
        self.last_model_name = model_name
        self.last_feature_dict = feature_dict
        return self._predictions


def _make_snapshot(symbol: str, close: float = 10.0, **kwargs) -> StockSnapshot:
    defaults = dict(
        symbol=symbol, date=datetime(2025, 6, 1),
        open=close, high=close * 1.02, low=close * 0.98,
        close=close, volume=1e6,
        name="Test", list_date=datetime(2020, 1, 1), market_cap=1e10,
        return_5d=0.01, return_20d=0.02, return_60d=0.03,
        volatility_20d=0.02, volatility_60d=0.025,
        turnover_rate=1.0, avg_turnover_20d=1.0,
        rsi_14=50.0, macd=0.1, macd_signal=0.05,
        ma_5=close, ma_20=close, ma_60=close,
        high_20d=close * 1.1, low_20d=close * 0.9,
        atr_14=0.5, skewness_20d=0.0, illiquidity_20d=0.001,
        obv_slope_20d=100.0, pe_ratio=15.0, pb_ratio=2.0, roe_ttm=0.1,
    )
    defaults.update(kwargs)
    return StockSnapshot(**defaults)


def _make_position(ticker: str, volume: int = 100) -> Position:
    return Position(account_id="test", ticker=ticker, total_volume=volume, available_volume=volume)


class TestMLReturnPredictionStrategy:
    def test_name_includes_model_name(self) -> None:
        strategy = MLReturnPredictionStrategy(model_name="test_model")
        assert "test_model" in strategy.name

    def test_empty_universe_returns_empty(self) -> None:
        strategy = MLReturnPredictionStrategy(model_name="test_model")
        fake_engine = FakeInferenceEngine(predictions={})
        strategy.set_inference_engine(fake_engine)
        signals = strategy.generate_cross_sectional_signals([], [], datetime(2025, 6, 1))
        assert signals == []

    def test_no_inference_engine_returns_empty(self) -> None:
        strategy = MLReturnPredictionStrategy(model_name="test_model")
        universe = [_make_snapshot("A")]
        signals = strategy.generate_cross_sectional_signals(universe, [], datetime(2025, 6, 1))
        assert signals == []

    def test_top_n_buy_signals(self) -> None:
        strategy = MLReturnPredictionStrategy(model_name="test_model", top_n=2)
        fake_engine = FakeInferenceEngine(predictions={"A": 0.8, "B": 0.6, "C": 0.4})
        strategy.set_inference_engine(fake_engine)

        universe = [_make_snapshot("A"), _make_snapshot("B"), _make_snapshot("C")]
        signals = strategy.generate_cross_sectional_signals(universe, [], datetime(2025, 6, 1))

        buy_signals = [s for s in signals if s.direction == SignalDirection.BUY]
        assert len(buy_signals) == 2
        buy_symbols = {s.symbol for s in buy_signals}
        assert "A" in buy_symbols
        assert "B" in buy_symbols

    def test_sell_dropped_positions(self) -> None:
        strategy = MLReturnPredictionStrategy(model_name="test_model", top_n=1)
        fake_engine = FakeInferenceEngine(predictions={"A": 0.8, "B": 0.6})
        strategy.set_inference_engine(fake_engine)

        universe = [_make_snapshot("A"), _make_snapshot("B")]
        positions = [_make_position("B")]
        signals = strategy.generate_cross_sectional_signals(universe, positions, datetime(2025, 6, 1))

        sell_signals = [s for s in signals if s.direction == SignalDirection.SELL]
        assert len(sell_signals) == 1
        assert sell_signals[0].symbol == "B"

    def test_min_score_filters_low_predictions(self) -> None:
        strategy = MLReturnPredictionStrategy(model_name="test", top_n=3, min_score=0.5)
        fake_engine = FakeInferenceEngine(predictions={"A": 0.8, "B": 0.3, "C": 0.6})
        strategy.set_inference_engine(fake_engine)

        universe = [_make_snapshot("A"), _make_snapshot("B"), _make_snapshot("C")]
        signals = strategy.generate_cross_sectional_signals(universe, [], datetime(2025, 6, 1))

        buy_signals = [s for s in signals if s.direction == SignalDirection.BUY]
        buy_symbols = {s.symbol for s in buy_signals}
        assert "B" not in buy_symbols
        assert "A" in buy_symbols
        assert "C" in buy_symbols
