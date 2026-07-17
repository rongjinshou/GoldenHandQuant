from src.domain.market.value_objects.price_limit import PriceLimit, calculate_price_limits


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


def test_get_price_limit_ratio_by_board():
    from src.domain.market.value_objects.price_limit import get_price_limit_ratio
    assert get_price_limit_ratio("600000.SH") == 0.10   # 沪主板
    assert get_price_limit_ratio("000001.SZ") == 0.10   # 深主板
    assert get_price_limit_ratio("688001.SH") == 0.20   # 科创板
    assert get_price_limit_ratio("300750.SZ") == 0.20   # 创业板
    assert get_price_limit_ratio("830799.BJ") == 0.30   # 北交所
    assert get_price_limit_ratio("000001.SZ", is_st=True) == 0.05  # ST
