from src.domain.risk.services.portfolio.ml_model_risk_monitor import MLModelRiskMonitor


class TestMLModelRiskMonitor:
    def setup_method(self):
        self.monitor = MLModelRiskMonitor()

    def test_overfitting_ic_decay(self):
        train = {"ic": 0.08, "sharpe": 2.0, "win_rate": 0.65}
        test = {"ic": 0.03, "sharpe": 1.5, "win_rate": 0.55}
        alerts = self.monitor.check_overfitting("strat_A", train, test)
        ic_alerts = [a for a in alerts if a.metric_name == "ic_decay_rate"]
        assert len(ic_alerts) == 1
        assert ic_alerts[0].alert_type == "overfitting"

    def test_overfitting_no_alert(self):
        train = {"ic": 0.08, "sharpe": 2.0, "win_rate": 0.65}
        test = {"ic": 0.07, "sharpe": 1.8, "win_rate": 0.60}
        alerts = self.monitor.check_overfitting("strat_A", train, test)
        assert len(alerts) == 0

    def test_overfitting_multiple_alerts(self):
        train = {"ic": 0.10, "sharpe": 3.0, "win_rate": 0.70}
        test = {"ic": 0.02, "sharpe": 0.5, "win_rate": 0.40}
        alerts = self.monitor.check_overfitting("strat_A", train, test)
        assert len(alerts) == 3  # IC, sharpe, win_rate all triggered

    def test_feature_drift_mean_shift_warning(self):
        alert = self.monitor.check_feature_drift(
            "strat_A", "momentum", 0.0, 1.0, 1.5, 1.0
        )
        assert alert is not None
        assert alert.alert_type == "feature_drift"
        assert alert.severity == "warning"

    def test_feature_drift_mean_shift_critical(self):
        alert = self.monitor.check_feature_drift(
            "strat_A", "momentum", 0.0, 1.0, 2.5, 1.0
        )
        assert alert is not None
        assert alert.severity == "critical"

    def test_feature_drift_variance_ratio(self):
        alert = self.monitor.check_feature_drift(
            "strat_A", "momentum", 0.0, 1.0, 0.1, 0.3
        )
        assert alert is not None
        assert "variance_ratio" in alert.metric_name

    def test_feature_drift_no_alert(self):
        alert = self.monitor.check_feature_drift(
            "strat_A", "momentum", 0.0, 1.0, 0.2, 1.0
        )
        assert alert is None

    def test_feature_drift_zero_std(self):
        alert = self.monitor.check_feature_drift(
            "strat_A", "momentum", 0.0, 0.0, 0.0, 1.0
        )
        assert alert is None

    def test_performance_degradation_sharpe(self):
        rolling_sharpe = [1.0, 1.2, 0.8, 1.1, 0.9, 1.0, 1.1, 0.9, 1.0, 0.8, -3.0]
        alerts = self.monitor.check_performance_degradation(
            "strat_A", rolling_sharpe, [], 0
        )
        sharpe_alerts = [a for a in alerts if a.metric_name == "rolling_sharpe_zscore"]
        assert len(sharpe_alerts) == 1

    def test_performance_degradation_consecutive_loss(self):
        alerts = self.monitor.check_performance_degradation(
            "strat_A", [], [], 7
        )
        loss_alerts = [a for a in alerts if a.metric_name == "consecutive_loss_days"]
        assert len(loss_alerts) == 1
        assert loss_alerts[0].severity == "warning"

    def test_performance_degradation_consecutive_loss_critical(self):
        alerts = self.monitor.check_performance_degradation(
            "strat_A", [], [], 12
        )
        loss_alerts = [a for a in alerts if a.metric_name == "consecutive_loss_days"]
        assert loss_alerts[0].severity == "critical"

    def test_performance_no_degradation(self):
        rolling_sharpe = [1.0, 1.1, 0.9, 1.0, 1.1, 0.9, 1.0, 1.1, 0.9, 1.0]
        alerts = self.monitor.check_performance_degradation(
            "strat_A", rolling_sharpe, [], 2
        )
        assert len(alerts) == 0
