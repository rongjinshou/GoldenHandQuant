import json
from unittest.mock import MagicMock, patch

from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)
from src.infrastructure.notification.telegram_gateway import TelegramNotificationGateway


def _make_message(
    title: str = "Test",
    body: str = "Body",
    level: NotificationLevel = NotificationLevel.INFO,
) -> NotificationMessage:
    return NotificationMessage(
        title=title,
        body=body,
        level=level,
        category="test",
    )


class TestTelegramNotificationGateway:
    @patch("src.infrastructure.notification.telegram_gateway.request.urlopen")
    def test_send_success(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"ok": True}).encode()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        gw = TelegramNotificationGateway("bot-token", "chat-id")
        result = gw.send(_make_message())

        assert result is True
        mock_urlopen.assert_called_once()

    @patch("src.infrastructure.notification.telegram_gateway.request.urlopen")
    def test_send_failure(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"ok": False, "error": "bad"}).encode()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        gw = TelegramNotificationGateway("bot-token", "chat-id")
        result = gw.send(_make_message())

        assert result is False

    @patch("src.infrastructure.notification.telegram_gateway.request.urlopen")
    def test_send_network_error(self, mock_urlopen):
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("timeout")

        gw = TelegramNotificationGateway("bot-token", "chat-id")
        result = gw.send(_make_message())

        assert result is False
