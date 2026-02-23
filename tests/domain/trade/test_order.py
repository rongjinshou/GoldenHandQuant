import pytest
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_status import OrderStatus
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType

class TestOrder:
    def test_init_should_validate_volume_and_price(self):
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Order volume must be positive"):
            Order(
                order_id="1", 
                account_id="acc", 
                ticker="600000.SH", 
                direction=OrderDirection.BUY, 
                price=10.0, 
                volume=0
            )

        with pytest.raises(ValueError, match="Order price cannot be negative"):
            Order(
                order_id="1", 
                account_id="acc", 
                ticker="600000.SH", 
                direction=OrderDirection.BUY, 
                price=-1.0, 
                volume=100
            )

    def test_init_buy_volume_must_be_multiple_of_100(self):
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Buy volume must be a multiple of 100"):
            Order(
                order_id="1", 
                account_id="acc", 
                ticker="600000.SH", 
                direction=OrderDirection.BUY, 
                price=10.0, 
                volume=150
            )

    def test_submit_should_change_status_to_submitted(self):
        # Arrange
        order = Order(
            order_id="1", 
            account_id="acc", 
            ticker="600000.SH", 
            direction=OrderDirection.BUY, 
            price=10.0, 
            volume=100
        )
        
        # Act
        order.submit()
        
        # Assert
        assert order.status == OrderStatus.SUBMITTED

    def test_submit_already_submitted_should_raise_error(self):
        # Arrange
        order = Order(
            order_id="1", 
            account_id="acc", 
            ticker="600000.SH", 
            direction=OrderDirection.BUY, 
            price=10.0, 
            volume=100
        )
        order.submit()
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="Cannot submit order in status"):
            order.submit()

    def test_on_fill_should_update_status_to_partial_filled(self):
        # Arrange
        order = Order(
            order_id="1", 
            account_id="acc", 
            ticker="600000.SH", 
            direction=OrderDirection.BUY, 
            price=10.0, 
            volume=200
        )
        order.submit()
        
        # Act
        order.on_fill(fill_volume=100, fill_price=10.0)
        
        # Assert
        assert order.status == OrderStatus.PARTIAL_FILLED
        assert order.traded_volume == 100
        assert order.traded_price == 10.0

    def test_on_fill_should_update_status_to_filled_when_fully_traded(self):
        # Arrange
        order = Order(
            order_id="1", 
            account_id="acc", 
            ticker="600000.SH", 
            direction=OrderDirection.BUY, 
            price=10.0, 
            volume=100
        )
        order.submit()
        
        # Act
        order.on_fill(fill_volume=100, fill_price=10.0)
        
        # Assert
        assert order.status == OrderStatus.FILLED
        assert order.traded_volume == 100

    def test_on_fill_exceeding_volume_should_raise_error(self):
        # Arrange
        order = Order(
            order_id="1", 
            account_id="acc", 
            ticker="600000.SH", 
            direction=OrderDirection.BUY, 
            price=10.0, 
            volume=100
        )
        order.submit()
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="Fill volume exceeds order volume"):
            order.on_fill(fill_volume=200, fill_price=10.0)

    def test_cancel_should_change_status_to_canceled(self):
        # Arrange
        order = Order(
            order_id="1", 
            account_id="acc", 
            ticker="600000.SH", 
            direction=OrderDirection.BUY, 
            price=10.0, 
            volume=100
        )
        order.submit()
        
        # Act
        order.cancel()
        
        # Assert
        assert order.status == OrderStatus.CANCELED

    def test_cancel_partial_filled_should_change_status_to_partial_canceled(self):
        # Arrange
        order = Order(
            order_id="1", 
            account_id="acc", 
            ticker="600000.SH", 
            direction=OrderDirection.BUY, 
            price=10.0, 
            volume=200
        )
        order.submit()
        order.on_fill(fill_volume=100, fill_price=10.0)
        
        # Act
        order.cancel()
        
        # Assert
        assert order.status == OrderStatus.PARTIAL_CANCELED

    def test_reject_should_change_status_to_rejected(self):
        # Arrange
        order = Order(
            order_id="1", 
            account_id="acc", 
            ticker="600000.SH", 
            direction=OrderDirection.BUY, 
            price=10.0, 
            volume=100
        )
        order.submit()
        
        # Act
        order.reject(reason="Insufficient funds")
        
        # Assert
        assert order.status == OrderStatus.REJECTED
        assert order.remark == "Insufficient funds"
