"""因子验证判决 — 硬门槛判定(§7)。"""

from dataclasses import dataclass

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
    # Verdict
    passed: bool = False
    reasons: list[str] = None     # why passed / failed

    def __post_init__(self):
        if self.reasons is None:
            object.__setattr__(self, "reasons", [])


# --- Hard thresholds from §7 ---
IC_MIN = 0.02
IR_MIN = 0.30
MONOTONICITY_MIN = 0.4       # moderate; design doc says "高"
LONG_SHORT_MIN = 0.0         # must be positive after costs
OOS_IC_SIGN_FLIP = False     # IC sign must not flip OOS


def judge_factor(
    report: ScoredFactorTestReport,
    oos_report: ScoredFactorTestReport | None = None,
    factor_id: str = "",
    factor_name: str = "",
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

    # 1. IC 有效: |IC均值| >= 0.02, IR >= 0.3
    if abs(r.ic_mean) < IC_MIN:
        passed = False
        reasons.append(f"|IC|={abs(r.ic_mean):.4f} < {IC_MIN} (IC门槛)")
    else:
        reasons.append(f"|IC|={abs(r.ic_mean):.4f} >= {IC_MIN} ✓")

    if abs(r.ir) < IR_MIN:
        passed = False
        reasons.append(f"|IR|={abs(r.ir):.3f} < {IR_MIN} (IR门槛)")
    else:
        reasons.append(f"|IR|={abs(r.ir):.3f} >= {IR_MIN} ✓")

    # 2. IC 正率明显偏离 50%
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

    # 4. 扣成本后多空为正
    if r.long_short_return <= LONG_SHORT_MIN:
        passed = False
        reasons.append(f"多空收益={r.long_short_return:.2%} <= 0 (扣成本后为负)")
    else:
        reasons.append(f"多空收益={r.long_short_return:.2%} > 0 ✓")

    # 5. 样本外一致性 (if available)
    oos_ic = 0.0
    oos_ir = 0.0
    oos_ls = 0.0
    if oos_report is not None:
        oos_r = oos_report.report
        oos_ic = oos_r.ic_mean
        oos_ir = oos_r.ir
        oos_ls = oos_r.long_short_return

        # IC 符号不翻转
        if (r.ic_mean > 0 and oos_r.ic_mean < 0) or (r.ic_mean < 0 and oos_r.ic_mean > 0):
            passed = False
            reasons.append(f"样本外IC符号翻转: IS={r.ic_mean:.4f} vs OOS={oos_r.ic_mean:.4f}")
        else:
            reasons.append(f"样本外IC符号一致: IS={r.ic_mean:.4f} vs OOS={oos_r.ic_mean:.4f} ✓")

        # OOS 多空仍为正
        if oos_r.long_short_return <= 0:
            passed = False
            reasons.append(f"样本外多空收益={oos_r.long_short_return:.2%} <= 0")
        else:
            reasons.append(f"样本外多空收益={oos_r.long_short_return:.2%} ✓")

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
        passed=passed,
        reasons=reasons,
    )
