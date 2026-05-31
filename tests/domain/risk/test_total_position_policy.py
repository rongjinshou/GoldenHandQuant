from unittest.mock import MagicMock

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.risk.services.risk_policies.total_position_policy import TotalPositionPolicy
from src.domain.trade.value_objects.order_direction import OrderDirection


def _make_order(direction: OrderDirection, price: float = 10.0, volume: int = 100) -> MagicMock:
    order = MagicMock()
    order.direction = direction
    order.price = price
    order.volume = volume
    order.ticker = "600000.SH"
    return order


def test_buy_within_limit_passes():
    positions = [
        Position(account_id="t", ticker="600000.SH", total_volume=1000, average_cost=10.0),
    ]
    asset = Asset(account_id="t", total_asset=1_000_000)
    prices = {"600000.SH": 10.0}

    policy = TotalPositionPolicy(positions, asset, prices, max_ratio=0.80)
    order = _make_order(OrderDirection.BUY, price=10.0, volume=100)

    # Market value = 10000, new order = 1000, ratio = 11000 / 1000000 = 1.1%
    result = policy.check(order)
    assert result.passed is True


def test_buy_exceeding_limit_rejected():
    positions = [
        Position(account_id="t", ticker="600000.SH", total_volume=50000, average_cost=10.0),
    ]
    asset = Asset(account_id="t", total_asset=1_000_000)
    prices = {"600000.SH": 10.0}

    policy = TotalPositionPolicy(positions, asset, prices, max_ratio=0.80)
    order = _make_order(OrderDirection.BUY, price=10.0, volume=40000)

    # Market value = 500000, new order = 400000, total = 900000 / 1000000 = 90%
    result = policy.check(order)
    assert result.passed is False
    assert "exceeds limit" in result.reason


def test_sell_always_passes():
    positions = [
        Position(account_id="t", ticker="600000.SH", total_volume=50000, average_cost=10.0),
    ]
    asset = Asset(account_id="t", total_asset=1_000_000)
    prices = {"600000.SH": 10.0}

    policy = TotalPositionPolicy(positions, asset, prices, max_ratio=0.80)
    order = _make_order(OrderDirection.SELL, price=10.0, volume=40000)

    result = policy.check(order)
    assert result.passed is True


def test_zero_asset_buy_passes():
    """当总资产为 0 时，ratio 计算为 0，不触发限制。"""
    positions = []
    asset = Asset(account_id="t", total_asset=0)
    prices = {}

    policy = TotalPositionPolicy(positions, asset, prices, max_ratio=0.80)
    order = _make_order(OrderDirection.BUY, price=10.0, volume=100)

    result = policy.check(order)
    assert result.passed is True
