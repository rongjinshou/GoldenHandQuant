"""元数据只读端点 — 驱动前端表单（策略选择/因子勾选）。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/strategies")
def strategies() -> dict:
    from src.domain.strategy.registry import list_strategies

    return {"strategies": [
        {
            "name": cfg.name,
            "strategy_type": cfg.strategy_type,
            "description": cfg.description,
            "default_params": {k: v for k, v in (cfg.default_params or {}).items()
                               if not k.startswith("_")},
        }
        for cfg in list_strategies()
    ]}


@router.get("/factors")
def factors() -> dict:
    from src.domain.strategy.factor_test.factor_catalog import ALL_FACTORS

    items = [
        {
            "factor_id": f.factor_id,
            "name": f.name,
            "category": f.category,
            "expression": f.expression,
            "direction_note": f.direction_note,
            "evidence_strength": f.evidence_strength,
            "field_ready": f.field_ready,
            "priority": f.priority,
        }
        for f in ALL_FACTORS
    ]
    groups: dict[str, list[str]] = {}
    for item in items:
        groups.setdefault(item["priority"], []).append(item["factor_id"])
    return {"factors": items, "groups": groups}


@router.get("/gates")
def gates() -> dict:
    """判决闸门阈值 — D2 单一真相源端点。

    前端 gates.ts 从此端点获取阈值，不再硬编码。
    """
    from src.domain.strategy.factor_test.gates_config import get_all_gates

    return get_all_gates()
