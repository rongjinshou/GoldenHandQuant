"""通知优先级枚举测试。"""

from src.domain.notification.value_objects.notification_priority import (
    NotificationPriority,
)


class TestNotificationPriority:
    """NotificationPriority 枚举测试。"""

    def test_emergency_value(self):
        assert NotificationPriority.EMERGENCY == "emergency"

    def test_critical_value(self):
        assert NotificationPriority.CRITICAL == "critical"

    def test_warning_value(self):
        assert NotificationPriority.WARNING == "warning"

    def test_info_value(self):
        assert NotificationPriority.INFO == "info"

    def test_from_string(self):
        assert NotificationPriority("emergency") is NotificationPriority.EMERGENCY
        assert NotificationPriority("critical") is NotificationPriority.CRITICAL
        assert NotificationPriority("warning") is NotificationPriority.WARNING
        assert NotificationPriority("info") is NotificationPriority.INFO

    def test_all_members(self):
        members = list(NotificationPriority)
        assert len(members) == 4
