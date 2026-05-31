from datetime import datetime

from src.domain.risk.value_objects.ml_risk_alert import MLRiskAlert


class MLModelRiskMonitor:
    """ML 模型风险监控器。"""

    def check_overfitting(
        self,
        strategy_name: str,
        train_metrics: dict[str, float],
        test_metrics: dict[str, float],
    ) -> list[MLRiskAlert]:
        """检测过拟合风险。

        比较训练集和测试集的关键指标（IC、夏普、胜率），
        若衰减超过阈值则生成告警。
        """
        alerts: list[MLRiskAlert] = []
        now = datetime.now()

        # IC 衰减率 > 50%
        train_ic = train_metrics.get("ic", 0.0)
        test_ic = test_metrics.get("ic", 0.0)
        if train_ic > 0:
            ic_decay = (train_ic - test_ic) / train_ic
            if ic_decay > 0.5:
                alerts.append(MLRiskAlert(
                    strategy_name=strategy_name,
                    alert_type="overfitting",
                    severity="critical" if ic_decay > 0.7 else "warning",
                    metric_name="ic_decay_rate",
                    metric_value=ic_decay,
                    threshold=0.5,
                    description=f"IC 衰减率 {ic_decay:.0%} 超过阈值 50%",
                    detected_at=now,
                ))

        # 夏普衰减率 > 40%
        train_sharpe = train_metrics.get("sharpe", 0.0)
        test_sharpe = test_metrics.get("sharpe", 0.0)
        if train_sharpe > 0:
            sharpe_decay = (train_sharpe - test_sharpe) / train_sharpe
            if sharpe_decay > 0.4:
                alerts.append(MLRiskAlert(
                    strategy_name=strategy_name,
                    alert_type="overfitting",
                    severity="critical" if sharpe_decay > 0.6 else "warning",
                    metric_name="sharpe_decay_rate",
                    metric_value=sharpe_decay,
                    threshold=0.4,
                    description=f"夏普衰减率 {sharpe_decay:.0%} 超过阈值 40%",
                    detected_at=now,
                ))

        # 胜率衰减 > 15%
        train_wr = train_metrics.get("win_rate", 0.0)
        test_wr = test_metrics.get("win_rate", 0.0)
        wr_decay = train_wr - test_wr
        if wr_decay > 0.15:
            alerts.append(MLRiskAlert(
                strategy_name=strategy_name,
                alert_type="overfitting",
                severity="critical" if wr_decay > 0.25 else "warning",
                metric_name="win_rate_decay",
                metric_value=wr_decay,
                threshold=0.15,
                description=f"胜率衰减 {wr_decay:.0%} 超过阈值 15%",
                detected_at=now,
            ))

        return alerts

    def check_feature_drift(
        self,
        strategy_name: str,
        feature_name: str,
        train_mean: float,
        train_std: float,
        online_mean: float,
        online_std: float,
    ) -> MLRiskAlert | None:
        """检测单个特征的分布漂移。"""
        now = datetime.now()

        if train_std == 0:
            return None

        mean_shift = abs(online_mean - train_mean) / train_std
        variance_ratio = online_std / train_std if train_std > 0 else 1.0

        # 均值偏移检测
        severity = "warning"
        if mean_shift > 2.0:
            severity = "critical"
            return MLRiskAlert(
                strategy_name=strategy_name,
                alert_type="feature_drift",
                severity=severity,
                metric_name=f"{feature_name}_mean_shift",
                metric_value=mean_shift,
                threshold=2.0,
                description=f"特征 {feature_name} 均值偏移 {mean_shift:.2f}，超过严重阈值 2.0",
                detected_at=now,
            )
        if mean_shift > 1.0:
            return MLRiskAlert(
                strategy_name=strategy_name,
                alert_type="feature_drift",
                severity="warning",
                metric_name=f"{feature_name}_mean_shift",
                metric_value=mean_shift,
                threshold=1.0,
                description=f"特征 {feature_name} 均值偏移 {mean_shift:.2f}，超过阈值 1.0",
                detected_at=now,
            )

        # 方差比检测
        if variance_ratio < 0.3 or variance_ratio > 3.0:
            severity = "critical"
        elif variance_ratio < 0.5 or variance_ratio > 2.0:
            severity = "warning"
        else:
            return None

        return MLRiskAlert(
            strategy_name=strategy_name,
            alert_type="feature_drift",
            severity=severity,
            metric_name=f"{feature_name}_variance_ratio",
            metric_value=variance_ratio,
            threshold=0.5 if variance_ratio < 1.0 else 2.0,
            description=f"特征 {feature_name} 方差比 {variance_ratio:.2f}，分布发生漂移",
            detected_at=now,
        )

    def check_performance_degradation(
        self,
        strategy_name: str,
        rolling_sharpe: list[float],
        rolling_win_rate: list[float],
        consecutive_loss_days: int,
    ) -> list[MLRiskAlert]:
        """检测策略表现退化。"""
        alerts: list[MLRiskAlert] = []
        now = datetime.now()

        # 滚动夏普 z-score < -2
        if len(rolling_sharpe) >= 10:
            mean_s = sum(rolling_sharpe) / len(rolling_sharpe)
            var_s = sum((s - mean_s) ** 2 for s in rolling_sharpe) / len(rolling_sharpe)
            std_s = var_s**0.5
            if std_s > 0:
                current = rolling_sharpe[-1]
                z = (current - mean_s) / std_s
                if z < -2:
                    alerts.append(MLRiskAlert(
                        strategy_name=strategy_name,
                        alert_type="performance_degradation",
                        severity="critical" if z < -3 else "warning",
                        metric_name="rolling_sharpe_zscore",
                        metric_value=z,
                        threshold=-2.0,
                        description=f"滚动夏普 z-score {z:.2f} 低于阈值 -2",
                        detected_at=now,
                    ))

        # 滚动胜率 z-score < -2
        if len(rolling_win_rate) >= 10:
            mean_w = sum(rolling_win_rate) / len(rolling_win_rate)
            var_w = sum((w - mean_w) ** 2 for w in rolling_win_rate) / len(rolling_win_rate)
            std_w = var_w**0.5
            if std_w > 0:
                current = rolling_win_rate[-1]
                z = (current - mean_w) / std_w
                if z < -2:
                    alerts.append(MLRiskAlert(
                        strategy_name=strategy_name,
                        alert_type="performance_degradation",
                        severity="critical" if z < -3 else "warning",
                        metric_name="rolling_win_rate_zscore",
                        metric_value=z,
                        threshold=-2.0,
                        description=f"滚动胜率 z-score {z:.2f} 低于阈值 -2",
                        detected_at=now,
                    ))

        # 连续亏损天数 >= 5
        if consecutive_loss_days >= 5:
            alerts.append(MLRiskAlert(
                strategy_name=strategy_name,
                alert_type="performance_degradation",
                severity="critical" if consecutive_loss_days >= 10 else "warning",
                metric_name="consecutive_loss_days",
                metric_value=float(consecutive_loss_days),
                threshold=5.0,
                description=f"连续亏损 {consecutive_loss_days} 天，超过阈值 5 天",
                detected_at=now,
            ))

        return alerts
