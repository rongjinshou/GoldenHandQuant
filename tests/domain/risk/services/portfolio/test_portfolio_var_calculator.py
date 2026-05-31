from src.domain.risk.services.portfolio.portfolio_var_calculator import PortfolioVaRCalculator


class TestPortfolioVaRCalculator:
    def setup_method(self):
        self.calc = PortfolioVaRCalculator()

    def test_percentile_basic(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert self.calc._percentile(data, 0.5) == 3.0

    def test_percentile_95th(self):
        data = list(range(100))
        result = self.calc._percentile(data, 0.05)
        assert 4 < result < 6

    def test_percentile_extremes(self):
        data = [1.0, 2.0, 3.0]
        assert self.calc._percentile(data, 0.0) == 1.0

    def test_z_score_table(self):
        assert self.calc._z_score(0.95) == 1.645
        assert self.calc._z_score(0.99) == 2.326
        assert self.calc._z_score(0.90) == 1.282
        assert self.calc._z_score(0.50) == 1.645  # default

    def test_historical_var_basic(self):
        returns = [-0.02, -0.01, 0.01, 0.02, -0.03, 0.01, -0.01, 0.02, 0.01, -0.02]
        result = self.calc.calculate_historical_var(returns, 100000, 0.95, 1)
        assert result.var_absolute > 0
        assert result.var_percentage > 0
        assert result.cvar >= result.var_percentage  # CVaR >= VaR
        assert result.method == "historical"
        assert result.confidence_level == 0.95

    def test_historical_var_holding_period(self):
        returns = [-0.02, -0.01, 0.01, 0.02, -0.03, 0.01, -0.01, 0.02, 0.01, -0.02]
        r1 = self.calc.calculate_historical_var(returns, 100000, 0.95, 1)
        r5 = self.calc.calculate_historical_var(returns, 100000, 0.95, 5)
        # sqrt(5) rule
        assert abs(r5.var_percentage / r1.var_percentage - 5**0.5) < 0.1

    def test_parametric_var_basic(self):
        returns = [-0.02, -0.01, 0.01, 0.02, -0.03, 0.01, -0.01, 0.02, 0.01, -0.02]
        result = self.calc.calculate_parametric_var(returns, 100000, 0.95, 1)
        assert result.var_absolute > 0
        assert result.method == "parametric"
        assert result.cvar >= result.var_percentage

    def test_portfolio_returns(self):
        sr = {"A": [0.01, 0.02, -0.01], "B": [0.02, -0.01, 0.03]}
        w = {"A": 0.6, "B": 0.4}
        result = self.calc.calculate_portfolio_returns(sr, w)
        assert len(result) == 3
        assert abs(result[0] - (0.6 * 0.01 + 0.4 * 0.02)) < 1e-10
        assert abs(result[1] - (0.6 * 0.02 + 0.4 * -0.01)) < 1e-10

    def test_empty_returns(self):
        result = self.calc.calculate_historical_var([], 100000, 0.95, 1)
        assert result.var_absolute == 0.0

    def test_cvar_gte_var(self):
        """CVaR should always be >= VaR (mathematical property)."""
        returns = [-0.05, -0.03, -0.02, -0.01, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
        r95 = self.calc.calculate_historical_var(returns, 100000, 0.95, 1)
        r99 = self.calc.calculate_historical_var(returns, 100000, 0.99, 1)
        assert r95.cvar >= r95.var_percentage
        assert r99.cvar >= r99.var_percentage
