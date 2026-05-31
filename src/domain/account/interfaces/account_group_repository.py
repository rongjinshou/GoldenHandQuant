from src.domain.account.entities.account_group import AccountGroup


class AccountGroupRepository:
    """账户组仓储 -- 管理 AccountGroup 的持久化与查询。

    内存实现，与 AccountRepository 同级。
    """

    def __init__(self) -> None:
        self._groups: dict[str, AccountGroup] = {}

    def save(self, group: AccountGroup) -> None:
        """保存（创建或更新）账户组。"""
        self._groups[group.group_id] = group

    def get(self, group_id: str) -> AccountGroup | None:
        """根据 group_id 获取账户组，不存在返回 None。"""
        return self._groups.get(group_id)

    def delete(self, group_id: str) -> None:
        """删除账户组。"""
        self._groups.pop(group_id, None)

    def list_groups(self) -> list[AccountGroup]:
        """列出所有账户组。"""
        return list(self._groups.values())

    def find_by_account(self, account_id: str) -> list[AccountGroup]:
        """查找包含指定账户的所有组。"""
        return [g for g in self._groups.values() if account_id in g.account_ids]
