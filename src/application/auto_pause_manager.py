import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.domain.notification.interfaces.notification_gateway import INotificationGateway
from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)
from src.domain.risk.value_objects.anomaly_event import AnomalyEvent

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class PauseState:
    """暂停状态。"""
    strategy_name: str
    is_paused: bool
    reason: str
    paused_at: datetime | None = None
    resume_conditions: list[str] = field(default_factory=list)


class AutoPauseManager:
    """自动暂停管理器。

    维护每个策略的暂停状态，管理暂停/恢复逻辑。
    暂停状态持久化到 JSON 文件。
    """

    def __init__(
        self,
        notification_gateway: INotificationGateway | None = None,
        state_file: str = "data/pause_state.json",
        hmac_key: str | None = None,
    ) -> None:
        self._notification_gateway = notification_gateway
        self._state_file = Path(state_file)
        self._states: dict[str, PauseState] = {}
        self._paused_all: bool = False
        self._paused_all_reason: str = ""
        self._paused_all_at: datetime | None = None
        self._hmac_key = (hmac_key or os.environ.get("PAUSE_STATE_HMAC_KEY", "")).encode()
        self._load_state()

    @property
    def is_all_paused(self) -> bool:
        return self._paused_all

    def pause_strategy(self, strategy_name: str, event: AnomalyEvent) -> None:
        """暂停指定策略。"""
        if strategy_name in self._states and self._states[strategy_name].is_paused:
            return

        self._states[strategy_name] = PauseState(
            strategy_name=strategy_name,
            is_paused=True,
            reason=event.message,
            paused_at=datetime.now(),
        )
        self._save_state()

        logger.warning("策略已暂停: %s - %s", strategy_name, event.message)

        if self._notification_gateway:
            self._notification_gateway.send(NotificationMessage(
                title=f"策略暂停: {strategy_name}",
                body=event.message,
                level=NotificationLevel.CRITICAL,
                category="anomaly",
            ))

    def pause_all(self, event: AnomalyEvent) -> None:
        """暂停所有策略 (紧急熔断)。"""
        self._paused_all = True
        self._paused_all_reason = event.message
        self._paused_all_at = datetime.now()
        self._save_state()

        logger.critical("全部策略已暂停: %s", event.message)

        if self._notification_gateway:
            self._notification_gateway.send(NotificationMessage(
                title="紧急熔断: 全部策略暂停",
                body=event.message,
                level=NotificationLevel.EMERGENCY,
                category="anomaly",
            ))

    def check_resume(self, strategy_name: str) -> bool:
        """检查是否满足恢复条件。

        恢复条件: 异常消失 (连续 N 次检测正常)。
        当前简化实现: 需要手动恢复。
        """
        return False

    def resume(self, strategy_name: str, operator: str = "system") -> None:
        """恢复策略执行。"""
        if strategy_name not in self._states:
            return

        state = self._states[strategy_name]
        if not state.is_paused:
            return

        state.is_paused = False
        state.reason = ""
        state.paused_at = None
        self._save_state()

        logger.info("策略已恢复: %s (操作者: %s)", strategy_name, operator)

        if self._notification_gateway:
            self._notification_gateway.send(NotificationMessage(
                title=f"策略恢复: {strategy_name}",
                body=f"由 {operator} 手动恢复",
                level=NotificationLevel.INFO,
                category="anomaly",
            ))

    def resume_all(self, operator: str = "system") -> None:
        """恢复所有策略。"""
        self._paused_all = False
        self._paused_all_reason = ""
        self._paused_all_at = None

        for state in self._states.values():
            state.is_paused = False
            state.reason = ""
            state.paused_at = None

        self._save_state()

        logger.info("全部策略已恢复 (操作者: %s)", operator)

        if self._notification_gateway:
            self._notification_gateway.send(NotificationMessage(
                title="全部策略恢复",
                body=f"由 {operator} 手动恢复",
                level=NotificationLevel.INFO,
                category="anomaly",
            ))

    def is_strategy_paused(self, strategy_name: str) -> bool:
        """检查策略是否被暂停。"""
        if self._paused_all:
            return True
        state = self._states.get(strategy_name)
        return state is not None and state.is_paused

    def get_status(self) -> list[PauseState]:
        """获取所有策略的暂停状态。"""
        return list(self._states.values())

    def _compute_signature(self, payload: str) -> str:
        """计算 HMAC 签名。"""
        return hmac.new(self._hmac_key, payload.encode(), hashlib.sha256).hexdigest()

    def _save_state(self) -> None:
        """持久化暂停状态到 JSON 文件，附带 HMAC 签名。"""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "paused_all": self._paused_all,
            "paused_all_reason": self._paused_all_reason,
            "paused_all_at": self._paused_all_at.isoformat() if self._paused_all_at else None,
            "strategies": {},
        }
        for name, state in self._states.items():
            data["strategies"][name] = {
                "is_paused": state.is_paused,
                "reason": state.reason,
                "paused_at": state.paused_at.isoformat() if state.paused_at else None,
            }
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
        wrapper = {
            "payload": json.loads(payload),
            "signature": self._compute_signature(payload),
        }
        self._state_file.write_text(json.dumps(wrapper, ensure_ascii=False, indent=2))

    def _load_state(self) -> None:
        """从 JSON 文件加载暂停状态，验证 HMAC 签名完整性。"""
        if not self._state_file.exists():
            return
        try:
            raw = json.loads(self._state_file.read_text())

            # 兼容无签名的旧格式
            if "payload" in raw and "signature" in raw:
                payload_str = json.dumps(raw["payload"], ensure_ascii=False, sort_keys=True)
                expected_sig = self._compute_signature(payload_str)
                if not hmac.compare_digest(expected_sig, raw["signature"]):
                    logger.error("暂停状态文件签名校验失败，拒绝加载（文件可能被篡改）")
                    return
                data = raw["payload"]
            else:
                data = raw

            self._paused_all = data.get("paused_all", False)
            self._paused_all_reason = data.get("paused_all_reason", "")
            paused_at_str = data.get("paused_all_at")
            if paused_at_str:
                self._paused_all_at = datetime.fromisoformat(paused_at_str)

            for name, info in data.get("strategies", {}).items():
                paused_at = None
                if info.get("paused_at"):
                    paused_at = datetime.fromisoformat(info["paused_at"])
                self._states[name] = PauseState(
                    strategy_name=name,
                    is_paused=info.get("is_paused", False),
                    reason=info.get("reason", ""),
                    paused_at=paused_at,
                )
        except Exception as e:
            logger.error("加载暂停状态失败: %s", e)
