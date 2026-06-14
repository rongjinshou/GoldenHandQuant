"""因子假设库 — P0/P1/P2 因子定义。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorHypothesis:
    """单条因子假设。"""
    factor_id: str          # e.g. "F01"
    name: str               # e.g. "小市值"
    category: str           # e.g. "规模"
    expression: str         # DSL expression, e.g. "0 - log(market_cap)"
    direction_note: str     # e.g. "高=小盘=预期跑赢"
    evidence_strength: str  # "强" | "中强" | "中" | "弱"
    field_ready: bool       # True if StockSnapshot field is populated
    priority: str           # "P0" | "P1" | "P2"


# P0 因子: 字段已就绪 · 证据强 · 个人优势区
P0_FACTORS: list[FactorHypothesis] = [
    FactorHypothesis(
        factor_id="F01", name="小市值", category="规模",
        expression="0 - log(market_cap)",
        direction_note="高=小盘=预期跑赢；raw log(market_cap) IC为负",
        evidence_strength="强", field_ready=True, priority="P0",
    ),
    FactorHypothesis(
        factor_id="F02", name="短期反转", category="量价",
        expression="0 - return_20d",
        direction_note="高=过去跌得多=预期反弹；raw return_20d IC为负",
        evidence_strength="强", field_ready=True, priority="P0",
    ),
    FactorHypothesis(
        factor_id="F03", name="换手率", category="流动性/情绪",
        expression="0 - avg_turnover_20d",
        direction_note="高=低换手=预期跑赢；raw换手IC为负",
        evidence_strength="强", field_ready=True, priority="P0",
    ),
    FactorHypothesis(
        factor_id="F04", name="低波动", category="风险",
        expression="0 - volatility_20d",
        direction_note="高=低波=预期跑赢；raw波动IC为负",
        evidence_strength="中强", field_ready=True, priority="P0",
    ),
    FactorHypothesis(
        factor_id="F05", name="抗博彩/低偏度", category="行为",
        expression="0 - skewness_20d",
        direction_note="高=低偏度=预期跑赢；raw偏度IC为负",
        evidence_strength="中", field_ready=True, priority="P0",
    ),
]

# P1 因子: 证据中 / 需补一步
P1_FACTORS: list[FactorHypothesis] = [
    FactorHypothesis(
        factor_id="F06", name="Amihud非流动性", category="流动性",
        expression="illiquidity_20d",
        direction_note="高=非流动性高=预期跑赢(流动性溢价)",
        evidence_strength="中", field_ready=True, priority="P1",
    ),
    FactorHypothesis(
        factor_id="F07", name="BP账面市值比", category="价值",
        expression="1 / pb_ratio",
        direction_note="高BP=便宜=预期跑赢；剔除PB<=0",
        evidence_strength="中", field_ready=True, priority="P1",
    ),
    FactorHypothesis(
        factor_id="F08", name="EP盈利市值比", category="价值",
        expression="1 / pe_ratio",
        direction_note="高EP=便宜=预期跑赢；处理PE<0",
        evidence_strength="中", field_ready=True, priority="P1",
    ),
    FactorHypothesis(
        factor_id="F09", name="ROE质量", category="质量",
        expression="roe_ttm",
        direction_note="高ROE=高质量=预期跑赢",
        evidence_strength="中", field_ready=True, priority="P1",
    ),
    FactorHypothesis(
        factor_id="F10", name="毛利率", category="质量",
        expression="gross_margin",
        direction_note="高毛利率=预期跑赢(Novy-Marx)",
        # 2026-06-11 夜判定: 基本面管道无 gross_margin 字段, 全链路恒 0,
        # run 20260611-192433 的 F10 判决无效。补字段前不得纳入批次。
        evidence_strength="中", field_ready=False, priority="P1",
    ),
]

# P2 因子: 对照 / 备选
P2_FACTORS: list[FactorHypothesis] = [
    FactorHypothesis(
        factor_id="F11", name="中期动量(对照)", category="量价",
        expression="return_60d",
        direction_note="A股动量弱/不稳，作反转对照",
        evidence_strength="弱", field_ready=True, priority="P2",
    ),
]

# P3 因子: 第二-edge 研究候选(多因子交互/质量/价值×成长, 仅用已就绪字段)。
# 全部 long_only + 中性化(剥离 size/reversal)检验是否为独立于 F01 的真 edge。2026-06-14 加入。
P3_FACTORS: list[FactorHypothesis] = [
    FactorHypothesis(
        factor_id="F20", name="价值×成长(EP×净利增速)", category="价值",
        expression="rank(1 / pe_ratio) * rank(earnings_growth)",
        direction_note="高=便宜且高增=GARP, 预期跑赢; 交互避免低PE垃圾/高成长泡沫",
        evidence_strength="中", field_ready=True, priority="P3",
    ),
    FactorHypothesis(
        factor_id="F21", name="价值×成长(EP×营收增速)", category="价值",
        expression="rank(1 / pe_ratio) * rank(revenue_growth)",
        direction_note="高=便宜且营收扩张, 预期跑赢",
        evidence_strength="中", field_ready=True, priority="P3",
    ),
    FactorHypothesis(
        factor_id="F22", name="质量×低波", category="质量",
        expression="rank(0 - volatility_20d) * rank(roe_ttm)",
        direction_note="高=低波且高ROE=防御型质量, 预期跑赢; 给 F04 低波加质量过滤",
        evidence_strength="中", field_ready=True, priority="P3",
    ),
    FactorHypothesis(
        factor_id="F23", name="成长稳定性", category="成长",
        expression="rank(earnings_growth) + rank(revenue_growth)",
        direction_note="高=利润与营收双增=质量成长, 预期跑赢",
        evidence_strength="中", field_ready=True, priority="P3",
    ),
    FactorHypothesis(
        factor_id="F24", name="经营现金流收益率", category="价值",
        expression="ocf_ttm / market_cap",
        direction_note="高=现金流相对市值高=便宜且盈利质量真, 预期跑赢",
        evidence_strength="中", field_ready=True, priority="P3",
    ),
    FactorHypothesis(
        factor_id="F25", name="低偏度×低波", category="风险",
        expression="zscore(skewness_20d) + zscore(0 - volatility_20d)",
        direction_note="高=低尾部博彩且低波=抗风险, 预期跑赢(给 F05 加低波)",
        evidence_strength="弱", field_ready=True, priority="P3",
    ),
    FactorHypothesis(
        factor_id="F26", name="动量残差(季-月)", category="量价",
        expression="return_60d - return_20d",
        direction_note="高=季动量强而近月未透支, 期限结构残差",
        evidence_strength="弱", field_ready=True, priority="P3",
    ),
    FactorHypothesis(
        factor_id="F27", name="质量×价值(ROE×BP)", category="质量",
        expression="rank(roe_ttm) * rank(1 / pb_ratio)",
        direction_note="高=高ROE且破净便宜=GARP/隐藏价值, 预期跑赢",
        evidence_strength="中", field_ready=True, priority="P3",
    ),
]

# P4 因子: 多因子组合(单因子已挖尽, F20/F21/F22/F27 中性化残差 IC 正 → 等权合成检验可投 edge)。2026-06-14 加入。
P4_FACTORS: list[FactorHypothesis] = [
    FactorHypothesis(
        factor_id="F30", name="多因子组合-zscore等权", category="复合",
        expression=(
            "zscore(rank(1 / pe_ratio) * rank(earnings_growth))"
            " + zscore(rank(1 / pe_ratio) * rank(revenue_growth))"
            " + zscore(rank(0 - volatility_20d) * rank(roe_ttm))"
            " + zscore(rank(roe_ttm) * rank(1 / pb_ratio))"
        ),
        direction_note="F20/F21/F22/F27 各 zscore 标准化后等权相加; 检验合成是否构成可投多因子 edge",
        evidence_strength="中", field_ready=True, priority="P4",
    ),
    FactorHypothesis(
        factor_id="F31", name="多因子组合-rank积等权", category="复合",
        expression=(
            "rank(1 / pe_ratio) * rank(earnings_growth)"
            " + rank(1 / pe_ratio) * rank(revenue_growth)"
            " + rank(0 - volatility_20d) * rank(roe_ttm)"
            " + rank(roe_ttm) * rank(1 / pb_ratio)"
        ),
        direction_note="同上, 但各 rank 积([0,1])直接等权相加(对量纲更稳健的对照)",
        evidence_strength="中", field_ready=True, priority="P4",
    ),
]

ALL_FACTORS: list[FactorHypothesis] = (
    P0_FACTORS + P1_FACTORS + P2_FACTORS + P3_FACTORS + P4_FACTORS
)

FACTOR_BY_ID: dict[str, FactorHypothesis] = {f.factor_id: f for f in ALL_FACTORS}
FACTOR_BY_NAME: dict[str, FactorHypothesis] = {f.name: f for f in ALL_FACTORS}


def resolve_factors(factor_str: str) -> list[FactorHypothesis]:
    """解析逗号分隔的因子标识符( ID 或名称)，返回 FactorHypothesis 列表。

    支持:
      - "F01,F02,F03"  (ID)
      - "小市值,短期反转"  (名称)
      - "P0"  (优先级组)
      - "all"  (全部)
    """
    if factor_str.strip().lower() == "all":
        return list(ALL_FACTORS)
    if factor_str.strip().upper() in ("P0", "P1", "P2", "P3", "P4"):
        priority = factor_str.strip().upper()
        return [f for f in ALL_FACTORS if f.priority == priority]

    results: list[FactorHypothesis] = []
    for token in factor_str.split(","):
        token = token.strip()
        if not token:
            continue
        # Try ID first
        f = FACTOR_BY_ID.get(token.upper())
        if f is None:
            # Try name
            f = FACTOR_BY_NAME.get(token)
        if f is None:
            raise ValueError(f"Unknown factor: {token!r}. Use factor ID (F01) or name (小市值).")
        results.append(f)
    return results
