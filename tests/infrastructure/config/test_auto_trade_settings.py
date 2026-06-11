"""AutoTradeSettings 新字段与 live 三重确认判定测试。"""
from src.infrastructure.config.settings import AutoTradeSettings
from src.interfaces.cli.auto_trade import resolve_mode


class TestAutoTradeSettings:
    def test_new_fields_have_safe_defaults(self):
        s = AutoTradeSettings()
        assert s.mode == "dry_run" and s.enabled is False
        assert s.strategy == "dual_ma"
        assert s.per_order_notional_cap == 1500.0
        assert s.daily_notional_cap == 3000.0
        assert s.daily_loss_limit_ratio == 0.02
        assert s.poll_timeout_seconds == 30.0
        assert s.db_path == "data/trading.db"
        assert s.max_orders_per_cycle == 3


class TestResolveMode:
    def test_live_requires_all_three_confirmations(self):
        s = AutoTradeSettings(mode="live", enabled=True)
        assert resolve_mode(s, live_flag=True) == "live"

    def test_missing_any_confirmation_downgrades(self):
        assert resolve_mode(AutoTradeSettings(mode="live", enabled=True),
                            live_flag=False) == "dry_run"
        assert resolve_mode(AutoTradeSettings(mode="live", enabled=False),
                            live_flag=True) == "dry_run"
        assert resolve_mode(AutoTradeSettings(mode="dry_run", enabled=True),
                            live_flag=True) == "dry_run"
