"""ConfigHotReloadService 测试。"""

import tempfile
from pathlib import Path

import yaml  # noqa: I001

from src.infrastructure.config.config_hot_reload import (
    ConfigHotReloadService,
    _get_nested,
    _is_blocked,
    _set_nested,
)
from src.infrastructure.config.settings import AppSettings, CostsSettings

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    def test_get_nested_simple(self):
        data = {"a": {"b": {"c": 42}}}
        assert _get_nested(data, "a.b.c") == 42

    def test_get_nested_missing_key(self):
        data = {"a": {"b": 1}}
        assert _get_nested(data, "a.x") is None

    def test_get_nested_intermediate_not_dict(self):
        data = {"a": 5}
        assert _get_nested(data, "a.b") is None

    def test_set_nested_simple(self):
        data: dict = {"a": {"b": 1}}
        _set_nested(data, "a.b", 99)
        assert data["a"]["b"] == 99

    def test_set_nested_create_intermediate(self):
        data: dict = {"a": {}}
        _set_nested(data, "a.b.c", 7)
        assert data["a"]["b"]["c"] == 7

    def test_is_blocked_qmt(self):
        assert _is_blocked("qmt")
        assert _is_blocked("qmt.userdata_path")
        assert not _is_blocked("qmt_extra")

    def test_is_blocked_tushare_token(self):
        assert _is_blocked("data.tushare.token")
        assert _is_blocked("data.tushare")

    def test_is_blocked_cache_dir(self):
        assert _is_blocked("data.cache_dir")

    def test_is_not_blocked_normal_paths(self):
        assert not _is_blocked("costs.commission_rate")
        assert not _is_blocked("risk.stop_loss.max_loss_ratio")
        assert not _is_blocked("auto_trade.min_confidence")


# ---------------------------------------------------------------------------
# ConfigHotReloadService
# ---------------------------------------------------------------------------

def _make_settings() -> AppSettings:
    """创建测试用 AppSettings。"""
    return AppSettings(
        costs=CostsSettings(
            commission_rate=0.00025,
            tax_rate=0.001,
            min_commission=5.0,
            slippage=0.001,
        ),
    )


def _write_yaml(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)


class TestConfigHotReloadService:
    def test_update_param_success(self):
        """正常更新参数并记录变更日志。"""
        settings = _make_settings()
        svc = ConfigHotReloadService(config_path="dummy.yaml", settings=settings)

        change = svc.update_param("costs.commission_rate", 0.0003, user_id="test_user")

        assert settings.costs.commission_rate == 0.0003
        assert change.config_path == "costs.commission_rate"
        assert change.old_value == 0.00025
        assert change.new_value == 0.0003
        assert change.user_id == "test_user"
        assert len(svc.change_history) == 1

    def test_update_param_blocked_path_raises(self):
        """敏感路径不允许热更新。"""
        settings = _make_settings()
        svc = ConfigHotReloadService(config_path="dummy.yaml", settings=settings)

        try:
            svc.update_param("qmt.session_id", 999)
            assert False, "应抛出 PermissionError"
        except PermissionError as e:
            assert "不支持热更新" in str(e)

    def test_update_param_blocked_tushare(self):
        """Tushare token 不允许热更新。"""
        settings = _make_settings()
        svc = ConfigHotReloadService(config_path="dummy.yaml", settings=settings)

        try:
            svc.update_param("data.tushare.token", "new_token")
            assert False, "应抛出 PermissionError"
        except PermissionError:
            pass

    def test_update_param_nonexistent_path_raises(self):
        """不存在的路径应抛 KeyError。"""
        settings = _make_settings()
        svc = ConfigHotReloadService(config_path="dummy.yaml", settings=settings)

        try:
            svc.update_param("nonexistent.path", 123)
            assert False, "应抛出 KeyError"
        except KeyError:
            pass

    def test_rollback_success(self):
        """回滚到快照。"""
        settings = _make_settings()
        svc = ConfigHotReloadService(config_path="dummy.yaml", settings=settings)
        svc.take_snapshot()

        svc.update_param("costs.commission_rate", 0.001)
        assert settings.costs.commission_rate == 0.001

        result = svc.rollback()
        assert result is True
        assert settings.costs.commission_rate == 0.00025

    def test_rollback_no_snapshot(self):
        """无快照时回滚返回 False。"""
        settings = _make_settings()
        svc = ConfigHotReloadService(config_path="dummy.yaml", settings=settings)

        assert svc.rollback() is False

    def test_reload_from_file(self):
        """从 YAML 文件重新加载配置。"""
        settings = _make_settings()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            yaml.dump({"costs": {"commission_rate": 0.0005}}, f, allow_unicode=True)
            config_path = f.name

        svc = ConfigHotReloadService(config_path=config_path, settings=settings)
        changes = svc.reload_from_file()

        assert settings.costs.commission_rate == 0.0005
        assert len(changes) >= 1

        # 清理
        Path(config_path).unlink()

    def test_reload_from_nonexistent_file(self):
        """文件不存在时返回空列表。"""
        settings = _make_settings()
        svc = ConfigHotReloadService(config_path="/nonexistent/path.yaml", settings=settings)

        changes = svc.reload_from_file()
        assert changes == []

    def test_change_history_accumulates(self):
        """变更历史持续累积。"""
        settings = _make_settings()
        svc = ConfigHotReloadService(config_path="dummy.yaml", settings=settings)

        svc.update_param("costs.commission_rate", 0.001)
        svc.update_param("costs.tax_rate", 0.002)

        history = svc.change_history
        assert len(history) == 2
        assert history[0].config_path == "costs.commission_rate"
        assert history[1].config_path == "costs.tax_rate"

    def test_on_change_callback_invoked(self):
        """参数更新时触发回调。"""
        callback_calls: list = []
        settings = _make_settings()
        svc = ConfigHotReloadService(
            config_path="dummy.yaml",
            settings=settings,
            on_change=lambda changes: callback_calls.extend(changes),
        )

        svc.update_param("costs.commission_rate", 0.001)
        assert len(callback_calls) == 1
        assert callback_calls[0].config_path == "costs.commission_rate"
