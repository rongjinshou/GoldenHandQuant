import json
import logging
from urllib import error, request

from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)

logger = logging.getLogger(__name__)

_LEVEL_EMOJI = {
    NotificationLevel.INFO: "[INFO]",
    NotificationLevel.WARNING: "[WARN]",
    NotificationLevel.CRITICAL: "[CRIT]",
    NotificationLevel.EMERGENCY: "[EMERG]",
}


class WeChatNotificationGateway:
    """企业微信机器人 Webhook 通知网关。"""

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    def send(self, message: NotificationMessage) -> bool:
        """通过企业微信 Webhook 发送文本消息。"""
        emoji = _LEVEL_EMOJI.get(message.level, "[INFO]")
        text = f"{emoji} {message.title}\n{message.body}"
        payload = {
            "msgtype": "text",
            "text": {"content": text},
        }
        return self._post_json(payload)

    def send_batch(self, messages: list[NotificationMessage]) -> int:
        """批量发送，返回成功数。"""
        success = 0
        for msg in messages:
            if self.send(msg):
                success += 1
        return success

    def _post_json(self, payload: dict) -> bool:
        """发送 JSON POST 请求。"""
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = request.Request(
                self._webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read())
                if body.get("errcode") == 0:
                    return True
                logger.error("企业微信发送失败: %s", body)
                return False
        except error.URLError as e:
            logger.error("企业微信请求失败: %s", e)
            return False
        except Exception as e:
            logger.error("企业微信通知异常: %s", e)
            return False
