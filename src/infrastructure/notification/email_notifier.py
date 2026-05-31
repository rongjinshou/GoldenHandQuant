import smtplib
from email.mime.text import MIMEText

from src.domain.risk.value_objects.risk_event import RiskEvent


class EmailNotifier:
    """邮件通知实现。"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        sender: str,
        password: str,
        receivers: list[str],
    ) -> None:
        self._host = smtp_host
        self._port = smtp_port
        self._sender = sender
        self._password = password
        self._receivers = receivers

    def notify(self, event: RiskEvent) -> None:
        subject = f"[Risk {event.severity}] {event.event_type}"
        body = f"[{event.severity}] {event.message}\nTime: {event.timestamp}"

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = self._sender
        msg["To"] = ", ".join(self._receivers)

        try:
            with smtplib.SMTP_SSL(self._host, self._port) as server:
                server.login(self._sender, self._password)
                server.sendmail(self._sender, self._receivers, msg.as_string())
        except Exception:
            pass  # 通知失败不应影响交易
