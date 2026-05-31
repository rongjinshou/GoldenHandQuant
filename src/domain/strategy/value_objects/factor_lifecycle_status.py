"""因子生命周期状态值对象。"""

from enum import StrEnum


class FactorLifecycleStatus(StrEnum):
    """因子生命周期状态。

    流转路径:
    DISCOVERED → TESTING → VALIDATED → ACTIVE → DECAYED → RETIRED
                                      ↑          |
                                      +----------+  (可重新验证后激活)
    """

    DISCOVERED = "DISCOVERED"    # 刚被挖掘，待检验
    TESTING = "TESTING"          # IC/分层回测检验中
    VALIDATED = "VALIDATED"      # 检验通过，待入库上线
    ACTIVE = "ACTIVE"            # 已上线使用
    DECAYED = "DECAYED"          # 因子衰减，暂停使用
    RETIRED = "RETIRED"          # 已退役，终态
