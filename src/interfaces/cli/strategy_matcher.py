"""自然语言到策略的关键词匹配模块。"""

from src.domain.strategy.registry import list_strategies

# 关键词 → 策略注册名
KEYWORD_MAP: dict[str, list[str]] = {
    "micro_value": ["微盘", "小盘", "微盘价值", "小市值", "壳价值"],
    "multi_factor": ["多因子", "因子", "基本面", "价值+质量", "综合选股", "量化选股"],
    "dual_ma": ["双均线", "均线", "金叉", "死叉", "趋势跟踪", "dual_ma", "ma"],
}


def match_strategy(idea: str) -> str | None:
    """从自然语言描述匹配策略名。返回 None 表示无法匹配。"""
    idea_lower = idea.lower()
    for strategy_name, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in idea_lower:
                return strategy_name
    return None


def format_available_strategies() -> str:
    """格式化可用策略列表，用于匹配失败时的提示。"""
    strategies = list_strategies()
    lines = [f"  {i}. {s.name:<20} -- {s.description}" for i, s in enumerate(strategies, 1)]
    return "\n".join(lines)
