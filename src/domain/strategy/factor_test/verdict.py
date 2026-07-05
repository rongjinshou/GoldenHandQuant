"""因子验证判决 — 硬门槛判定(§7)。

债 D2 修复: 闸门阈值统一从 gates_config.py 读取(单一真相源)。
"""

from dataclasses import dataclass

from src.domain.strategy.factor_test.gates_config import (
    EXCESS_IR_MIN,
    EXCESS_POSITIVE_RATE_MIN,
    IC_MIN,
    IR_MIN,
    LONG_SHORT_MIN,
    MONOTONICITY_MIN,
    TOP_EXCESS_MIN,
)
from src.domain.strategy.factor_test.report import ScoredFactorTestReport


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorVerdict:
    """单因子判决结果。"""
    factor_id: str
    factor_name: str
    expression: str
    # In-sample metrics
    ic_mean: float
    ir: float
    ic_positive_rate: float
    monotonicity_score: float
    long_short_return: float
    score: float
    grade: str
    # Out-of-sample metrics (empty dict if no split)
    oos_ic_mean: float = 0.0
    oos_ir: float = 0.0
    oos_long_short_return: float = 0.0
    # --- long-only 记分牌 ---
    objective: str = "long_short"
    top_excess_return: float = 0.0
    oos_top_excess_return: float = 0.0
    excess_ir: float = 0.0
    excess_positive_rate: float = 0.0
    # Neutralized (orthogonalized) IC — §7.5
    neutralized_ic: float = 0.0
    # Verdict
    passed: bool = False
    reasons: list[str] = None     # why passed / failed

    def __post_init__(self):
        if self.reasons is None:
            object.__setattr__(self, "reasons", [])




def judge_factor(
    report: ScoredFactorTestReport,
    oos_report: ScoredFactorTestReport | None = None,
    factor_id: str = "",
    factor_name: str = "",
    neutralized_ic: float | None = None,
    objective: str = "long_short",
) -> FactorVerdict:
    """Apply §7 hard thresholds to a factor test report.

    Args:
        report: In-sample scored report.
        oos_report: Out-of-sample scored report (None = no split).
        factor_id: Factor ID for labeling.
        factor_name: Factor name for labeling.

    Returns:
        FactorVerdict with pass/fail and reasons.
    """
    r = report.report
    reasons: list[str] = []
    passed = True
    long_only = objective == "long_only"

    # 1. IC 有效: 因子已定向(高=预期跑赢), IC 须为正且 >= 0.02, IR >= 0.3
    #    (用有符号判定, 不用 abs: 负 IC = 方向错, 应判负)
    if r.ic_mean < IC_MIN:
        passed = False
        reasons.append(f"IC={r.ic_mean:.4f} < {IC_MIN} (IC门槛/方向)")
    else:
        reasons.append(f"IC={r.ic_mean:.4f} >= {IC_MIN} ✓")

    # 稳定性: long_short→IC-IR; long_only→Top 超额信息比
    if long_only:
        if r.excess_ir < EXCESS_IR_MIN:
            passed = False
            reasons.append(f"超额信息比={r.excess_ir:.2f} < {EXCESS_IR_MIN} (稳定性不足)")
        else:
            reasons.append(f"超额信息比={r.excess_ir:.2f} >= {EXCESS_IR_MIN} ✓")
    else:
        if r.ir < IR_MIN:
            passed = False
            reasons.append(f"IR={r.ir:.3f} < {IR_MIN} (IR门槛)")
        else:
            reasons.append(f"IR={r.ir:.3f} >= {IR_MIN} ✓")

    # 2. 一致性: long_short→IC 正率; long_only→Top 超额正率
    if long_only:
        if r.excess_positive_rate < EXCESS_POSITIVE_RATE_MIN:
            passed = False
            reasons.append(f"超额正率={r.excess_positive_rate:.1%} < {EXCESS_POSITIVE_RATE_MIN:.0%} (偏离不足)")
        else:
            reasons.append(f"超额正率={r.excess_positive_rate:.1%} ✓")
    else:
        if r.ic_positive_rate < 0.52:
            passed = False
            reasons.append(f"IC正率={r.ic_positive_rate:.1%} < 52% (偏离不足)")
        else:
            reasons.append(f"IC正率={r.ic_positive_rate:.1%} ✓")

    # 3. 分层单调
    if r.monotonicity_score < MONOTONICITY_MIN:
        passed = False
        reasons.append(f"单调性={r.monotonicity_score:.2f} < {MONOTONICITY_MIN} (单调性不足)")
    else:
        reasons.append(f"单调性={r.monotonicity_score:.2f} ✓")

    # 4. 变现(扣成本后为正): long_short→多空价差; long_only→Top 层超额
    if long_only:
        if r.top_excess_return <= TOP_EXCESS_MIN:
            passed = False
            reasons.append(f"Top超额={r.top_excess_return:.2%} <= 0 (扣成本后为负)")
        else:
            reasons.append(f"Top超额={r.top_excess_return:.2%} > 0 ✓")
    else:
        if r.long_short_return <= LONG_SHORT_MIN:
            passed = False
            reasons.append(f"多空收益={r.long_short_return:.2%} <= 0 (扣成本后为负)")
        else:
            reasons.append(f"多空收益={r.long_short_return:.2%} > 0 ✓")

    # 5. 样本外一致性 (if available)
    oos_ic = 0.0
    oos_ir = 0.0
    oos_ls = 0.0
    oos_te = 0.0
    if oos_report is not None:
        oos_r = oos_report.report
        oos_ic = oos_r.ic_mean
        oos_ir = oos_r.ir
        oos_ls = oos_r.long_short_return
        oos_te = oos_r.top_excess_return

        # IC 符号不翻转 (两种记分牌通用)
        if (r.ic_mean > 0 and oos_r.ic_mean < 0) or (r.ic_mean < 0 and oos_r.ic_mean > 0):
            passed = False
            reasons.append(f"样本外IC符号翻转: IS={r.ic_mean:.4f} vs OOS={oos_r.ic_mean:.4f}")
        else:
            reasons.append(f"样本外IC符号一致: IS={r.ic_mean:.4f} vs OOS={oos_r.ic_mean:.4f} ✓")

        # 样本外变现仍为正 (绑定闸): long_short→多空; long_only→Top 超额
        if long_only:
            if oos_te <= 0:
                passed = False
                reasons.append(f"样本外Top超额={oos_te:.2%} <= 0")
            else:
                reasons.append(f"样本外Top超额={oos_te:.2%} ✓")
        else:
            if oos_ls <= 0:
                passed = False
                reasons.append(f"样本外多空收益={oos_ls:.2%} <= 0")
            else:
                reasons.append(f"样本外多空收益={oos_ls:.2%} ✓")

    # 6. 正交化增量(§7.5): 剥离市值/反转后 IC 须仍过门槛
    # (规模/量价因子本身是控制变量, 由调用方传 None 跳过)
    if neutralized_ic is not None:
        if abs(neutralized_ic) < IC_MIN:
            passed = False
            reasons.append(f"中性化后|IC|={abs(neutralized_ic):.4f} < {IC_MIN} (疑似市值/反转影子)")
        else:
            reasons.append(f"中性化后|IC|={abs(neutralized_ic):.4f} >= {IC_MIN} (有增量) ✓")

    return FactorVerdict(
        factor_id=factor_id,
        factor_name=factor_name,
        expression=r.expression,
        ic_mean=r.ic_mean,
        ir=r.ir,
        ic_positive_rate=r.ic_positive_rate,
        monotonicity_score=r.monotonicity_score,
        long_short_return=r.long_short_return,
        score=report.score,
        grade=report.grade,
        oos_ic_mean=oos_ic,
        oos_ir=oos_ir,
        oos_long_short_return=oos_ls,
        objective=objective,
        top_excess_return=r.top_excess_return,
        oos_top_excess_return=oos_te,
        excess_ir=r.excess_ir,
        excess_positive_rate=r.excess_positive_rate,
        neutralized_ic=neutralized_ic if neutralized_ic is not None else 0.0,
        passed=passed,
        reasons=reasons,
    )
