import hmac
import logging

logger = logging.getLogger(__name__)


class TokenAuth:
    """Token 认证中间件。

    支持静态 Token 和基于 HMAC 的临时 Token。
    """

    def __init__(self, api_token: str) -> None:
        self._api_token = api_token

    def verify(self, token: str) -> bool:
        """验证 Token 是否有效。"""
        if not self._api_token:
            logger.warning("API Token 未配置，拒绝所有请求")
            return False
        return hmac.compare_digest(token, self._api_token)

    @staticmethod
    def mask_sensitive(text: str) -> str:
        """日志脱敏: 隐藏敏感信息。"""
        # 遮盖账户 ID 后四位
        import re
        return re.sub(r'(\w{4})\w{4}(\w{0,4})', r'\1****\2', text)
