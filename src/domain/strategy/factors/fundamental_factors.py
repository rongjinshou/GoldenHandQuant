"""基本面因子集合。

每个因子从 StockSnapshot 中提取一个基本面指标的原始值，
供 FactorScorer.percentile_rank 打分使用。
"""

from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class ROAFactor:
    """ROA (总资产收益率) 因子 — 高 ROA 得高分。"""

    name = "roa"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.roa_ttm
            for s in snapshots
            if s.roa_ttm is not None
        }


class GrossMarginFactor:
    """毛利率因子 — 高毛利率得高分。"""

    name = "gross_margin"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.gross_margin
            for s in snapshots
            if s.gross_margin is not None
        }


class NetMarginFactor:
    """净利率因子 — 高净利率得高分。"""

    name = "net_margin"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.net_margin
            for s in snapshots
            if s.net_margin is not None
        }


class AssetTurnoverFactor:
    """总资产周转率因子 — 高周转率得高分。"""

    name = "asset_turnover"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.asset_turnover
            for s in snapshots
            if s.asset_turnover is not None and s.asset_turnover > 0
        }


class CurrentRatioFactor:
    """流动比率因子 — 高流动比率得高分。"""

    name = "current_ratio"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.current_ratio
            for s in snapshots
            if s.current_ratio is not None and s.current_ratio > 0
        }


class DebtToEquityFactor:
    """资产负债率因子 — 低负债率得高分 (invert=True)。"""

    name = "debt_to_equity"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.debt_to_equity
            for s in snapshots
            if s.debt_to_equity is not None and s.debt_to_equity > 0
        }


class PCFRatioFactor:
    """市现率因子 — 低 PCF 得高分 (invert=True)。"""

    name = "pcf_ratio"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.pcf_ratio
            for s in snapshots
            if s.pcf_ratio is not None and s.pcf_ratio > 0
        }


class PSRatioFactor:
    """市销率因子 — 低 PS 得高分 (invert=True)。"""

    name = "ps_ratio"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.ps_ratio
            for s in snapshots
            if s.ps_ratio is not None and s.ps_ratio > 0
        }


class DividendYieldFactor:
    """股息率因子 — 高股息率得高分。"""

    name = "dividend_yield"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.dividend_yield
            for s in snapshots
            if s.dividend_yield is not None and s.dividend_yield > 0
        }


class EarningsGrowthFactor:
    """盈利增长因子 — 高增长得高分（允许负增长）。"""

    name = "earnings_growth"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.earnings_growth
            for s in snapshots
            if s.earnings_growth is not None
        }
