"""auto-trade 的 LiveSignalService 装配 —— 按策略类型选 sizer / 数据源。

R3c(架构重构 0628): 截面策略(micro_value/F01)经决策核心 CrossSectionalStrategyRunner
扫描, 必须拿到 EqualWeightSizer + fundamental_registry, 否则 universe 恒空、F01 信号
静默为零。本模块把"按 strategy_type 分流装配"从 QMT 网关组装(_build_service)里抽出,
使该决策可脱离 QMT 单测。

- cross_section: EqualWeightSizer(n=top_n) + DuckDB 同源 fundamental_registry(离线全市场)
                 + 宇宙取自 DuckDB(at.symbols 非空则取交集, 允许缩小到受限宇宙)。
- bar(时序):    FixedRatioSizer(position_ratio) + at.symbols 监视列表(原行为)。

真实 QMT live 的实时 fundamental 装配留真单 Spec; dry-run/影子盘用 DuckDB 同源。
设计: docs/feat/0628-backtest-live-unification/。
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from src.application.live_signal_service import LiveSignalService
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer
from src.domain.strategy.registry import get_strategy
from src.infrastructure.config.settings import AutoTradeSettings
from src.interfaces.cli._backtest_wiring import build_backtest_cross_section

# 基本面快照按季度更新; 3 年回溯窗口足以让 get_all_at_date(now) 取到最近一期,
# 即便 DuckDB 数据相对今天偏旧也不至落空。
_FUNDAMENTAL_LOOKBACK_DAYS = 1095


def build_live_signal_service(
    at: AutoTradeSettings,
    *,
    market_gateway,
    account_gateway,
    trade_gateway,
    registry_builder: Callable[..., tuple] = build_backtest_cross_section,
    today: date | None = None,
    lookback_days: int = _FUNDAMENTAL_LOOKBACK_DAYS,
) -> tuple[LiveSignalService, list[str]]:
    """按 at.strategy 的类型装配 LiveSignalService, 返回 (service, 有效宇宙)。"""
    config = get_strategy(at.strategy)

    if config.strategy_type != "cross_section":
        service = LiveSignalService(
            market_gateway=market_gateway,
            account_gateway=account_gateway,
            trade_gateway=trade_gateway,
            sizer=FixedRatioSizer(ratio=at.position_ratio),
            bar_lookback=at.bar_lookback,
        )
        return service, list(at.symbols)

    end = today or date.today()
    start = end - timedelta(days=lookback_days)
    registry, universe = registry_builder(
        "DuckDBHistoryDataFetcher", start.isoformat(), end.isoformat(),
    )
    if at.symbols:
        universe_set = set(universe)
        symbols = [s for s in at.symbols if s in universe_set]
    else:
        symbols = list(universe)

    top_n = int(config.default_params.get("top_n", 9))
    service = LiveSignalService(
        market_gateway=market_gateway,
        account_gateway=account_gateway,
        trade_gateway=trade_gateway,
        sizer=EqualWeightSizer(n_symbols=top_n),
        bar_lookback=at.bar_lookback,
        fundamental_registry=registry,
    )
    return service, symbols
