class AccountError(Exception):
    """账户领域基础异常。"""


class InsufficientFundsError(AccountError):
    """资金不足异常。

    Args:
        required: 所需金额。
        available: 可用金额。
        ticker: 相关标的代码（可选）。
    """

    def __init__(self, required: float, available: float, ticker: str = "") -> None:
        self.required = required
        self.available = available
        self.ticker = ticker
        msg = (
            f"Insufficient funds: required {required:.2f}, "
            f"available {available:.2f}"
        )
        if ticker:
            msg += f" (ticker: {ticker})"
        super().__init__(msg)


class PositionNotAvailableError(AccountError):
    """持仓不足异常。

    Args:
        ticker: 标的代码。
        required: 所需数量。
        available: 可用数量。
    """

    def __init__(self, ticker: str, required: int, available: int) -> None:
        self.ticker = ticker
        self.required = required
        self.available = available
        super().__init__(
            f"Position not available for {ticker}: "
            f"required {required}, available {available}"
        )


class FrozenCashExceededError(AccountError):
    """解冻金额超过已冻结金额异常。"""

    def __init__(self, requested: float, frozen: float) -> None:
        self.requested = requested
        self.frozen = frozen
        super().__init__(
            f"Cannot unfreeze more than frozen: "
            f"requested {requested:.2f}, frozen {frozen:.2f}"
        )
