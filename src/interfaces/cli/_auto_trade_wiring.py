"""auto-trade 的 LiveSignalService 装配 —— 按策略类型选 sizer / 数据源。

R3c(架构重构 0628): 截面策略(micro_value/F01)经决策核心 CrossSectionalStrategyRunner
扫描, 必须拿到 EqualWeightSizer + fundamental_registry, 否则 universe 恒空、F01 信号
静默为零。本模块把"按 strategy_type 分流装配"从 QMT 网关组装(_build_service)里抽出,
使该决策可脱离 QMT 单测。

- cross_section: EqualWeightSizer(n=top_n, top_n 取 registry 默认 + at.strategy_params
                 覆盖) + DuckDB 同源 fundamental_registry(离线全市场)
                 + 宇宙取自 DuckDB(at.symbols 非空则取交集, 允许缩小到受限宇宙)。
                 0626 阶段1: at.mainboard_only 时按 check_symbol_scope 口径过滤宇宙;
                 today 无 fundamental 行时回退最近一期以 today 别名注册(as-of, DD-5),
                 滞后 >7 天或有效宇宙为空则抛 DataHealthError 拒绝装配(fail-fast, DD-4)。
- bar(时序):    FixedRatioSizer(position_ratio) + at.symbols 监视列表(原行为)。

真实 QMT live 的实时 fundamental 装配留真单 Spec; dry-run/影子盘用 DuckDB 同源。
设计: docs/feat/0628-backtest-live-unification/、docs/feat/0626-mainboard-f01-shadow/。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from src.application.data_health import DataHealthError
from src.application.live_signal_service import LiveSignalService
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer
from src.domain.strategy.registry import get_strategy
from src.domain.trade.services.pre_trade_checks import check_symbol_scope
from src.infrastructure.config.settings import AutoTradeSettings
from src.interfaces.cli._backtest_wiring import build_backtest_cross_section

# 基本面快照按季度更新; 3 年回溯窗口足以让 get_all_at_date(now) 取到最近一期,
# 即便 DuckDB 数据相对今天偏旧也不至落空。
_FUNDAMENTAL_LOOKBACK_DAYS = 1095

# as-of 别名容忍的最大滞后(日历日): 超过视为数据陈腐, 拒绝决策(DD-4/DD-5)。
_MAX_FUNDAMENTAL_STALENESS_DAYS = 7


@dataclass(slots=True, kw_only=True)
class AssemblyMeta:
    """截面装配元信息 — 注入 LiveSignalService 供决策快照留痕(DD-7)。"""
    universe_size: int
    filtered_size: int
    fundamental_date: datetime | None
    staleness_days: int


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

    merged_params = {**config.default_params, **at.strategy_params}
    top_n = int(merged_params.get("top_n", 9))

    end = today or date.today()
    start = end - timedelta(days=lookback_days)
    registry, universe = registry_builder(
        "DuckDBHistoryDataFetcher", start.isoformat(), end.isoformat(),
    )
    universe_size = len(universe)
    if at.mainboard_only:
        universe = [s for s in universe if check_symbol_scope(s) is None]
    filtered_size = len(universe)

    if at.symbols:
        universe_set = set(universe)
        symbols = [s for s in at.symbols if s in universe_set]
    else:
        symbols = list(universe)

    # as-of 别名(DD-5): 当日无 fundamental 行则回退最近一期, 以 today 别名注册
    today_dt = datetime.combine(end, time())
    staleness_days = 0
    fundamental_date: datetime | None = today_dt
    if not registry.get_all_at_date(today_dt):
        latest = registry.latest_date_at_or_before(today_dt)
        if latest is None:
            raise DataHealthError("fundamental registry 为空: market.duckdb 无可用基本面")
        staleness_days = (today_dt - latest).days
        if staleness_days > _MAX_FUNDAMENTAL_STALENESS_DAYS:
            raise DataHealthError(
                f"基本面滞后 {staleness_days} 天"
                f"(>{_MAX_FUNDAMENTAL_STALENESS_DAYS}), 先 data refresh",
            )
        registry.alias_date(latest, today_dt)
        fundamental_date = latest
    if not symbols:
        raise DataHealthError("有效宇宙为空(过滤后/交集后): 数据故障或配置错误, 拒绝装配")

    service = LiveSignalService(
        market_gateway=market_gateway,
        account_gateway=account_gateway,
        trade_gateway=trade_gateway,
        sizer=EqualWeightSizer(n_symbols=top_n),
        bar_lookback=at.bar_lookback,
        fundamental_registry=registry,
        strategy_params=merged_params,
        assembly_meta=AssemblyMeta(
            universe_size=universe_size,
            filtered_size=filtered_size,
            fundamental_date=fundamental_date,
            staleness_days=staleness_days,
        ),
    )
    return service, symbols
