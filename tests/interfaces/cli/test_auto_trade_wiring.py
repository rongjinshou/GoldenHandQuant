"""R3c: auto-trade 装配按策略类型选 sizer / fundamental_registry。

截面策略(micro_value)必须拿到 EqualWeightSizer + DuckDB 同源 fundamental_registry,
否则决策核心 universe 恒空、F01 信号静默为零(R3c 修复的洞)。
0626 阶段1(B1): 主板过滤 + fundamental as-of 别名 + 装配期 fail-fast + strategy_params。
"""
from datetime import date, datetime, timedelta
from unittest.mock import Mock

import pytest

from src.application.data_health import DataHealthError
from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer
from src.infrastructure.config.settings import AutoTradeSettings
from src.interfaces.cli._auto_trade_wiring import build_live_signal_service

_TODAY = date(2026, 6, 30)
_TODAY_DT = datetime(2026, 6, 30)


def _gateways() -> dict:
    return {
        "market_gateway": Mock(),
        "account_gateway": Mock(),
        "trade_gateway": Mock(),
    }


def _registry_with(symbols: list[str], day: datetime) -> FundamentalRegistry:
    registry = FundamentalRegistry()
    for symbol in symbols:
        registry.add(FundamentalSnapshot(
            symbol=symbol, date=day, name=symbol[:6],
            list_date=datetime(2015, 1, 1), market_cap=5e9,
        ))
    return registry


def _builder_returning(registry: FundamentalRegistry, universe: list[str]):
    def fake_builder(fetcher_type, start, end):
        return registry, universe
    return fake_builder


def test_cross_section_wires_equal_weight_and_fundamental_registry():
    # Arrange: micro_value 是 cross_section, default top_n=9
    universe = ["000001.SZ", "000002.SZ", "600000.SH"]
    registry = _registry_with(universe, _TODAY_DT)
    captured: dict = {}

    def fake_builder(fetcher_type, start, end):
        captured["args"] = (fetcher_type, start, end)
        return registry, universe

    at = AutoTradeSettings(strategy="micro_value", symbols=[])

    # Act
    service, symbols = build_live_signal_service(
        at, **_gateways(), registry_builder=fake_builder, today=_TODAY,
    )

    # Assert: 截面 → 等权 sizer(n=top_n) + 注入 registry + 全宇宙
    assert isinstance(service.sizer, EqualWeightSizer)
    assert service.sizer._n_symbols == 9
    assert service.fundamental_registry is registry
    assert symbols == ["000001.SZ", "000002.SZ", "600000.SH"]
    # DuckDB 同源, 3 年回溯窗口至 today
    assert captured["args"][0] == "DuckDBHistoryDataFetcher"
    assert captured["args"][2] == "2026-06-30"
    assert captured["args"][1] == (_TODAY - timedelta(days=1095)).isoformat()


def test_cross_section_intersects_configured_symbols():
    # 显式配 at.symbols → 与 DuckDB 宇宙取交集(允许缩小到受限宇宙)
    universe = ["000001.SZ", "000002.SZ"]
    registry = _registry_with(universe, _TODAY_DT)

    at = AutoTradeSettings(strategy="micro_value", symbols=["000001.SZ", "999999.XX"])
    _, symbols = build_live_signal_service(
        at, **_gateways(),
        registry_builder=_builder_returning(registry, universe), today=_TODAY,
    )
    assert symbols == ["000001.SZ"]  # 999999 不在宇宙, 被滤掉


def test_bar_strategy_wires_fixed_ratio_and_skips_fundamental():
    # 时序策略(dual_ma=bar) → FixedRatioSizer, 不构建 fundamental, 用 at.symbols
    called: list = []

    def fake_builder(*args, **kwargs):
        called.append(1)
        return FundamentalRegistry(), []

    at = AutoTradeSettings(strategy="dual_ma", symbols=["600000.SH"], position_ratio=0.2)
    service, symbols = build_live_signal_service(
        at, **_gateways(), registry_builder=fake_builder,
    )
    assert isinstance(service.sizer, FixedRatioSizer)
    assert service.fundamental_registry is None
    assert symbols == ["600000.SH"]
    assert called == []  # bar 路径绝不触发 DuckDB 装配


def test_mainboard_only_filters_universe_and_reports_sizes():
    universe = ["600000.SH", "300001.SZ", "000001.SZ", "688001.SH"]
    registry = _registry_with(universe, _TODAY_DT)
    at = AutoTradeSettings(strategy="micro_value", symbols=[], mainboard_only=True)

    service, symbols = build_live_signal_service(
        at, **_gateways(),
        registry_builder=_builder_returning(registry, universe), today=_TODAY,
    )

    assert symbols == ["600000.SH", "000001.SZ"]
    assert service.assembly_meta.universe_size == 4
    assert service.assembly_meta.filtered_size == 2


def test_mainboard_off_keeps_full_universe():
    # 默认 mainboard_only=False → 创业板/科创板不被过滤(行为回归)
    universe = ["600000.SH", "300001.SZ", "688001.SH"]
    registry = _registry_with(universe, _TODAY_DT)
    at = AutoTradeSettings(strategy="micro_value", symbols=[])

    service, symbols = build_live_signal_service(
        at, **_gateways(),
        registry_builder=_builder_returning(registry, universe), today=_TODAY,
    )

    assert symbols == universe
    assert service.assembly_meta.universe_size == 3
    assert service.assembly_meta.filtered_size == 3


def test_strategy_params_top_n_overrides_registry_default():
    universe = ["000001.SZ", "600000.SH"]
    registry = _registry_with(universe, _TODAY_DT)
    at = AutoTradeSettings(
        strategy="micro_value", symbols=[], strategy_params={"top_n": 20},
    )

    service, _ = build_live_signal_service(
        at, **_gateways(),
        registry_builder=_builder_returning(registry, universe), today=_TODAY,
    )

    assert service.sizer._n_symbols == 20
    assert service.strategy_params["top_n"] == 20


def test_fundamental_alias_when_today_missing():
    # registry 只有 D-3 行 → 装配后以 today 别名可查, meta 留痕滞后天数与源日
    universe = ["000001.SZ", "600000.SH"]
    d_minus_3 = _TODAY_DT - timedelta(days=3)
    registry = _registry_with(universe, d_minus_3)
    at = AutoTradeSettings(strategy="micro_value", symbols=[])

    service, _ = build_live_signal_service(
        at, **_gateways(),
        registry_builder=_builder_returning(registry, universe), today=_TODAY,
    )

    aliased = registry.get_all_at_date(_TODAY_DT)
    assert {s.symbol for s in aliased} == set(universe)
    assert service.assembly_meta.staleness_days == 3
    assert service.assembly_meta.fundamental_date == d_minus_3


def test_empty_universe_after_filter_raises_data_health():
    # 全宇宙无主板票 + mainboard_only=True → 过滤后为空, 拒绝装配
    universe = ["300001.SZ", "688001.SH"]
    registry = _registry_with(universe, _TODAY_DT)
    at = AutoTradeSettings(strategy="micro_value", symbols=[], mainboard_only=True)

    with pytest.raises(DataHealthError):
        build_live_signal_service(
            at, **_gateways(),
            registry_builder=_builder_returning(registry, universe), today=_TODAY,
        )


def test_stale_fundamental_raises_data_health():
    # 最近 fundamental 在 today-10d(>7 天) → 拒绝用陈腐数据决策
    universe = ["000001.SZ", "600000.SH"]
    registry = _registry_with(universe, _TODAY_DT - timedelta(days=10))
    at = AutoTradeSettings(strategy="micro_value", symbols=[])

    with pytest.raises(DataHealthError):
        build_live_signal_service(
            at, **_gateways(),
            registry_builder=_builder_returning(registry, universe), today=_TODAY,
        )
