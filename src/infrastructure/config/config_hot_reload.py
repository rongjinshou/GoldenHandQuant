"""配置热更新服务。

运行时动态调整参数，支持参数变更审计日志和变更回滚。
"""

import logging
from collections.abc import Callable
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any

import yaml

from src.domain.common.value_objects.config_change_log import ConfigChangeLog

logger = logging.getLogger(__name__)

# 不支持热更新的敏感配置路径前缀
BLOCKED_PATHS: frozenset[str] = frozenset({
    "qmt",
    "data.tushare",
    "data.cache_dir",
})


def _get_nested(data: dict[str, Any], dotpath: str) -> Any:
    """从嵌套字典中按点分路径取值。"""
    keys = dotpath.split(".")
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _set_nested(data: dict[str, Any], dotpath: str, value: Any) -> None:
    """在嵌套字典中按点分路径设值。"""
    keys = dotpath.split(".")
    current: Any = data
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def _is_blocked(config_path: str) -> bool:
    """检查配置路径是否被阻止热更新。"""
    for blocked in BLOCKED_PATHS:
        if config_path == blocked or config_path.startswith(blocked + "."):
            return True
    return False


def _dataclass_to_dict(obj: object) -> dict[str, Any]:
    """递归将 dataclass 转换为嵌套字典。"""
    if not hasattr(obj, "__dataclass_fields__"):
        return obj  # type: ignore[return-value]
    result: dict[str, Any] = {}
    for f in dataclass_fields(obj):  # type: ignore[arg-type]
        value = getattr(obj, f.name)
        if hasattr(value, "__dataclass_fields__"):
            result[f.name] = _dataclass_to_dict(value)
        elif isinstance(value, list):
            result[f.name] = [
                _dataclass_to_dict(item) if hasattr(item, "__dataclass_fields__") else item
                for item in value
            ]
        else:
            result[f.name] = value
    return result


class ConfigHotReloadService:
    """配置热更新服务。

    职责:
    - 从 YAML 文件重新加载配置并合并到运行时设置
    - 按点分路径动态修改单个参数
    - 记录变更审计日志（ConfigChangeLog）
    - 支持回滚到上一次变更前的状态

    Args:
        config_path: YAML 配置文件路径。
        settings: 运行时的 AppSettings 实例（原地修改）。
        on_change: 配置变更后的可选回调。
    """

    def __init__(
        self,
        config_path: str,
        settings: Any,
        on_change: Callable[[list[ConfigChangeLog]], None] | None = None,
    ) -> None:
        self._config_path = Path(config_path)
        self._settings = settings
        self._on_change = on_change
        self._change_history: list[ConfigChangeLog] = []
        self._snapshot: dict[str, Any] = {}

    @property
    def change_history(self) -> list[ConfigChangeLog]:
        return list(self._change_history)

    def take_snapshot(self) -> None:
        """保存当前配置快照，用于回滚。"""
        self._snapshot = _dataclass_to_dict(self._settings)
        logger.debug("已保存配置快照")

    def reload_from_file(self) -> list[ConfigChangeLog]:
        """从 YAML 文件重新加载配置。

        对比当前运行时值与文件中的值，差异部分生成变更日志并更新 settings。

        Returns:
            本次变更的 ConfigChangeLog 列表。
        """
        if not self._config_path.is_file():
            logger.error("配置文件不存在: %s", self._config_path)
            return []

        with open(self._config_path, encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}

        from src.infrastructure.config.settings import _resolve_dict_env_vars
        raw_data = _resolve_dict_env_vars(raw_data)

        old_dict = _dataclass_to_dict(self._settings)
        changes = self._diff_and_apply(old_dict, raw_data)

        if changes and self._on_change:
            self._on_change(changes)

        return changes

    def update_param(self, config_path: str, new_value: Any, *, user_id: str = "system") -> ConfigChangeLog:
        """动态更新单个配置参数。

        Args:
            config_path: 点分路径（如 "costs.commission_rate"）。
            new_value: 新值。
            user_id: 操作者标识。

        Returns:
            本次变更的 ConfigChangeLog。

        Raises:
            PermissionError: 当路径属于被阻止热更新的敏感配置。
            KeyError: 当路径在当前配置中不存在。
        """
        if _is_blocked(config_path):
            raise PermissionError(f"配置路径 '{config_path}' 不支持热更新（安全敏感）")

        # 取旧值
        settings_dict = _dataclass_to_dict(self._settings)
        old_value = _get_nested(settings_dict, config_path)
        if old_value is None:
            raise KeyError(f"配置路径 '{config_path}' 不存在")

        # 创建变更日志
        change = ConfigChangeLog(
            config_path=config_path,
            old_value=old_value,
            new_value=new_value,
            user_id=user_id,
        )

        # 应用到 settings 对象
        self._apply_to_settings(config_path, new_value)
        self._change_history.append(change)

        logger.info(
            "配置已更新: %s  %s -> %s (by %s)",
            config_path, old_value, new_value, user_id,
        )

        if self._on_change:
            self._on_change([change])

        return change

    def rollback(self) -> bool:
        """回滚到上一次快照。

        Returns:
            True 回滚成功，False 无快照可回滚。
        """
        if not self._snapshot:
            logger.warning("无配置快照可回滚")
            return False

        old_dict = _dataclass_to_dict(self._settings)
        changes = self._diff_and_apply(old_dict, self._snapshot, user_id="rollback")
        logger.info("已回滚配置，共 %d 项变更", len(changes))
        return True

    def _diff_and_apply(
        self,
        old_dict: dict[str, Any],
        new_dict: dict[str, Any],
        *,
        prefix: str = "",
        user_id: str = "file_watch",
    ) -> list[ConfigChangeLog]:
        """递归对比两个字典，差异部分应用到 settings 并生成变更日志。"""
        changes: list[ConfigChangeLog] = []
        all_keys = set(old_dict.keys()) | set(new_dict.keys())

        for key in all_keys:
            full_path = f"{prefix}.{key}" if prefix else key
            old_val = old_dict.get(key)
            new_val = new_dict.get(key)

            if isinstance(old_val, dict) and isinstance(new_val, dict):
                changes.extend(
                    self._diff_and_apply(old_val, new_val, prefix=full_path, user_id=user_id),
                )
            elif old_val != new_val:
                if _is_blocked(full_path):
                    logger.debug("跳过受保护配置: %s", full_path)
                    continue
                # 尝试应用
                try:
                    self._apply_to_settings(full_path, new_val)
                    change = ConfigChangeLog(
                        config_path=full_path,
                        old_value=old_val,
                        new_value=new_val,
                        user_id=user_id,
                    )
                    changes.append(change)
                    self._change_history.append(change)
                    logger.info("配置已更新: %s  %s -> %s", full_path, old_val, new_val)
                except (KeyError, AttributeError, TypeError) as e:
                    logger.warning("无法更新配置 %s: %s", full_path, e)

        return changes

    def _apply_to_settings(self, config_path: str, value: Any) -> None:
        """将值应用到 AppSettings 对象的嵌套属性。"""
        keys = config_path.split(".")
        obj = self._settings
        for key in keys[:-1]:
            obj = getattr(obj, key)
        setattr(obj, keys[-1], value)
