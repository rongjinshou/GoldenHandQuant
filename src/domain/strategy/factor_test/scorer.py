"""因子有效性综合评分器 (0-100)。"""

from src.domain.strategy.factor_test.report import FactorTestReport


def _linear_score(value: float, low_threshold: float, high_threshold: float) -> float:
    """线性插值评分：value 在 [low, high] 之间映射到 [0, 1]。"""
    if value >= high_threshold:
        return 1.0
    if value <= low_threshold:
        return 0.0
    return (value - low_threshold) / (high_threshold - low_threshold)


def _grade(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "D"


class FactorScorer:
    """综合评分器：根据 IC/IR/分层收益/单调性/衰减计算 0-100 评分。"""

    def score(
        self, report: FactorTestReport, objective: str = "long_short"
    ) -> tuple[float, str, list[str]]:
        """返回 (score_0_100, grade_ABCD, reasons)。

        objective='long_only' 时变现项(20%)从多空收益切到 Top 层超额。
        """
        reasons: list[str] = []

        # 1. IC 均值 (30%): |IC| >= 0.05 → 满分, |IC| < 0.01 → 0 分
        ic_abs = abs(report.ic_mean)
        ic_part = _linear_score(ic_abs, 0.01, 0.05) * 30
        reasons.append(f"IC 均值 (30%): {ic_part:.0f}/30  |IC|={ic_abs:.4f}")

        # 2. IR (25%): |IR| >= 0.5 → 满分, |IR| < 0.1 → 0 分
        ir_abs = abs(report.ir)
        ir_part = _linear_score(ir_abs, 0.1, 0.5) * 25
        reasons.append(f"IR (25%): {ir_part:.0f}/25  |IR|={ir_abs:.3f}")

        # 3. 变现 (20%): long_short→多空 0.03→0.15; long_only→Top 超额 0.0→0.05
        if objective == "long_only":
            realize_part = _linear_score(report.top_excess_return, 0.0, 0.05) * 20
            reasons.append(f"Top超额 (20%): {realize_part:.0f}/20  年化 {report.top_excess_return:.1%}")
        else:
            realize_part = _linear_score(report.long_short_return, 0.03, 0.15) * 20
            reasons.append(f"多空收益 (20%): {realize_part:.0f}/20  年化 {report.long_short_return:.1%}")

        # 4. 单调性 (15%): score 1.0 → 满分, score 0 → 0 分
        mono_part = report.monotonicity_score * 15
        reasons.append(f"单调性 (15%): {mono_part:.0f}/15  得分 {report.monotonicity_score:.2f}")

        # 5. IC 衰减 (10%): 20 日 IC 保持 > 50% 的 1 日 IC → 满分
        decay_part = 0.0
        if len(report.decay_periods) >= 2 and len(report.decay_ics) >= 2:
            ic_1d = abs(report.decay_ics[0]) if report.decay_ics[0] != 0 else 1e-9
            # 找 20 日 IC
            ic_20d = 0.0
            for i, p in enumerate(report.decay_periods):
                if p == 20 and i < len(report.decay_ics):
                    ic_20d = abs(report.decay_ics[i])
                    break
            retention = ic_20d / ic_1d if ic_1d > 0 else 0
            decay_part = _linear_score(retention, 0.0, 0.5) * 10
            reasons.append(f"衰减 (10%): {decay_part:.0f}/10  20日IC保留 {retention:.0%}")
        else:
            reasons.append(f"衰减 (10%): {decay_part:.0f}/10  数据不足")

        total = ic_part + ir_part + realize_part + mono_part + decay_part
        total = min(100.0, max(0.0, total))
        return total, _grade(total), reasons
