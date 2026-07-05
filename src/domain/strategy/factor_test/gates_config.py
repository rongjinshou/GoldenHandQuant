"""判决闸门阈值 — 单一真相源 (Single Source of Truth)。

解决债 D2: 原先 verdict.py、gates.ts、CLI 输出三处独立硬编码。
此后修改门槛只改此处，Python 端直接 import，前端通过 /api/meta/gates 端点获取。
"""

from __future__ import annotations

# ── 多空记分牌门槛 ──
IC_MIN = 0.02           # IC 门槛 / 方向
IR_MIN = 0.30           # IC-IR 门槛
IC_POSITIVE_RATE_MIN = 0.52  # IC 正率门槛
MONOTONICITY_MIN = 0.6  # 分层单调门槛 (5层时 ≥3/4 相邻递增)
LONG_SHORT_MIN = 0.0    # 多空收益须为正

# ── long-only 记分牌门槛 ──
EXCESS_IR_MIN = 0.50            # Top 超额年化信息比
EXCESS_POSITIVE_RATE_MIN = 0.52 # Top 超额正率
TOP_EXCESS_MIN = 0.0            # Top 层超额扣成本后须为正

# ── OOS 一致性 ──
OOS_IC_SIGN_FLIP = False  # IC 符号不可翻转


def get_all_gates() -> dict[str, float | bool]:
    """返回所有闸门阈值，供 API 端点序列化。"""
    return {
        "ic_min": IC_MIN,
        "ir_min": IR_MIN,
        "ic_positive_rate_min": IC_POSITIVE_RATE_MIN,
        "monotonicity_min": MONOTONICITY_MIN,
        "long_short_min": LONG_SHORT_MIN,
        "excess_ir_min": EXCESS_IR_MIN,
        "excess_positive_rate_min": EXCESS_POSITIVE_RATE_MIN,
        "top_excess_min": TOP_EXCESS_MIN,
        "oos_ic_sign_flip": OOS_IC_SIGN_FLIP,
    }
