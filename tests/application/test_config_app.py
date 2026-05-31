"""ConfigAppService 测试。"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from src.application.config_app import ConfigAppService
from src.infrastructure.config.settings import AppSettings, CostsSettings


def _make_settings() -> AppSettings:
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


class TestConfigAppService:
    def test_update_param(self):
        """代理 update_param 调用。"""
        settings = _make_settings()
        svc = ConfigAppService(config_path="dummy.yaml", settings=settings)

        change = svc.update_param("costs.commission_rate", 0.001, user_id="api_user")

        assert settings.costs.commission_rate == 0.001
        assert change.user_id == "api_user"

    def test_change_history(self):
        """变更历史查询。"""
        settings = _make_settings()
        svc = ConfigAppService(config_path="dummy.yaml", settings=settings)

        svc.update_param("costs.commission_rate", 0.001)
        svc.update_param("costs.tax_rate", 0.002)

        assert len(svc.change_history) == 2

    def test_snapshot_and_rollback(self):
        """快照与回滚。"""
        settings = _make_settings()
        svc = ConfigAppService(config_path="dummy.yaml", settings=settings)

        svc.take_snapshot()
        svc.update_param("costs.commission_rate", 0.999)
        assert settings.costs.commission_rate == 0.999

        result = svc.rollback()
        assert result is True
        assert settings.costs.commission_rate == 0.00025

    def test_reload_from_file(self):
        """从文件重新加载。"""
        settings = _make_settings()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            yaml.dump({"costs": {"commission_rate": 0.0008}}, f, allow_unicode=True)
            config_path = f.name

        svc = ConfigAppService(config_path=config_path, settings=settings)
        changes = svc.reload()

        assert settings.costs.commission_rate == 0.0008
        assert len(changes) >= 1

        Path(config_path).unlink()

    def test_is_watching_false_by_default(self):
        """默认未在监听。"""
        settings = _make_settings()
        svc = ConfigAppService(config_path="dummy.yaml", settings=settings)
        assert svc.is_watching is False

    def test_blocked_path_raises(self):
        """敏感路径更新应抛出异常。"""
        settings = _make_settings()
        svc = ConfigAppService(config_path="dummy.yaml", settings=settings)

        try:
            svc.update_param("qmt.session_id", 999)
            assert False, "应抛出 PermissionError"
        except PermissionError:
            pass

    def test_on_change_callback(self):
        """配置变更时触发回调。"""
        callback = MagicMock()
        settings = _make_settings()
        svc = ConfigAppService(
            config_path="dummy.yaml",
            settings=settings,
            on_change=callback,
        )

        svc.update_param("costs.commission_rate", 0.001)
        callback.assert_called_once()

    def test_start_and_stop_watching(self):
        """启动和停止文件监听。"""
        settings = _make_settings()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            _write_yaml(config_path, {"costs": {"commission_rate": 0.00025}})

            svc = ConfigAppService(config_path=str(config_path), settings=settings)
            svc.start_watching()
            assert svc.is_watching is True

            svc.stop_watching()
            assert svc.is_watching is False

    def test_start_watching_nonexistent_dir(self):
        """目录不存在时不影响启动（不崩溃）。"""
        settings = _make_settings()
        svc = ConfigAppService(config_path="/nonexistent/dir/config.yaml", settings=settings)
        svc.start_watching()
        # 应该不崩溃，只是记录错误
        assert svc.is_watching is False
