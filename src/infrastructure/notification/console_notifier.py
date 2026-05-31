from src.domain.risk.value_objects.risk_event import RiskEvent, RiskSeverity


class ConsoleNotifier:
    """终端通知实现。"""

    _SEVERITY_COLORS = {
        RiskSeverity.INFO: "\033[94m",
        RiskSeverity.WARNING: "\033[93m",
        RiskSeverity.CRITICAL: "\033[91m",
    }
    _RESET = "\033[0m"

    def notify(self, event: RiskEvent) -> None:
        color = self._SEVERITY_COLORS.get(event.severity, "")
        print(f"{color}[RISK {event.severity}] {event.message}{self._RESET}")
