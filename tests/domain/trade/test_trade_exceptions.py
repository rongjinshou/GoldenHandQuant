import pytest
from src.domain.trade.exceptions import TradeError, MarketClosedError, OrderValidationError


def test_market_closed_error_with_ticker():
    with pytest.raises(MarketClosedError) as exc_info:
        raise MarketClosedError(ticker="000001.SZ", detail="Trading hours: 9:30-15:00")

    assert exc_info.value.ticker == "000001.SZ"
    assert "Market is closed" in str(exc_info.value)
    assert "000001.SZ" in str(exc_info.value)
    assert "9:30-15:00" in str(exc_info.value)


def test_order_validation_error_carries_order_id():
    with pytest.raises(OrderValidationError) as exc_info:
        raise OrderValidationError(reason="volume must be multiple of 100", order_id="ORD_001")

    assert exc_info.value.reason == "volume must be multiple of 100"
    assert exc_info.value.order_id == "ORD_001"
