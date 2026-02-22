from src.domain.risk.simple_policy import SimpleRiskPolicy
from src.domain.trade.order import Order, OrderDirection
from src.domain.risk.policy import RiskCheckResult

class TestSimpleRiskPolicy:
    def test_check_should_pass_valid_order(self):
        # Arrange
        policy = SimpleRiskPolicy()
        order = Order(
            order_id="1", 
            account_id="acc", 
            ticker="600000.SH", 
            direction=OrderDirection.BUY, 
            price=10.0, 
            volume=100
        )
        
        # Act
        result = policy.check(order)
        
        # Assert
        assert result.passed is True
        assert result.reason == ""

    def test_check_should_reject_negative_price(self):
        # Arrange
        policy = SimpleRiskPolicy()
        # Order init prevents negative price, but we can manually set it to test policy independent of Order validation
        # However, Order class is strict. We will rely on Order init raising ValueError, 
        # but if we bypass it (e.g. mocking or modifying), policy should catch it.
        # Since Order is a dataclass, we can modify attributes after init.
        order = Order(
            order_id="1", 
            account_id="acc", 
            ticker="600000.SH", 
            direction=OrderDirection.BUY, 
            price=10.0, 
            volume=100
        )
        order.price = -1.0
        
        # Act
        result = policy.check(order)
        
        # Assert
        assert result.passed is False
        assert result.reason == "Price must be positive"

    def test_check_should_reject_zero_volume(self):
        # Arrange
        policy = SimpleRiskPolicy()
        order = Order(
            order_id="1", 
            account_id="acc", 
            ticker="600000.SH", 
            direction=OrderDirection.BUY, 
            price=10.0, 
            volume=100
        )
        order.volume = 0
        
        # Act
        result = policy.check(order)
        
        # Assert
        assert result.passed is False
        assert result.reason == "Volume must be positive"
