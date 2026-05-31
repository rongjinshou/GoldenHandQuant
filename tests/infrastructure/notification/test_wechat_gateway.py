import json
from unittest.mock import MagicMock, patch

from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)
from src.infrastructure.notification.wechat_gateway import WeChatNotificationGateway


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


class TestWeChatNotificationGateway:
    @patch("src.infrastructure.notification.wechat_gateway.request.urlopen")
    def test_send_success(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"errcode": 0}).encode()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        gw = WeChatNotificationGateway("https://example.com/webhook")
        result = gw.send(_make_message())

        assert result is True
        mock_urlopen.assert_called_once()

    @patch("src.infrastructure.notification.wechat_gateway.request.urlopen")
    def test_send_failure(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"errcode": 93000, "errmsg": "invalid"}).encode()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        gw = WeChatNotificationGateway("https://example.com/webhook")
        result = gw.send(_make_message())

        assert result is False

    @patch("src.infrastructure.notification.wechat_gateway.request.urlopen")
    def test_send_network_error(self, mock_urlopen):
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("connection refused")

        gw = WeChatNotificationGateway("https://example.com/webhook")
        result = gw.send(_make_message())

        assert result is False

    @patch("src.infrastructure.notification.wechat_gateway.request.urlopen")
    def test_send_batch(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"errcode": 0}).encode()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        gw = WeChatNotificationGateway("https://example.com/webhook")
        messages = [_make_message(title=f"Msg {i}") for i in range(3)]
        count = gw.send_batch(messages)

        assert count == 3
