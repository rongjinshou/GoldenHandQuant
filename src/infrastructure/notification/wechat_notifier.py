import json
import urllib.request

from src.domain.risk.value_objects.risk_event import RiskEvent, RiskSeverity


class WeChatNotifier:
    """企业微信 Webhook 通知。"""

    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    def notify(self, event: RiskEvent) -> None:
        emoji = {
            RiskSeverity.INFO: "[INFO]",
            RiskSeverity.WARNING: "[WARN]",
            RiskSeverity.CRITICAL: "[ALERT]",
        }
        payload = {
            "msgtype": "text",
            "text": {
                "content": f"{emoji.get(event.severity, '')} {event.message}"
            },
        }
        req = urllib.request.Request(
            self._url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # 通知失败不应影响交易
