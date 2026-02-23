from src.domain.market.value_objects.timeframe import Timeframe

class TestTimeframe:
    def test_enum_values(self):
        assert Timeframe.MIN_1 == "1m"
        assert Timeframe.MIN_5 == "5m"
        assert Timeframe.MIN_15 == "15m"
        assert Timeframe.MIN_30 == "30m"
        assert Timeframe.HOUR_1 == "1h"
        assert Timeframe.DAY_1 == "1d"
