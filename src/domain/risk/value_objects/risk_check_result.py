from dataclasses import dataclass
from typing import Self

@dataclass(slots=True, kw_only=True)
class RiskCheckResult:
    """风控检查结果。

    Attributes:
        passed: 是否通过。
        reason: 拒绝原因 (若未通过)。
    """

    passed: bool
    reason: str = ""

    @classmethod
    def pass_check(cls) -> Self:
        return cls(passed=True)

    @classmethod
    def reject(cls, reason: str) -> Self:
        return cls(passed=False, reason=reason)
