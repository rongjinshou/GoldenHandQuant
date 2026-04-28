from dataclasses import dataclass, field
from pathlib import Path
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
class AppSettings:
    backtest: BacktestSettings = field(default_factory=BacktestSettings)
    strategy: StrategySettings = field(default_factory=StrategySettings)
    position_sizing: PositionSizingSettings = field(default_factory=PositionSizingSettings)
    qmt: QmtSettings = field(default_factory=QmtSettings)


def load_backtest_config(path: str = "config/backtest.yaml") -> AppSettings:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AppSettings(
        backtest=BacktestSettings(**data.get("backtest", {})),
        strategy=StrategySettings(**data.get("strategy", {})),
        position_sizing=PositionSizingSettings(**data.get("position_sizing", {})),
    )


def load_trading_config(path: str = "config/trading.yaml") -> AppSettings:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AppSettings(
        qmt=QmtSettings(**data.get("qmt", {})),
    )
