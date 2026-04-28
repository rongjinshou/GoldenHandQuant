import logging
import sys

from src.application.order_service import OrderService
from src.domain.risk.services.simple_risk_policy import SimpleRiskPolicy
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.infrastructure.gateway.qmt_trade import QmtTradeGateway
from src.infrastructure.config.settings import load_trading_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def main() -> None:
    """CLI 入口点。"""
    logger.info("Starting QuantFlow Strategy...")

    # 1. 初始化基础设施
    # 从配置文件加载，保留硬编码回退
    try:
        settings = load_trading_config()
        qmt_path = settings.qmt.userdata_path
        session_id = settings.qmt.session_id
        account_id = settings.qmt.account_id
        logger.info("Loaded trading configuration from config/trading.yaml")
    except FileNotFoundError:
        qmt_path = r"D:\国金QMT交易端模拟\userdata_mini"
        session_id = 123456
        account_id = "88888888"
        logger.info("Config file not found, using default parameters.")

    try:
        gateway = QmtTradeGateway(qmt_path, session_id, account_id)
    except Exception as e:
        logger.error(f"Failed to initialize gateway: {e}")
        return

    # 2. 初始化领域服务 (依赖注入)
    risk_policy = SimpleRiskPolicy()
    order_service = OrderService(gateway, risk_policy)

    # 3. 模拟业务操作
    logger.info("Placing a test order...")
    order = Order(
        order_id="test_order_001",
        account_id=account_id,
        ticker="600000.SH",
        direction=OrderDirection.BUY,
        price=10.0,
        volume=100,
        type=OrderType.LIMIT,
    )

    result = order_service.place_order(order)
    if result.success:
        logger.info(f"Order placed successfully! ID: {result.order_id}")
    else:
        logger.error(f"Order placement failed: {result.message}")


if __name__ == "__main__":
    main()
