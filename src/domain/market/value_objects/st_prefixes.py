"""ST 风险警示名称前缀 — 单一事实源。

消费方: domain/strategy filter_st(选股过滤)、domain/trade check_st_name(实时闸)、
回测截面名称修正(0711-st-honesty §4.4)。判定与剥除均按最长优先。
"""

ST_NAME_PREFIXES: tuple[str, ...] = ("S*ST", "*ST", "SST", "ST")


def is_st_name(name: str) -> bool:
    return name.upper().startswith(ST_NAME_PREFIXES)


def correct_st_name(name: str, *, is_st: bool) -> str:
    """按 as-of ST 状态修正名称前缀(名称仅作 ST 布尔语义载体)。"""
    if is_st:
        return name if is_st_name(name) else f"ST{name}"
    upper = name.upper()
    for prefix in ST_NAME_PREFIXES:
        if upper.startswith(prefix):
            return name[len(prefix):]
    return name
