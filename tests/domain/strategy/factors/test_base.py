from src.domain.strategy.factors.base import FactorScorer


class TestFactorScorer:
    def test_percentile_rank_basic(self):
        raw = {"A": 10.0, "B": 20.0, "C": 30.0, "D": 40.0}
        scores = FactorScorer.percentile_rank(raw)
        assert scores["A"] == 0.0
        assert scores["D"] == 1.0
        assert 0.0 < scores["B"] < 1.0

    def test_percentile_rank_same_values(self):
        raw = {"A": 10.0, "B": 10.0, "C": 10.0}
        scores = FactorScorer.percentile_rank(raw)
        for v in scores.values():
            assert v == 0.5

    def test_percentile_rank_single(self):
        raw = {"A": 42.0}
        scores = FactorScorer.percentile_rank(raw)
        assert scores["A"] == 0.5

    def test_percentile_rank_empty(self):
        scores = FactorScorer.percentile_rank({})
        assert scores == {}

    def test_percentile_rank_inverted(self):
        raw = {"A": 10.0, "B": 20.0, "C": 30.0}
        scores = FactorScorer.percentile_rank(raw, invert=True)
        assert scores["A"] == 1.0
        assert scores["C"] == 0.0

    def test_weighted_combine(self):
        scores_a = {"A": 0.8, "B": 0.4, "C": 0.6}
        scores_b = {"A": 0.2, "B": 0.6, "C": 0.4}
        combined = FactorScorer.weighted_combine([scores_a, scores_b], [0.6, 0.4])
        assert abs(combined["A"] - 0.56) < 1e-6
        assert abs(combined["B"] - 0.48) < 1e-6
        assert abs(combined["C"] - 0.52) < 1e-6

    def test_weighted_combine_empty(self):
        combined = FactorScorer.weighted_combine([], [])
        assert combined == {}

    def test_weighted_combine_missing_symbol(self):
        scores_a = {"A": 0.8, "B": 0.4}
        scores_b = {"A": 0.6}
        combined = FactorScorer.weighted_combine([scores_a, scores_b], [0.5, 0.5])
        assert "A" in combined
        assert "B" not in combined

    def test_rank_top_n(self):
        scores = {"A": 0.9, "B": 0.3, "C": 0.7, "D": 0.5, "E": 0.1}
        top = FactorScorer.rank_top_n(scores, 3)
        assert top == ["A", "C", "D"]

    def test_rank_top_n_more_than_available(self):
        scores = {"A": 0.5, "B": 0.3}
        top = FactorScorer.rank_top_n(scores, 10)
        assert top == ["A", "B"]
