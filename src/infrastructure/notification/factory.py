from src.domain.notification.interfaces.notification_gateway import INotificationGateway
from src.domain.risk.interfaces.notification import IRiskNotifier
from src.infrastructure.config.settings import NotificationSettings
from src.infrastructure.notification.console_notifier import ConsoleNotifier
from src.infrastructure.notification.email_notifier import EmailNotifier
from src.infrastructure.notification.risk_notifier_adapter import RiskNotifierAdapter
from src.infrastructure.notification.wechat_notifier import WeChatNotifier


def create_notifiers(settings: NotificationSettings) -> list[IRiskNotifier]:
    """根据配置创建通知器列表。"""
    notifiers: list[IRiskNotifier] = []

    if settings.console:
        notifiers.append(ConsoleNotifier())

    if settings.wechat.enabled and settings.wechat.webhook_url:
        notifiers.append(WeChatNotifier(webhook_url=settings.wechat.webhook_url))

    if settings.email.enabled and settings.email.smtp_host:
        notifiers.append(EmailNotifier(
            smtp_host=settings.email.smtp_host,
            smtp_port=settings.email.smtp_port,
            sender=settings.email.sender,
            password=settings.email.password,
            receivers=settings.email.receivers,
        ))

    return notifiers


def create_notification_gateway(settings: NotificationSettings) -> INotificationGateway | None:
    """创建 INotificationGateway 适配器（桥接 IRiskNotifier -> INotificationGateway）。"""
    notifiers = create_notifiers(settings)
    if not notifiers:
        return None
    # 使用第一个通知器作为底层实现
    return RiskNotifierAdapter(notifiers[0])
