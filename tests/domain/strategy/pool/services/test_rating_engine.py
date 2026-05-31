import pytest
from datetime import datetime

from src.domain.strategy.pool.services.rating_engine import RatingEngine
from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating


class TestCalculateScore:
    def setup_method(self):
        self.engine = RatingEngine()

    def test_high_sharpe_low_drawdown_high_winrate(self):
        # sharpe=2.0 -> risk=100, dd=0.10 -> drawdown=66.7, win=0.60 -> consistency=60
        # score = 0.4*100 + 0.3*66.7 + 0.3*60 = 40 + 20 + 18 = 78
        score = self.engine.calculate_score(
            sharpe_ratio=2.0, max_drawdown=0.10, win_rate=0.60
        )
        assert score >= 78  # A-level territory with no penalty

    def test_low_sharpe_high_drawdown_low_winrate(self):
        score = self.engine.calculate_score(
            sharpe_ratio=0.5, max_drawdown=0.25, win_rate=0.40
        )
        assert score < 40  # D-level

    def test_zero_sharpe(self):
        score = self.engine.calculate_score(
            sharpe_ratio=0.0, max_drawdown=0.0, win_rate=0.50
        )
        assert score == pytest.approx(0.40 * 0 + 0.30 * 100 + 0.30 * 50, abs=0.1)

    def test_max_drawdown_at_limit(self):
        score = self.engine.calculate_score(
            sharpe_ratio=1.0, max_drawdown=0.30, win_rate=0.50
        )
        # drawdown score = 0
        expected = 0.40 * 50 + 0.30 * 0 + 0.30 * 50
        assert score == pytest.approx(expected, abs=0.1)

    def test_underperform_penalty(self):
        score_no_penalty = self.engine.calculate_score(
            1.5, 0.15, 0.55, underperform_weeks=0
        )
        score_with_penalty = self.engine.calculate_score(
            1.5, 0.15, 0.55, underperform_weeks=4
        )
        assert score_no_penalty - score_with_penalty == pytest.approx(20)

    def test_score_clamped_at_0(self):
        score = self.engine.calculate_score(
            0.0, 0.50, 0.0, underperform_weeks=100
        )
        assert score == 0.0

    def test_score_clamped_at_100(self):
        score = self.engine.calculate_score(
            5.0, 0.0, 1.0, underperform_weeks=0
        )
        assert score == 100.0


class TestCalculateRating:
    def setup_method(self):
        self.engine = RatingEngine()

    def test_a_rating(self):
        assert self.engine.calculate_rating(80) == StrategyRating.A
        assert self.engine.calculate_rating(100) == StrategyRating.A

    def test_b_rating(self):
        assert self.engine.calculate_rating(60) == StrategyRating.B
        assert self.engine.calculate_rating(79) == StrategyRating.B

    def test_c_rating(self):
        assert self.engine.calculate_rating(40) == StrategyRating.C
        assert self.engine.calculate_rating(59) == StrategyRating.C

    def test_d_rating(self):
        assert self.engine.calculate_rating(0) == StrategyRating.D
        assert self.engine.calculate_rating(39) == StrategyRating.D
