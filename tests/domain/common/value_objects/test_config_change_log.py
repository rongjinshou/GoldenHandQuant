"""ConfigChangeLog 值对象测试。"""

from datetime import UTC, datetime

from src.domain.common.value_objects.config_change_log import ConfigChangeLog


class TestConfigChangeLog:
    def test_create_with_defaults(self):
        """应自动生成 change_id 和 timestamp。"""
        log = ConfigChangeLog(
            config_path="costs.commission_rate",
            old_value=0.00025,
            new_value=0.0003,
        )
        assert log.change_id  # 非空
        assert log.config_path == "costs.commission_rate"
        assert log.old_value == 0.00025
        assert log.new_value == 0.0003
        assert log.user_id == "system"
        assert isinstance(log.timestamp, datetime)

    def test_create_with_explicit_values(self):
        """所有字段可显式指定。"""
        ts = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        log = ConfigChangeLog(
            change_id="custom-id",
            config_path="risk.stop_loss.max_loss_ratio",
            old_value=0.03,
            new_value=0.05,
            timestamp=ts,
            user_id="admin",
        )
        assert log.change_id == "custom-id"
        assert log.user_id == "admin"
        assert log.timestamp == ts

    def test_frozen_immutable(self):
        """值对象不可变。"""
        log = ConfigChangeLog(
            config_path="test.path",
            old_value=1,
            new_value=2,
        )
        try:
            log.new_value = 3  # type: ignore[misc]
            assert False, "应抛出 FrozenInstanceError"
        except AttributeError:
            pass

    def test_different_instances_have_unique_ids(self):
        """不同实例的 change_id 不同。"""
        log1 = ConfigChangeLog(config_path="a.b", old_value=1, new_value=2)
        log2 = ConfigChangeLog(config_path="a.b", old_value=1, new_value=3)
        assert log1.change_id != log2.change_id

    def test_none_values_allowed(self):
        """old_value 和 new_value 支持 None。"""
        log = ConfigChangeLog(
            config_path="some.path",
            old_value=None,
            new_value=42,
        )
        assert log.old_value is None
        assert log.new_value == 42
