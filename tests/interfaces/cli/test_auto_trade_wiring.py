"""R3c: auto-trade 装配按策略类型选 sizer / fundamental_registry。

截面策略(micro_value)必须拿到 EqualWeightSizer + DuckDB 同源 fundamental_registry,
否则决策核心 universe 恒空、F01 信号静默为零(R3c 修复的洞)。
"""
from datetime import date, timedelta
from unittest.mock import Mock

from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer
from src.infrastructure.config.settings import AutoTradeSettings
from src.interfaces.cli._auto_trade_wiring import build_live_signal_service


def _gateways() -> dict:
    return {
        "market_gateway": Mock(),
        "account_gateway": Mock(),
        "trade_gateway": Mock(),
    }


def test_cross_section_wires_equal_weight_and_fundamental_registry():
    # Arrange: micro_value 是 cross_section, default top_n=9
    registry = FundamentalRegistry()
    captured: dict = {}

    def fake_builder(fetcher_type, start, end):
        captured["args"] = (fetcher_type, start, end)
        return registry, ["000001.SZ", "000002.SZ", "600000.SH"]

    at = AutoTradeSettings(strategy="micro_value", symbols=[])

    # Act
    service, symbols = build_live_signal_service(
        at, **_gateways(), registry_builder=fake_builder, today=date(2026, 6, 30),
    )

    # Assert: 截面 → 等权 sizer(n=top_n) + 注入 registry + 全宇宙
    assert isinstance(service.sizer, EqualWeightSizer)
    assert service.sizer._n_symbols == 9
    assert service.fundamental_registry is registry
    assert symbols == ["000001.SZ", "000002.SZ", "600000.SH"]
    # DuckDB 同源, 3 年回溯窗口至 today
    assert captured["args"][0] == "DuckDBHistoryDataFetcher"
    assert captured["args"][2] == "2026-06-30"
    assert captured["args"][1] == (date(2026, 6, 30) - timedelta(days=1095)).isoformat()


def test_cross_section_intersects_configured_symbols():
    # 显式配 at.symbols → 与 DuckDB 宇宙取交集(允许缩小到受限宇宙)
    registry = FundamentalRegistry()

    def fake_builder(fetcher_type, start, end):
        return registry, ["000001.SZ", "000002.SZ"]

    at = AutoTradeSettings(strategy="micro_value", symbols=["000001.SZ", "999999.XX"])
    _, symbols = build_live_signal_service(
        at, **_gateways(), registry_builder=fake_builder,
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
