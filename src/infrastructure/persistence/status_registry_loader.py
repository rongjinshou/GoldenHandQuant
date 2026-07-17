"""区间 → StockStatusRegistry 稠密展开(设计 0711-st-honesty §4.1)。

registry 是精确日期索引(domain 不动): 区间∩回测窗口按交易日逐日展开。
量级: 窗口 ~1350 交易日 × 在册 ST 股 ~200 → ~20 万条内存条目, 可接受。
"""
import logging
from datetime import date, datetime, time

from src.domain.market.value_objects.suspension import StockStatus, StockStatusRegistry

logger = logging.getLogger(__name__)


def build_status_registry_from_db(
    db_path: str = "data/market.duckdb", *, start, end,
) -> StockStatusRegistry | None:
    """按库路径一步构建(11 处回测构造点的一行式入口); start/end 收 date 或 ISO 字符串。

    失败软着陆返回 None(库缺失/表空 → 调用方回退普通涨跌停口径, 与回填前行为一致)。
    """
    from src.infrastructure.persistence.market_data_store import MarketDataStore

    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)
    try:
        store = MarketDataStore(db_path, read_only=True)
    except Exception as exc:
        logger.warning("ST 状态注册表构建失败(库不可用: %s), 回退普通涨跌停口径", exc)
        return None
    try:
        return build_status_registry(store, start=start, end=end)
    finally:
        store.close()


def build_status_registry(store, *, start: date, end: date) -> StockStatusRegistry | None:
    """从 market.duckdb 的 st_status_periods 构建注册表; 表空返回 None(调用方回退旧行为)。"""
    periods = store.load_st_periods()
    if not periods:
        logger.warning(
            "st_status_periods 为空: ST 涨跌停幅度回退普通口径"
            "(先跑 scripts/backfill_st_status.py)"
        )
        return None
    trading_days = [d for d in store.trading_dates() if start <= d <= end]
    registry = StockStatusRegistry()
    for p in periods:
        p_end = p.end or date.max
        for d in trading_days:
            if p.start <= d < p_end:
                registry.add(StockStatus(
                    symbol=p.symbol,
                    date=datetime.combine(d, time.min),
                    is_st=p.label == "ST",
                    is_star_st=p.label == "*ST",
                ))
    return registry
