import numpy as np
from unittest.mock import MagicMock
from src.infrastructure.ml_engine.inference import InferenceEngine


def test_predict_returns_probability():
    mock_model = MagicMock()
    mock_model.predict_proba.return_value = np.array([[0.3, 0.7]])

    loader = MagicMock()
    loader.load_catboost.return_value = mock_model

    engine = InferenceEngine(loader)
    result = engine.predict("test_model", np.array([[0.1, 0.2, 0.3, 0.4, 0.5]]))
    assert 0 <= result[0] <= 1
    assert abs(result[0] - 0.7) < 0.01


def test_predict_batch_returns_symbol_map():
    mock_model = MagicMock()
    mock_model.predict_proba.return_value = np.array([[0.4, 0.6]])

    loader = MagicMock()
    loader.load_catboost.return_value = mock_model

    engine = InferenceEngine(loader)
    features = {
        "000001.SZ": np.array([[0.1, 0.2, 0.3, 0.4, 0.5]]),
        "000002.SZ": np.array([[0.2, 0.3, 0.4, 0.5, 0.6]]),
    }
    results = engine.predict_batch("test_model", features)
    assert len(results) == 2
    assert "000001.SZ" in results
    assert all(0 <= v <= 1 for v in results.values())
