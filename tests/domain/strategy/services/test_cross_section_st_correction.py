"""截面名称按 as-of ST 状态修正(设计 0711-st-honesty §4.4)。

摘帽股历史期恢复 ST 前缀 → filter_st 可拦; 误标 ST 的历史期去前缀 → 不再误杀。
"""
from datetime import datetime

from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
from src.domain.market.value_objects.suspension import StockStatus, StockStatusRegistry
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.services.cross_section_builder import CrossSectionBuilder

D = datetime(2022, 5, 6)


def _setup(name="深科技"):
    reg = FundamentalRegistry()
    reg.add(FundamentalSnapshot(symbol="000021.SZ", date=D, name=name,
                                market_cap=1e9, list_date=datetime(2000, 1, 1)))
    bars = {"000021.SZ": Bar(symbol="000021.SZ", timeframe=Timeframe.DAY_1, timestamp=D,
                             open=10, high=10, low=10, close=10, volume=1000.0)}
    return reg, bars


def test_name_gains_st_prefix_when_registry_says_st():
    reg, bars = _setup()
    status = StockStatusRegistry()
    status.add(StockStatus(symbol="000021.SZ", date=D, is_st=True))
    [snap] = CrossSectionBuilder.build_cross_section(D, bars, reg, status_registry=status)
    assert snap.name == "ST深科技"


def test_name_loses_prefix_when_symbol_covered_but_clean_that_day():
    reg, bars = _setup(name="*ST深科")
    status = StockStatusRegistry()
    # 该股在册(别的日期有 ST 记录), 查询日无记录 = 确知该日非 ST → 剥前缀
    status.add(StockStatus(symbol="000021.SZ", date=datetime(2021, 1, 4), is_st=True))
    [snap] = CrossSectionBuilder.build_cross_section(D, bars, reg, status_registry=status)
    assert snap.name == "深科"


def test_uncovered_symbol_keeps_name_even_with_registry():
    """部分覆盖防线: registry 不认识的股票(如沪市未回填)保持原名——
    剥掉现状 ST 股的前缀会让 filter_st 放行, 比不修更糟。"""
    reg, bars = _setup(name="ST沪股")
    status = StockStatusRegistry()  # 空注册表 = 谁都不在册
    [snap] = CrossSectionBuilder.build_cross_section(D, bars, reg, status_registry=status)
    assert snap.name == "ST沪股"


def test_name_untouched_without_registry():
    reg, bars = _setup()
    [snap] = CrossSectionBuilder.build_cross_section(D, bars, reg)
    assert snap.name == "深科技"
