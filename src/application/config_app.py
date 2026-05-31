"""配置应用服务。

集成配置文件监听和热更新，可注册到 AutoTradingEngine 等上层组件。
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.domain.common.value_objects.config_change_log import ConfigChangeLog
from src.infrastructure.config.config_hot_reload import ConfigHotReloadService
from src.infrastructure.config.config_watcher import ConfigWatcher

logger = logging.getLogger(__name__)


class ConfigAppService:
    """配置应用服务。

    职责:
    - 启动/停止配置文件监听
    - 代理热更新操作（update_param / rollback / reload）
    - 提供变更历史查询

    Args:
        config_path: YAML 配置文件路径。
        settings: 运行时 AppSettings 实例。
        on_change: 配置变更后的可选回调（如通知 AutoTradingEngine 刷新参数）。
    """

    def __init__(
        self,
        config_path: str,
        settings: Any,
        on_change: Callable[[list[ConfigChangeLog]], None] | None = None,
    ) -> None:
        self._config_path = config_path
        self._hot_reload = ConfigHotReloadService(
            config_path=config_path,
            settings=settings,
            on_change=on_change,
        )
        self._watcher: ConfigWatcher | None = None

    @property
    def is_watching(self) -> bool:
        return self._watcher is not None and self._watcher.is_running

    @property
    def change_history(self) -> list[ConfigChangeLog]:
        return self._hot_reload.change_history

    def start_watching(self) -> None:
        """启动配置文件监听。"""
        if self.is_watching:
            return
        watch_dir = Path(self._config_path).parent
        self._watcher = ConfigWatcher(
            watch_dir=watch_dir,
            callback=self._on_file_changed,
        )
        self._watcher.start()
        logger.info("配置文件监听已启动")

    def stop_watching(self) -> None:
        """停止配置文件监听。"""
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None

    def take_snapshot(self) -> None:
        """保存当前配置快照。"""
        self._hot_reload.take_snapshot()

    def reload(self) -> list[ConfigChangeLog]:
        """从文件重新加载配置。"""
        return self._hot_reload.reload_from_file()

    def update_param(self, config_path: str, new_value: Any, *, user_id: str = "api") -> ConfigChangeLog:
        """动态更新单个参数。

        Args:
            config_path: 点分路径（如 "costs.commission_rate"）。
            new_value: 新值。
            user_id: 操作者标识。

        Returns:
            变更日志。
        """
        return self._hot_reload.update_param(config_path, new_value, user_id=user_id)

    def rollback(self) -> bool:
        """回滚到上一次快照。"""
        return self._hot_reload.rollback()

    def _on_file_changed(self, file_path: Path) -> None:
        """文件变更回调。"""
        logger.info("配置文件变更，重新加载: %s", file_path)
        self._hot_reload.reload_from_file()
