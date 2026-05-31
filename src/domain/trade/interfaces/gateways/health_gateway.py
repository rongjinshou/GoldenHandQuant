from typing import Protocol


class IHealthGateway(Protocol):
    """健康检查网关接口。

    由基础设施层实现，负责探活和运行时信息采集。
    """

    def check_heartbeat(self) -> bool:
        """检查心跳是否正常。

        Returns:
            bool: 心跳正常返回 True，超时返回 False。
        """
        ...

    def get_uptime(self) -> float:
        """获取进程运行时长（秒）。

        Returns:
            float: 自启动以来的秒数。
        """
        ...

    def is_alive(self) -> bool:
        """检查目标进程/线程是否存活。

        Returns:
            bool: 存活返回 True。
        """
        ...
