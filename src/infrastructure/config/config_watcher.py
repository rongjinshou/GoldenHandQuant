"""配置文件监听器（基于 watchdog）。

监听 YAML 配置文件变更，触发回调通知上层服务进行热更新。
"""

import logging
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

# 文件变更回调签名: callback(file_path: Path) -> None
FileChangeCallback = Callable[[Path], None]


class _YamlChangeHandler(FileSystemEventHandler):
    """watchdog 事件处理器，过滤 YAML 文件修改事件。"""

    def __init__(self, callback: FileChangeCallback) -> None:
        super().__init__()
        self._callback = callback

    def on_modified(self, event: FileModifiedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix in (".yaml", ".yml"):
            logger.info("检测到配置文件变更: %s", path)
            self._callback(path)


class ConfigWatcher:
    """配置文件监听器。

    使用 watchdog 监听指定目录下 YAML 文件的变更，文件修改时触发回调。
    线程安全，支持 start/stop 生命周期管理。

    Args:
        watch_dir: 要监听的目录路径。
        callback: 文件变更时的回调函数。
        recursive: 是否递归监听子目录，默认 False。
    """

    def __init__(
        self,
        watch_dir: str | Path,
        callback: FileChangeCallback,
        *,
        recursive: bool = False,
    ) -> None:
        self._watch_dir = Path(watch_dir)
        self._callback = callback
        self._recursive = recursive
        self._observer: Observer | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """启动文件监听（后台守护线程）。"""
        if self._running:
            logger.warning("ConfigWatcher 已在运行中")
            return
        if not self._watch_dir.is_dir():
            logger.error("监听目录不存在: %s", self._watch_dir)
            return

        handler = _YamlChangeHandler(self._callback)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._watch_dir), recursive=self._recursive)
        self._observer.daemon = True
        self._observer.start()
        self._running = True
        logger.info("ConfigWatcher 已启动，监听目录: %s", self._watch_dir)

    def stop(self) -> None:
        """停止文件监听。"""
        if not self._running or self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None
        self._running = False
        logger.info("ConfigWatcher 已停止")
