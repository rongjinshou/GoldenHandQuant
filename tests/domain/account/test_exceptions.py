import pytest
from src.domain.account.exceptions import (
    AccountError,
    InsufficientFundsError,
    PositionNotAvailableError,
    FrozenCashExceededError,
)


def test_account_error_is_base():
    with pytest.raises(AccountError):
        raise AccountError("test")


def test_insufficient_funds_error_carries_context():
    with pytest.raises(InsufficientFundsError) as exc_info:
        raise InsufficientFundsError(required=50000.0, available=30000.0, ticker="000001.SZ")

    assert exc_info.value.required == 50000.0
    assert exc_info.value.available == 30000.0
    assert exc_info.value.ticker == "000001.SZ"
    assert "50000" in str(exc_info.value)
    assert "30000" in str(exc_info.value)
    assert "000001.SZ" in str(exc_info.value)


def test_position_not_available_error_carries_context():
    with pytest.raises(PositionNotAvailableError) as exc_info:
        raise PositionNotAvailableError(ticker="000001.SZ", required=500, available=200)

    assert exc_info.value.ticker == "000001.SZ"
    assert exc_info.value.required == 500
    assert exc_info.value.available == 200


def test_frozen_cash_exceeded_error():
    with pytest.raises(FrozenCashExceededError) as exc_info:
        raise FrozenCashExceededError(requested=1000.0, frozen=500.0)

    assert exc_info.value.requested == 1000.0
    assert exc_info.value.frozen == 500.0
