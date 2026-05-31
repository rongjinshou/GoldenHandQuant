# Phase 2.5: 信号审核界面 — 实现计划

**文档版本**: v1.0
**创建日期**: 2026-05-31
**对应设计文档**: `docs/feat/0530-system-roadmap/2026-05-31-signal-review-design.md`

---

## Task 总览

| # | Task | 文件 | 依赖 | 估计 |
|---|------|------|------|------|
| 1 | 新增值对象：ReviewAction + SignalReviewRecord | 2 个新文件 | 无 | 小 |
| 2 | 新增 EnhancedSignalDisplay + 风险评分计算 | 1 个新文件 | Task 1 | 小 |
| 3 | 审核记录持久化 ReviewStore | 1 个新文件 | Task 1 | 中 |
| 4 | IMarketGateway 扩展 get_stock_snapshots | 1 个修改文件 | 无 | 小 |
| 5 | LiveSignalService 支持截面策略扫描 | 1 个修改文件 | Task 4 | 中 |
| 6 | Rich 审核界面 review_ui.py | 1 个新文件 | Task 1-3, 5 | 大 |
| 7 | 重构 live_trade.py 入口 | 1 个修改文件 | Task 6 | 中 |
| 8 | 端到端测试 | 2 个新文件 | Task 7 | 中 |

---

## Task 1: 新增值对象

### 文件

- **新建** `src/domain/strategy/value_objects/review_action.py`
- **新建** `src/domain/strategy/value_objects/signal_review_record.py`

### 内容

**review_action.py**：
- `ReviewAction` 枚举：`APPROVED`, `REJECTED`, `SKIPPED`

**signal_review_record.py**：
- `SignalReviewRecord` dataclass（`slots=True, kw_only=True`），字段见设计文档 3.1
- 包含 `__post_init__` 验证：`risk_score` 在 `[0, 1]` 范围内

### 验证标准

```bash
python -c "from src.domain.strategy.value_objects.review_action import ReviewAction; print(ReviewAction.APPROVED)"
python -c "from src.domain.strategy.value_objects.signal_review_record import SignalReviewRecord"
python -m pytest tests/domain/strategy/value_objects/ -v  # 不破坏现有测试
```

---

## Task 2: EnhancedSignalDisplay + 风险评分

### 文件

- **新建** `src/interfaces/cli/signal_review/__init__.py`
- **新建** `src/interfaces/cli/signal_review/enhanced_display.py`

### 内容

- `EnhancedSignalDisplay` 继承 `SignalDisplay`，新增字段：`risk_score`, `ml_confidence`, `signal_age_hours`, `historical_win_rate`
- `calculate_risk_score(signal, position, asset) -> float` 函数：
  - 基于持仓集中度（单只占比）、信号置信度（反向）、方向（卖出风险低于买入）计算
  - 返回 `[0.0, 1.0]`，0.0 = 低风险，1.0 = 高风险

### 验证标准

```bash
python -c "from src.interfaces.cli.signal_review.enhanced_display import EnhancedSignalDisplay, calculate_risk_score"
python -m pytest tests/interfaces/cli/signal_review/ -v
```

---

## Task 3: 审核记录持久化 ReviewStore

### 文件

- **新建** `src/interfaces/cli/signal_review/review_store.py`

### 内容

- `ReviewStore` 类：
  - `__init__(storage_dir: Path = Path("resources/signal_reviews"))`
  - `load_today() -> list[SignalReviewRecord]`：加载当日 JSON 文件，不存在则返回空列表
  - `append(record: SignalReviewRecord) -> None`：追加记录并写入文件
  - `save_all(records: list[SignalReviewRecord]) -> None`：批量写入
  - `get_strategy_stats(strategy_name: str, lookback_days: int = 30) -> dict`：查询历史胜率等统计
- 内部使用 `json` 标准库，dataclass 手动序列化（不引入第三方库）
- 文件损坏时静默重建空文件，logger.warning 记录

### 验证标准

```bash
python -c "
from src.interfaces.cli.signal_review.review_store import ReviewStore
from pathlib import Path
store = ReviewStore(Path('/tmp/test_reviews'))
print(store.load_today())
"
python -m pytest tests/interfaces/cli/signal_review/test_review_store.py -v
```

---

## Task 4: IMarketGateway 扩展

### 文件

- **修改** `src/domain/market/interfaces/gateways/market_gateway.py`

### 内容

在 `IMarketGateway` Protocol 中新增方法：

```python
def get_stock_snapshots(self, symbols: list[str]) -> list[StockSnapshot]:
    """获取标的日频快照，供截面策略使用。默认实现返回空列表。"""
    return []
```

同步更新 mock gateway 和 QMT gateway 的实现（如已有 `StockSnapshot` 类型）。

### 验证标准

```bash
python -m pytest tests/domain/market/ -v  # 不破坏现有测试
python -m pytest tests/infrastructure/mock/ -v
```

---

## Task 5: LiveSignalService 截面策略支持

### 文件

- **修改** `src/application/live_signal_service.py`

### 内容

重构 `_scan_cross_sectional()` 方法：
1. 调用 `self.market_gateway.get_stock_snapshots(symbols)` 获取快照
2. 若快照为空，降级为逐 symbol 拉 bar 并构造简化 `StockSnapshot`
3. 调用 `strategy.generate_cross_sectional_signals(snapshots, positions, datetime.now())`
4. 复用 `_signals_to_displays()` 转换

新增 `_build_fallback_snapshots()` 私有方法实现降级逻辑。

### 验证标准

```bash
python -m pytest tests/application/test_live_signal_service.py -v
```

---

## Task 6: Rich 审核界面

### 文件

- **新建** `src/interfaces/cli/signal_review/review_ui.py`

### 内容

- `SignalReviewUI` 类：
  - `__init__(service: LiveSignalService, order_service: OrderService, store: ReviewStore)`
  - `run(strategy_name: str, symbols: list[str]) -> None`：主循环
- 核心方法：
  - `_render_table(displays: list[EnhancedSignalDisplay]) -> None`：Rich 表格渲染
  - `_render_detail(display: EnhancedSignalDisplay) -> None`：展开卡片
  - `_parse_command(input_str: str) -> tuple[str, list[int]]`：解析用户命令
  - `_execute_batch(approved: list, rejected: list) -> tuple[list[OrderResult], list[SignalReviewRecord]]`：批量下单 + 记录
- 依赖 `rich` 库（已在项目依赖中）
- 交互命令：`a`, `r`, `r 2,4`, `1,3,5`, `n 1 note`, `d 3`, `q`
- 信号数量 >20 时分页

### 验证标准

```bash
python -c "from src.interfaces.cli.signal_review.review_ui import SignalReviewUI; print('import ok')"
# 手动测试：连接 QMT 后运行完整审核流程
```

---

## Task 7: 重构 live_trade.py

### 文件

- **修改** `src/interfaces/cli/live_trade.py`

### 内容

1. 精简 `main()`：保留参数解析 + QMT 连接 + 调用 `SignalReviewUI.run()`
2. 删除 `print_signal_table()`, `confirm_single()`, `print_order_results()` 等函数（已迁移到 review_ui.py）
3. 保留 `parse_args()`, `print_header()` 作为入口辅助
4. 移除截面策略阻断逻辑（`sys.exit(0)` 改为正常流程）
5. 新增 `--review-mode` 参数（默认 `rich`，可选 `legacy` 回退到旧版纯文本模式）

### 验证标准

```bash
python -m src.interfaces.cli.live_trade --help  # 参数正常显示
python -m pytest tests/interfaces/cli/ -v
ruff check src/interfaces/cli/live_trade.py
```

---

## Task 8: 端到端测试

### 文件

- **新建** `tests/interfaces/cli/signal_review/test_review_ui.py`
- **新建** `tests/interfaces/cli/signal_review/test_integration.py`

### 内容

**test_review_ui.py**（单元测试）：
- 测试 `_parse_command()` 各种输入解析
- 测试 `_render_table()` 空信号 / 多信号 / 分页场景
- 测试批量操作逻辑（mock LiveSignalService）

**test_integration.py**（集成测试）：
- 测试完整流程：扫描信号 -> 审核 -> 下单 -> 记录持久化
- 使用 MockMarketGateway + MockTradeGateway
- 验证 JSON 文件内容正确

### 验证标准

```bash
python -m pytest tests/interfaces/cli/signal_review/ -v --tb=short
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -v  # 全量测试通过
ruff check src/
```

---

## 执行顺序

```
Task 1 ──┬──> Task 2 ──┐
         │              ├──> Task 6 ──> Task 7 ──> Task 8
         └──> Task 3 ──┘
Task 4 ──> Task 5 ─────────────────────┘
```

- Task 1-3 可并行（无相互依赖）
- Task 4-5 串行（接口扩展 -> 实现）
- Task 6 依赖 Task 1-3, 5
- Task 7 依赖 Task 6
- Task 8 最后执行

## 风险点

| 风险 | 缓解措施 |
|------|---------|
| `rich` 未安装 | 在 `review_ui.py` 中 try-import，降级到纯文本 |
| 截面策略 `StockSnapshot` 数据源不可用 | `_build_fallback_snapshots()` 降级方案 |
| JSON 并发写入冲突 | 单线程 CLI，无需加锁；未来 Web 版本再考虑 |
| 现有测试因接口变更失败 | Task 4 中用默认实现 `return []`，不破坏现有测试 |
