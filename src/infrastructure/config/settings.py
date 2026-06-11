import os
import re
from dataclasses import dataclass, field

import yaml


def _resolve_env_vars(value: str) -> str:
    """将字符串中的 ${VAR} 占位符替换为环境变量值。"""
    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, "")
    return re.sub(r"\$\{(\w+)\}", _replace, value)


def _resolve_dict_env_vars(data: object) -> object:
    """递归解析字典中所有字符串值的 ${VAR} 占位符。"""
    if isinstance(data, str):
        return _resolve_env_vars(data)
    if isinstance(data, dict):
        return {k: _resolve_dict_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_dict_env_vars(item) for item in data]
    return data


@dataclass(slots=True, kw_only=True)
class BacktestSettings:
    symbols: list[str] = field(default_factory=lambda: ["000021.SZ"])
    start_date: str = "2016-01-01"
    end_date: str = "2024-12-31"
    base_timeframe: str = "1d"
    initial_capital: float = 1_000_000.0
    plot: bool = True
    benchmark: str = "000852.SH"


@dataclass(slots=True, kw_only=True)
class StrategySettings:
    name: str = "DualMaStrategy"
    top_n: int = 9
    weights: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class PositionSizingSettings:
    type: str = "FixedRatioSizer"
    ratio: float = 0.2


@dataclass(slots=True, kw_only=True)
class QmtAccountConfig:
    """单个 QMT 账户配置。"""
    account_id: str = ""
    account_type: str = "STOCK"
    initial_capital: float = 1_000_000.0


@dataclass(slots=True, kw_only=True)
class QmtSettings:
    userdata_path: str = ""
    session_id: int = 0
    account_id: str = ""
    account_type: str = "STOCK"
    accounts: list[QmtAccountConfig] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class TushareDataSettings:
    token: str | None = None


@dataclass(slots=True, kw_only=True)
class DataSettings:
    cache_dir: str = "data/"
    history_fetcher: str = "TushareHistoryDataFetcher"
    tushare: TushareDataSettings = field(default_factory=TushareDataSettings)


@dataclass(slots=True, kw_only=True)
class SystemGateSettings:
    index_symbol: str = "000852.SH"
    ma_period: int = 20


@dataclass(slots=True, kw_only=True)
class StopLossSettings:
    max_loss_ratio: float = 0.03


@dataclass(slots=True, kw_only=True)
class CircuitBreakerSettings:
    enabled: bool = False
    max_daily_loss: float = 0.03
    max_total_drawdown: float = 0.20
    cooldown_days: int = 1


@dataclass(slots=True, kw_only=True)
class WeChatNotificationSettings:
    enabled: bool = False
    webhook_url: str = ""


@dataclass(slots=True, kw_only=True)
class EmailNotificationSettings:
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 465
    sender: str = ""
    password: str = ""
    receivers: list[str] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class NotificationSettings:
    console: bool = True
    wechat: WeChatNotificationSettings = field(default_factory=WeChatNotificationSettings)
    email: EmailNotificationSettings = field(default_factory=EmailNotificationSettings)


@dataclass(slots=True, kw_only=True)
class RiskSettings:
    system_gate: SystemGateSettings = field(default_factory=SystemGateSettings)
    stop_loss: StopLossSettings = field(default_factory=StopLossSettings)
    circuit_breaker: CircuitBreakerSettings = field(default_factory=CircuitBreakerSettings)
    notification: NotificationSettings = field(default_factory=NotificationSettings)
    policies: list[str] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class CostsSettings:
    commission_rate: float = 0.00025
    tax_rate: float = 0.001
    min_commission: float = 5.0
    slippage: float = 0.001


@dataclass(slots=True, kw_only=True)
class LiveTradeSettings:
    strategy: str = "dual_ma"
    symbols: list[str] = field(default_factory=list)
    position_ratio: float = 0.1
    slippage_buy: float = 0.001
    slippage_sell: float = 0.001
    bar_lookback: int = 100


@dataclass(slots=True, kw_only=True)
class AutoTradeSettings:
    """自动交易配置 (闭环 v1 设计 DD-8)。"""
    enabled: bool = False
    mode: str = "dry_run"               # dry_run | live (live 还需 CLI --live)
    strategy: str = "dual_ma"
    strategy_names: list[str] = field(default_factory=list)   # 兼容旧字段
    symbols: list[str] = field(default_factory=list)
    execution_times: list[str] = field(default_factory=lambda: ["09:35", "14:50"])
    max_orders_per_cycle: int = 3
    min_confidence: float = 0.6
    check_interval_seconds: int = 60
    per_order_notional_cap: float = 1500.0
    daily_notional_cap: float = 3000.0
    daily_loss_limit_ratio: float = 0.02
    poll_timeout_seconds: float = 30.0
    position_ratio: float = 0.1
    bar_lookback: int = 100
    db_path: str = "data/trading.db"


@dataclass(slots=True, kw_only=True)
class AnomalySettings:
    """异常检测配置。"""
    min_win_rate: float = 0.45
    max_consecutive_losses: int = 5
    lookback_trades: int = 20
    crash_threshold: float = -0.03
    max_price_jump: float = 0.10
    volume_spike_ratio: float = 10.0


@dataclass(slots=True, kw_only=True)
class TelegramNotificationSettings:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


@dataclass(slots=True, kw_only=True)
class AutoNotificationSettings:
    """自动交易通知配置。"""
    quiet_hours_start: int = 23
    quiet_hours_end: int = 7
    rate_limit_per_minute: int = 10
    telegram: TelegramNotificationSettings = field(
        default_factory=TelegramNotificationSettings,
    )


@dataclass(slots=True, kw_only=True)
class MonitorAlertSettings:
    daily_loss_threshold: float = 0.03
    stock_loss_threshold: float = 0.05
    position_ratio_max: float = 0.80
    position_ratio_min: float = 0.10
    concentration_max: float = 0.30


@dataclass(slots=True, kw_only=True)
class MonitorSettings:
    refresh_interval: int = 3
    snapshot_dir: str = "data/snapshots/"
    alerts: MonitorAlertSettings = field(default_factory=MonitorAlertSettings)


@dataclass(slots=True, kw_only=True)
class MultiAccountSettings:
    """多账户配置。"""
    enabled: bool = False
    group_id: str = "default_group"
    group_name: str = "默认账户组"
    max_total_exposure: float = 0.0
    max_single_concentration: float = 0.30
    max_account_count: int = 10


@dataclass(slots=True, kw_only=True)
class AppSettings:
    backtest: BacktestSettings = field(default_factory=BacktestSettings)
    strategy: StrategySettings = field(default_factory=StrategySettings)
    position_sizing: PositionSizingSettings = field(default_factory=PositionSizingSettings)
    qmt: QmtSettings = field(default_factory=QmtSettings)
    data: DataSettings = field(default_factory=DataSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    costs: CostsSettings = field(default_factory=CostsSettings)
    live_trade: LiveTradeSettings = field(default_factory=LiveTradeSettings)
    monitor: MonitorSettings = field(default_factory=MonitorSettings)
    auto_trade: AutoTradeSettings = field(default_factory=AutoTradeSettings)
    anomaly: AnomalySettings = field(default_factory=AnomalySettings)
    auto_notification: AutoNotificationSettings = field(
        default_factory=AutoNotificationSettings,
    )
    multi_account: MultiAccountSettings = field(default_factory=MultiAccountSettings)


def load_backtest_config(path: str = "resources/backtest.yaml") -> AppSettings:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data = _resolve_dict_env_vars(data)

    data_dict = data.get("data", {})
    tushare_dict = data_dict.pop("tushare", {})
    tushare_token = tushare_dict.get("token")
    tushare_settings = TushareDataSettings(token=tushare_token)
    data_settings = DataSettings(tushare=tushare_settings, **data_dict)

    risk_data = data.get("risk", {})
    system_gate_dict = risk_data.pop("system_gate", {})
    stop_loss_dict = risk_data.pop("stop_loss", {})
    cb_dict = risk_data.pop("circuit_breaker", {})
    notif_dict = risk_data.pop("notification", {})

    wechat_dict = notif_dict.pop("wechat", {})
    email_dict = notif_dict.pop("email", {})
    notification_settings = NotificationSettings(
        wechat=WeChatNotificationSettings(**wechat_dict),
        email=EmailNotificationSettings(**email_dict),
        **notif_dict,
    )

    risk_settings = RiskSettings(
        system_gate=SystemGateSettings(**system_gate_dict),
        stop_loss=StopLossSettings(**stop_loss_dict),
        circuit_breaker=CircuitBreakerSettings(**cb_dict),
        notification=notification_settings,
        **risk_data,
    )

    return AppSettings(
        backtest=BacktestSettings(**data.get("backtest", {})),
        strategy=StrategySettings(**data.get("strategy", {})),
        position_sizing=PositionSizingSettings(**data.get("position_sizing", {})),
        data=data_settings,
        risk=risk_settings,
        costs=CostsSettings(**data.get("costs", {})),
    )


def load_trading_config(path: str = "resources/trading.yaml") -> AppSettings:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data = _resolve_dict_env_vars(data)

    live_trade_data = data.get("live_trade", {})
    live_trade_data.pop("strategy_params", None)
    live_trade = LiveTradeSettings(**live_trade_data)

    qmt_data = data.get("qmt", {})
    accounts_data = qmt_data.pop("accounts", [])
    accounts = [QmtAccountConfig(**acc) for acc in accounts_data]
    qmt = QmtSettings(accounts=accounts, **qmt_data)

    monitor_data = data.get("monitor", {})
    alerts_data = monitor_data.pop("alerts", {})
    monitor = MonitorSettings(
        alerts=MonitorAlertSettings(**alerts_data),
        **monitor_data,
    )

    # 解析 auto_trade 配置
    auto_trade_data = data.get("auto_trade", {})
    auto_trade = AutoTradeSettings(**auto_trade_data)

    # 解析 anomaly 配置
    anomaly_data = data.get("anomaly", {})
    anomaly = AnomalySettings(**anomaly_data)

    # 解析 auto_notification 配置
    auto_notif_data = data.get("auto_notification", {})
    telegram_data = auto_notif_data.pop("telegram", {})
    auto_notification = AutoNotificationSettings(
        telegram=TelegramNotificationSettings(**telegram_data),
        **auto_notif_data,
    )

    # 解析 multi_account 配置
    multi_account_data = data.get("multi_account", {})
    multi_account = MultiAccountSettings(**multi_account_data)

    return AppSettings(
        qmt=qmt,
        live_trade=live_trade,
        monitor=monitor,
        auto_trade=auto_trade,
        anomaly=anomaly,
        auto_notification=auto_notification,
        multi_account=multi_account,
    )
