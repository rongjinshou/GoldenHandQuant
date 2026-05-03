from dataclasses import dataclass, field

import yaml


@dataclass(slots=True, kw_only=True)
class BacktestSettings:
    symbols: list[str] = field(default_factory=lambda: ["000021.SZ"])
    start_date: str = "2016-01-01"
    end_date: str = "2024-12-31"
    base_timeframe: str = "1d"
    initial_capital: float = 1_000_000.0
    plot: bool = True


@dataclass(slots=True, kw_only=True)
class StrategySettings:
    name: str = "DualMaStrategy"


@dataclass(slots=True, kw_only=True)
class PositionSizingSettings:
    type: str = "FixedRatioSizer"
    ratio: float = 0.2


@dataclass(slots=True, kw_only=True)
class QmtSettings:
    userdata_path: str = ""
    session_id: int = 123456
    account_id: str = ""
    account_type: str = "STOCK"


@dataclass(slots=True, kw_only=True)
class TushareDataSettings:
    token: str | None = None


@dataclass(slots=True, kw_only=True)
class DataSettings:
    cache_dir: str = "data/"
    history_fetcher: str = "TushareHistoryDataFetcher"
    tushare: TushareDataSettings = field(default_factory=TushareDataSettings)


@dataclass(slots=True, kw_only=True)
class RiskSettings:
    system_gate: dict = field(default_factory=dict)
    stop_loss: dict = field(default_factory=dict)
    policies: list[str] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class CostsSettings:
    commission_rate: float = 0.0002
    tax_rate: float = 0.001
    min_commission: float = 5.0
    slippage: float = 0.003


@dataclass(slots=True, kw_only=True)
class AppSettings:
    backtest: BacktestSettings = field(default_factory=BacktestSettings)
    strategy: StrategySettings = field(default_factory=StrategySettings)
    position_sizing: PositionSizingSettings = field(default_factory=PositionSizingSettings)
    qmt: QmtSettings = field(default_factory=QmtSettings)
    data: DataSettings = field(default_factory=DataSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    costs: CostsSettings = field(default_factory=CostsSettings)


def load_backtest_config(path: str = "resources/backtest.yaml") -> AppSettings:
    import os
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data_dict = data.get("data", {})
    tushare_dict = data_dict.pop("tushare", {})
    tushare_token = tushare_dict.get("token") or os.environ.get("TUSHARE_TOKEN")
    tushare_settings = TushareDataSettings(token=tushare_token)
    data_settings = DataSettings(tushare=tushare_settings, **data_dict)

    return AppSettings(
        backtest=BacktestSettings(**data.get("backtest", {})),
        strategy=StrategySettings(**data.get("strategy", {})),
        position_sizing=PositionSizingSettings(**data.get("position_sizing", {})),
        data=data_settings,
        risk=RiskSettings(**data.get("risk", {})),
        costs=CostsSettings(**data.get("costs", {})),
    )


def load_trading_config(path: str = "resources/trading.yaml") -> AppSettings:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AppSettings(
        qmt=QmtSettings(**data.get("qmt", {})),
    )
