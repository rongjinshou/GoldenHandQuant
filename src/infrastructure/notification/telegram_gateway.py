import json
import logging
from urllib import error, request
from urllib.parse import urlparse

from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)

logger = logging.getLogger(__name__)


def _validate_api_url(url: str) -> None:
    """校验 API URL 安全性。

    要求必须以 https:// 开头，拒绝 http:// 和非标准端口。

    Raises:
        ValueError: URL 不符合安全要求。
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"API URL 必须使用 HTTPS，当前: {parsed.scheme or '(无协议)'}")
    if parsed.port and parsed.port != 443:
        raise ValueError(f"API URL 不允许使用非标准端口: {parsed.port}")

_LEVEL_TAG = {
    NotificationLevel.INFO: "INFO",
    NotificationLevel.WARNING: "WARNING",
    NotificationLevel.CRITICAL: "CRITICAL",
    NotificationLevel.EMERGENCY: "EMERGENCY",
}


class TelegramNotificationGateway:
    """Telegram Bot 通知网关。"""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        _validate_api_url(self._base_url)

    def send(self, message: NotificationMessage) -> bool:
        """通过 Telegram Bot API 发送消息。"""
        tag = _LEVEL_TAG.get(message.level, "INFO")
        text = f"[{tag}] {message.title}\n{message.body}"
        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        return self._post_json(url, payload)

    def send_batch(self, messages: list[NotificationMessage]) -> int:
        """批量发送，返回成功数。"""
        success = 0
        for msg in messages:
            if self.send(msg):
                success += 1
        return success

    def _post_json(self, url: str, payload: dict) -> bool:
        """发送 JSON POST 请求。"""
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read())
                if body.get("ok"):
                    return True
                logger.error("Telegram 发送失败: %s", body)
                return False
        except error.URLError as e:
            logger.error("Telegram 请求失败: %s", e)
            return False
        except Exception as e:
            logger.error("Telegram 通知异常: %s", e)
            return False
