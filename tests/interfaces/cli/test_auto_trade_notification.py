"""confirmed-bug(2026-07-05 全项目排查发现) 回归测试:

`_build_notification_hub` 通过 `settings.notification` 读通知配置，但
`AppSettings` 顶层没有 `notification` 字段（配置嵌在 `settings.risk.notification`
下）——`quant auto-trade` 的任何模式（--once/守护循环、dry_run/live）在装配阶段
都会必现 `AttributeError`，整个自动交易入口不可用。同批一并修复 `load_trading_config`
从未解析 `risk` 段的问题（详见 `test_settings.py::test_load_trading_config_parses_risk_section`）。
"""
from src.application.notification_hub import NotificationHub
from src.infrastructure.config.settings import (
    AppSettings,
    NotificationSettings,
    RiskSettings,
    WeChatNotificationSettings,
)
from src.interfaces.cli.auto_trade import _build_notification_hub


def test_build_notification_hub_does_not_raise_with_real_app_settings():
    """回归核心: 传入真实 AppSettings 不应抛 AttributeError(此前 100% 必现)。"""
    settings = AppSettings()
    hub = _build_notification_hub(settings)
    assert hub is not None  # 默认 console=True, 至少有一个通知渠道


def test_build_notification_hub_returns_none_when_all_channels_disabled():
    settings = AppSettings(
        risk=RiskSettings(notification=NotificationSettings(console=False)),
    )
    hub = _build_notification_hub(settings)
    assert hub is None


def test_build_notification_hub_uses_risk_notification_not_toplevel():
    """确认读的是 settings.risk.notification, 不是(不存在的) settings.notification。"""
    settings = AppSettings(
        risk=RiskSettings(
            notification=NotificationSettings(
                console=False,
                wechat=WeChatNotificationSettings(enabled=True, webhook_url="https://example.com/hook"),
            ),
        ),
    )
    hub = _build_notification_hub(settings)
    assert isinstance(hub, NotificationHub)
