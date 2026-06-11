# Python 编码风格规范 (Coding Style)

> 适用范围：全项目。Python 3.13+，以 Ruff 为格式化与 lint 标准。

## 1. 现代类型注解 (Type Hinting)

- **全面弃用**旧版 `typing` 大写集合：`List`、`Dict`、`Union`、`Optional` 一律不用。
- 强制使用内置泛型与管道符：`list[str]`、`dict[str, int]`、`str | None`。
- 返回类实例自身时使用 `typing.Self`。
- 所有函数签名、类属性必须有完整准确的类型注解（核心红线之一）。

## 2. 高性能数据类 (Dataclasses)

- 领域实体（Entity）：`@dataclass(slots=True, kw_only=True)`。
- 值对象（Value Object）：`@dataclass(frozen=True, slots=True, kw_only=True)`，确保不可变。
- `slots=True`：杜绝动态字典，优化海量持仓/订单对象内存。
- `kw_only=True`：强制关键字传参，杜绝参数错位导致的致命交易 Bug。

## 3. 结构化模式匹配 (match/case)

处理领域状态机（如 `Order` 状态流转、表达式求值分支）或事件路由时，
**优先使用 `match / case`**，替代冗长易错的 `if-elif-else`。

## 4. 命名与格式化 (PEP 8 严格模式)

- 单行长度 120 字符（ruff 配置为准）。
- 类名 `PascalCase`；函数、变量、方法 `snake_case`；全局常量 `UPPER_SNAKE_CASE`。
- 模块私有成员用单下划线 `_` 前缀；禁止滥用双下划线 `__`（除非规避命名冲突）。

## 5. 异常处理与错误边界

- 禁止 bare `except:` 与 `except Exception: pass`。
- 必须捕获具体异常类型；基础设施层捕获第三方异常后，包装为领域异常再上抛
  （如 `raise OrderSubmitError from e`）。
- 领域异常定义在各子域 `exceptions.py`（现存示例：`src/domain/trade/exceptions.py`）。

## 6. 文档字符串 (Docstrings)

- 公共模块、类、复杂领域方法必须有 **Google Style** Docstring。
- 标注 `Args:`、`Returns:`、可能抛出的 `Raises:`。

## 7. 模块导入规范

- **跨层/跨模块调用必须绝对导入**：如 infrastructure 调 domain 必须
  `from src.domain.trade.entities.order import Order`，禁止相对导入。
- **同包兄弟模块推荐相对导入**：如 `src/infrastructure/gateway/` 内
  `qmt_trade.py` 调同目录 `xtquant_client.py`，用 `from .xtquant_client import xtdata`，
  保持包内聚与重构友好。
