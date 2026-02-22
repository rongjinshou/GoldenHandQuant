import pytest
from src.domain.account.position import Position

class TestPosition:
    def test_on_buy_filled_should_increase_total_volume_but_not_available_volume(self):
        """测试 T+1 买入规则：买入当日只增加总持仓，不增加可用持仓"""
        # Arrange
        pos = Position(account_id="test_account", ticker="600000.SH", total_volume=0, available_volume=0)
        
        # Act
        pos.on_buy_filled(volume=100, price=10.0)
        
        # Assert
        assert pos.total_volume == 100
        assert pos.available_volume == 0  # T+1 rule
        assert pos.average_cost == 10.0

    def test_on_buy_filled_should_update_average_cost(self):
        # Arrange
        # 初始持仓 100 股，成本 10 元
        pos = Position(
            account_id="test_account", 
            ticker="600000.SH", 
            total_volume=100, 
            available_volume=100, 
            average_cost=10.0
        )
        
        # Act
        # 再买入 100 股，价格 20 元
        pos.on_buy_filled(volume=100, price=20.0)
        
        # Assert
        # 新成本 = (100*10 + 100*20) / 200 = 15.0
        assert pos.total_volume == 200
        assert pos.available_volume == 100  # available volume not changed
        assert pos.average_cost == 15.0

    def test_on_sell_filled_should_decrease_both_total_and_available_volume(self):
        # Arrange
        pos = Position(
            account_id="test_account", 
            ticker="600000.SH", 
            total_volume=200, 
            available_volume=200, 
            average_cost=10.0
        )
        
        # Act
        pos.on_sell_filled(volume=100, price=12.0)
        
        # Assert
        assert pos.total_volume == 100
        assert pos.available_volume == 100
        assert pos.average_cost == 10.0  # Selling does not change average cost

    def test_on_sell_filled_insufficient_available_volume_should_raise_error(self):
        # Arrange
        pos = Position(
            account_id="test_account", 
            ticker="600000.SH", 
            total_volume=200, 
            available_volume=100  # Only 100 available
        )
        
        # Act & Assert
        with pytest.raises(ValueError, match="Insufficient available volume"):
            pos.on_sell_filled(volume=150, price=10.0)

    def test_settle_t_plus_1_should_make_all_volume_available(self):
        # Arrange
        # 昨日持仓 100 (available), 今日买入 100 (frozen) -> total 200, available 100
        pos = Position(
            account_id="test_account", 
            ticker="600000.SH", 
            total_volume=200, 
            available_volume=100
        )
        
        # Act
        pos.settle_t_plus_1()
        
        # Assert
        assert pos.available_volume == 200
        assert pos.total_volume == 200

    def test_on_sell_filled_clearing_position_should_reset_cost(self):
        # Arrange
        pos = Position(
            account_id="test_account", 
            ticker="600000.SH", 
            total_volume=100, 
            available_volume=100,
            average_cost=10.0
        )
        
        # Act
        pos.on_sell_filled(volume=100, price=12.0)
        
        # Assert
        assert pos.total_volume == 0
        assert pos.available_volume == 0
        assert pos.average_cost == 0.0
