from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class StressScenario:
    """压力测试场景定义。

    Attributes:
        name: 场景名称。
        scenario_type: "historical" 或 "hypothetical"。
        description: 场景描述。
        date_range: 历史场景的时间区间（假设场景为空）。
        shock_params: 假设场景的冲击参数（历史场景为空）。
    """

    name: str
    scenario_type: str
    description: str
    date_range: tuple[datetime, datetime] | None = None
    shock_params: dict[str, float] = field(default_factory=dict)


def get_historical_scenarios() -> list[StressScenario]:
    """返回 A 股 4 个历史极端行情场景。"""
    return [
        StressScenario(
            name="2015 股灾",
            scenario_type="historical",
            description="杠杆崩盘、流动性枯竭、千股跌停，基准跌幅 -43%",
            date_range=(datetime(2015, 6, 12), datetime(2015, 7, 9)),
        ),
        StressScenario(
            name="2018 熊市",
            scenario_type="historical",
            description="贸易摩擦、去杠杆、持续阴跌，基准跌幅 -30%",
            date_range=(datetime(2018, 1, 29), datetime(2018, 12, 28)),
        ),
        StressScenario(
            name="2020 新冠",
            scenario_type="historical",
            description="外部冲击、全球联动、快速下跌后 V 型反弹，基准跌幅 -16%",
            date_range=(datetime(2020, 1, 20), datetime(2020, 3, 23)),
        ),
        StressScenario(
            name="2022 调整",
            scenario_type="historical",
            description="俄乌冲突、疫情反复、地产风险，基准跌幅 -27%",
            date_range=(datetime(2022, 1, 4), datetime(2022, 10, 31)),
        ),
    ]
