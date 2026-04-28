from src.domain.market.value_objects.price_limit import calculate_price_limits, PriceLimit


def test_calculate_price_limits_main_board():
    limits = calculate_price_limits(10.0, board_multiplier=0.10)
    assert limits.limit_up == 11.00
    assert limits.limit_down == 9.00


def test_calculate_price_limits_star_board():
    limits = calculate_price_limits(50.0, board_multiplier=0.20)
    assert limits.limit_up == 60.00
    assert limits.limit_down == 40.00


def test_limit_up_prevents_buy():
    limits = PriceLimit(limit_up=11.00, limit_down=9.00)
    assert limits.can_buy(11.00) is False
    assert limits.can_buy(10.99) is True


def test_limit_down_prevents_sell():
    limits = PriceLimit(limit_up=11.00, limit_down=9.00)
    assert limits.can_sell(9.00) is False
    assert limits.can_sell(9.01) is True


def test_prices_within_limits_allow_trading():
    limits = PriceLimit(limit_up=11.00, limit_down=9.00)
    assert limits.can_buy(10.50) is True
    assert limits.can_sell(10.50) is True
