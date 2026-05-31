from enum import StrEnum


class StrategyRating(StrEnum):
    """策略评级。"""

    A = "A"  # 优秀 (>= 80)
    B = "B"  # 良好 (60-79)
    C = "C"  # 一般 (40-59)
    D = "D"  # 差   (< 40)
