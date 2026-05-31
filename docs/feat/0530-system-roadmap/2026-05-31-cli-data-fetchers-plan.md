# Agent Team v2 CLI 数据接口 — 实现计划

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 实现计划 / 任务分解
**状态**: 草案
**关联设计文档**: `2026-05-31-cli-data-fetchers-design.md`

---

## 实现概览

共 4 个阶段，预计 11 个原子任务。依赖关系如下：

```
Phase 1: 基础框架 + P0 命令（最高优先级）
  ├── Task 1: 提取 CLI 公共工具模块 cli_utils.py
  ├── Task 2: 改造 fetch_account.py 支持 JSON 输出
  ├── Task 3: 新增 fetch_quote.py
  └── Task 4: 集成测试 P0 命令

Phase 2: P1 命令
  ├── Task 5: 新增 fetch_financial.py
  ├── Task 6: 新增 fetch_indicators.py（含技术指标计算）
  └── Task 7: 集成测试 P1 命令

Phase 3: P2 命令
  ├── Task 8: 新增 fetch_northbound.py（需先确认 API）
  └── Task 9: 新增 fetch_dragon_tiger.py（需先确认 API）

Phase 4: P3 命令 + 收尾
  ├── Task 10: 新增 fetch_sector.py
  └── Task 11: 文档更新 + ruff check + 全量回归
```

---

## Phase 1: 基础框架 + P0 命令

### Task 1: 提取 CLI 公共工具模块

**文件**: `src/interfaces/cli/cli_utils.py`（新建）

**内容**:
- `output_json(data: dict) -> None`：统一 JSON 输出到 stdout
- `output_error(message: str) -> None`：统一错误输出到 stderr + stdout JSON
- `output_success(data: dict) -> None`：封装 success 信封
- `check_qmt_connection() -> bool`：检测 QMT 连接状态
- `setup_timeout(seconds: int) -> None`：设置超时信号
- `cancel_timeout() -> None`：取消超时信号
- `TIMEOUT_SECONDS = 30` 常量

**设计要点**:
- 超时使用 `signal.SIGALRM`（WSL/Linux），`threading.Timer`（Windows 兜底）
- `check_qmt_connection` 通过 `xtdata.get_instrument_detail("000001.SZ")` 检测
- 所有时间戳使用 `datetime.now().astimezone().isoformat()`（含时区信息）

**验证**: `python -c "from src.interfaces.cli.cli_utils import output_json; output_json({'test': True})"` 输出正确 JSON。

**预估**: 20 分钟

---

### Task 2: 改造 fetch_account.py 支持 JSON 输出

**文件**: `src/interfaces/cli/fetch_account.py`（修改）

**变更**:
1. 新增 `--json` 命令行参数
2. 当 `--json` 时，调用 `cli_utils.output_json()` 输出账户 JSON
3. 保留默认模式的 Markdown 输出（向后兼容）
4. 从 `fetch_account_info()` 的返回值中新增 `market_value` 字段
5. 添加超时和 QMT 连接检测

**JSON 输出结构**:
```json
{
  "success": true,
  "data": {
    "account_id": "...",
    "total_asset": 1050000.00,
    "available_cash": 50000.00,
    "frozen_cash": 0.00,
    "market_value": 1000000.00,
    "positions": [...]
  },
  "timestamp": "..."
}
```

**向后兼容**:
- 不加 `--json` 参数时行为不变（输出 Markdown）
- `assemble_task()` 函数不改动
- 现有 `connect_qmt()` 和 `fetch_account_info()` 接口不变

**验证**:
- `python -m src.interfaces.cli.fetch_account --json` 输出正确 JSON
- `python -m src.interfaces.cli.fetch_account` 输出 Markdown（向后兼容）

**预估**: 20 分钟

---

### Task 3: 新增 fetch_quote.py

**文件**: `src/interfaces/cli/fetch_quote.py`（新建）

**功能**: 获取单只标的的实时行情快照

**命令行参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--symbol` / `-s` | str | 是 | 标的代码，如 600519.SH |
| `--config` / `-c` | str | 否 | 配置文件路径（默认 resources/trading.yaml） |

**数据获取流程**:

1. **QMT 连接检测**
2. **获取实时快照**: `xtdata.get_full_tick([symbol])`
   - 若失败（非交易时间等），降级为 `xtdata.get_market_data_ex()` 获取最近一个交易日数据
3. **获取合约详情**: `xtdata.get_instrument_detail(symbol)`
   - 提取：`InstrumentName`, `TotalVolume`
4. **获取财务指标**: `xtdata.get_financial_data(stock_list=[symbol], table_list=['PershareIndex'])`
   - 提取最新一期：`s_fa_eps_basic`（EPS）→ 计算 PE
   - 提取最新一期：`s_fa_bps`（BPS）→ 计算 PB
5. **组装 JSON 输出**

**降级策略**:
- `get_full_tick` 失败 → 用 `get_market_data_ex` 最近 1 日数据
- `get_financial_data` 失败 → PE/PB 返回 null
- `get_instrument_detail` 失败 → name 返回 symbol 本身

**验证**: `python -m src.interfaces.cli.fetch_quote --symbol 600519.SH --json` 输出正确 JSON。

**预估**: 30 分钟

---

### Task 4: 集成测试 P0 命令

**测试方式**: 手动在 Windows Python 环境中运行（QMT 客户端已启动）

**测试用例**:

| # | 命令 | 预期 |
|---|------|------|
| 1 | `fetch_account --json` | 返回 success: true，包含 total_asset 和 positions |
| 2 | `fetch_account` | 返回 Markdown（向后兼容） |
| 3 | `fetch_quote --symbol 600519.SH` | 返回 success: true，包含 price 和 name |
| 4 | `fetch_quote --symbol INVALID.XX` | 返回 success: false 或 data 中字段为 null |
| 5 | `fetch_quote`（无 symbol） | argparse 报错 |
| 6 | QMT 未启动时运行 | 返回 success: false, error: "QMT 客户端未连接" |

**验证**: 所有用例通过。

**预估**: 15 分钟

---

## Phase 2: P1 命令

### Task 5: 新增 fetch_financial.py

**文件**: `src/interfaces/cli/fetch_financial.py`（新建）

**功能**: 获取单只标的的财务数据

**命令行参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--symbol` / `-s` | str | 是 | 标的代码 |
| `--quarters` / `-q` | int | 否 | 获取最近 N 个季度（默认 4） |

**数据获取流程**:

1. **QMT 连接检测**
2. **下载财务数据**: `xtdata.download_financial_data(stock_list=[symbol])`
3. **获取合约详情**: `xtdata.get_instrument_detail(symbol)` → name, list_date, TotalVolume
4. **获取财务报表**: `xtdata.get_financial_data(stock_list=[symbol], table_list=['PershareIndex'])`
5. **解析 PershareIndex DataFrame**:
   - 按 `m_anntime`（公告日期）排序，取最近 N 期
   - 提取字段：`equity_roe`, `s_fa_eps_basic`, `s_fa_bps`, `s_fa_ocfps`, `gear_ratio`, `gross_profit`, `net_profit`, `inc_revenue_rate`, `inc_net_profit_rate`
6. **组装 JSON 输出**

**字段映射**（参考 `QmtFundamentalFetcher` 第 137-143 行）:
```python
FIELD_MAP = {
    "equity_roe": "roe",
    "s_fa_eps_basic": "eps",
    "s_fa_bps": "bps",
    "s_fa_ocfps": "ocf_per_share",
    "gear_ratio": "debt_ratio",
    "gross_profit": "gross_profit",
    "net_profit": "net_profit",
    "inc_revenue_rate": "revenue_growth",
    "inc_net_profit_rate": "net_profit_growth",
}
```

**验证**: `python -m src.interfaces.cli.fetch_financial --symbol 600519.SH` 输出包含 latest_report 和 quarters。

**预估**: 30 分钟

---

### Task 6: 新增 fetch_indicators.py

**文件**: `src/interfaces/cli/fetch_indicators.py`（新建）

**功能**: 获取单只标的的技术指标

**命令行参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--symbol` / `-s` | str | 是 | 标的代码 |
| `--period` / `-p` | str | 否 | K 线周期（默认 1d，支持 1d/1w/1m） |
| `--bars` / `-b` | int | 否 | 获取 K 线数量（默认 120） |

**数据获取流程**:

1. **QMT 连接检测**
2. **下载历史数据**: `xtdata.download_history_data(symbol, period, ...)`
3. **获取 K 线**: `xtdata.get_market_data_ex(field_list=['open','high','low','close','volume'], period=period, count=bars)`
4. **计算技术指标**（纯 Python 实现）:
   - MA(5/10/20/60)
   - RSI(6/14)
   - MACD(12,26,9)
   - Bollinger Bands(20,2)
   - KDJ(9,3,3)
   - ATR(14)
   - 量比
5. **组装 JSON 输出**

**技术指标计算模块**: 直接在 `fetch_indicators.py` 内部实现辅助函数，不新建独立模块（保持轻量）。

```python
def _calc_ma(closes: list[float], n: int) -> float | None: ...
def _calc_rsi(closes: list[float], n: int) -> float | None: ...
def _calc_macd(closes: list[float]) -> tuple[float, float, float]: ...
def _calc_bollinger(closes: list[float], n: int = 20, k: float = 2.0) -> tuple[float, float, float]: ...
def _calc_kdj(highs: list[float], lows: list[float], closes: list[float]) -> tuple[float, float, float]: ...
def _calc_atr(highs: list[float], lows: list[float], closes: list[float], n: int = 14) -> float: ...
```

**验证**: `python -m src.interfaces.cli.fetch_indicators --symbol 600519.SH` 输出包含 ma/rsi/macd/boll/kdj/atr。

**预估**: 45 分钟

---

### Task 7: 集成测试 P1 命令

**测试方式**: 手动在 Windows Python 环境中运行

**测试用例**:

| # | 命令 | 预期 |
|---|------|------|
| 1 | `fetch_financial --symbol 600519.SH` | 包含 latest_report 和 quarters |
| 2 | `fetch_financial --symbol 600519.SH --quarters 8` | quarters 数组有 8 个元素 |
| 3 | `fetch_indicators --symbol 600519.SH` | 包含 ma/rsi/macd 等指标 |
| 4 | `fetch_indicators --symbol 600519.SH --period 1w` | 使用周线数据计算 |
| 5 | `fetch_indicators --symbol 600519.SH --bars 200` | 获取 200 根 K 线 |

**验证**: 所有用例通过。

**预估**: 15 分钟

---

## Phase 3: P2 命令

### Task 8: 新增 fetch_northbound.py

**前置条件**: 需先通过 `explore_qmt_data.py` 确认 xtdata 北向资金 API 可用性。

**文件**: `src/interfaces/cli/fetch_northbound.py`（新建）

**功能**: 获取北向资金（沪深港通）数据

**命令行参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--date` / `-d` | str | 否 | 查询日期（默认当日，格式 YYYY-MM-DD） |
| `--top` / `-t` | int | 否 | 显示前 N 名（默认 10） |

**实现方案**（按可行性排序）:

**方案 A**（首选）: 使用 xtdata 北向资金专用接口
- 调用 `xtdata.get_market_data_ex()` 获取沪股通/深股通专用标的的资金数据
- 若 xtdata 提供 `get_northbound_flow()` 等专用接口则直接使用

**方案 B**（降级）: 从已有数据推导
- 获取沪深港通成分股列表
- 获取各成分股的资金流向数据
- 汇总计算净买入

**方案 C**（兜底）: 返回提示信息
- 若 API 不可用，返回 `success: true, data: {"message": "北向资金数据暂不可用，请使用第三方数据源"}`

**预估**: 30 分钟（含 API 探测时间）

---

### Task 9: 新增 fetch_dragon_tiger.py

**前置条件**: 需先确认 xtdata 龙虎榜 API 可用性。

**文件**: `src/interfaces/cli/fetch_dragon_tiger.py`（新建）

**功能**: 获取龙虎榜数据

**命令行参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--date` / `-d` | str | 否 | 查询日期（默认当日） |
| `--top` / `-t` | int | 否 | 显示前 N 名（默认 20） |

**实现方案**: 同 Task 8，按 API 可用性选择方案 A/B/C。

**预估**: 30 分钟（含 API 探测时间）

---

## Phase 4: P3 命令 + 收尾

### Task 10: 新增 fetch_sector.py

**文件**: `src/interfaces/cli/fetch_sector.py`（新建）

**功能**: 获取行业板块成分股及行情

**命令行参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--sector` / `-s` | str | 是 | 板块代码或名称 |
| `--top` / `-t` | int | 否 | 显示前 N 只（默认 20） |

**板块名称映射**:
```python
SECTOR_MAP = {
    "semiconductor": "半导体",
    "new_energy": "新能源",
    "pharma": "医药",
    "consumer": "消费",
    "finance": "金融",
    "tech": "科技",
    "auto": "汽车",
    "military": "军工",
    "real_estate": "房地产",
    "material": "材料",
}
```

**数据获取流程**:

1. **QMT 连接检测**
2. **解析板块名称**: 支持中文名（如"半导体"）和英文代码（如"semiconductor"）
3. **获取成分股**: `xtdata.get_stock_list_in_sector(sector_name)`
4. **获取行情**: `xtdata.get_full_tick(stocks)` 或 `xtdata.get_market_data_ex()`
5. **组装 JSON 输出**: 按涨跌幅排序

**验证**: `python -m src.interfaces.cli.fetch_sector --sector semiconductor` 返回成分股列表和行情。

**预估**: 25 分钟

---

### Task 11: 文档更新 + 代码检查

**变更**:
1. 更新 `CLAUDE.md` 的"常用命令"章节，添加 CLI 数据接口命令示例
2. `ruff check src/interfaces/cli/` 确保无 lint 错误
3. `pytest tests/ --ignore=tests/infrastructure/gateway/` 全量回归
4. 确认所有新增文件遵循项目规范：
   - `list[X]` / `dict[K,V]` / `X | None`（Python 3.13+ 类型注解）
   - 状态日志输出到 stderr，数据输出到 stdout
   - JSON 使用 `ensure_ascii=False` 保留中文

**验证**: ruff 无报错，全量测试通过。

**预估**: 15 分钟

---

## 总预估工时

| Phase | 任务数 | 预估时间 | 优先级 |
|-------|--------|---------|--------|
| Phase 1: 基础框架 + P0 | 4 | 85 分钟 | 最高 |
| Phase 2: P1 命令 | 3 | 90 分钟 | 高 |
| Phase 3: P2 命令 | 2 | 60 分钟 | 中（依赖 API 探测） |
| Phase 4: P3 + 收尾 | 2 | 40 分钟 | 低 |
| **合计** | **11** | **275 分钟（~4.5 小时）** | |

---

## 风险与应急

| 风险 | 影响 | 应急方案 |
|------|------|---------|
| xtdata 北向/龙虎榜 API 不可用 | P2 命令无法实现 | 降级为返回提示信息（方案 C） |
| get_full_tick 非交易时间失败 | fetch_quote 无法获取实时数据 | 降级为 get_market_data_ex 最近一日数据 |
| signal.SIGALRM 在 Windows 不可用 | 超时机制失效 | 使用 threading.Timer 替代 |
| 技术指标计算与专业库有差异 | Hermes Agent 分析结果偏差 | 对齐 xtquant 内置指标，误差 < 0.1% |
| fetch_account 改造破坏现有功能 | Hermes 任务组装失败 | 保留默认 Markdown 模式，JSON 为新增模式 |

---

## 实施建议

1. **先做 Phase 1**：fetch_account 改造 + fetch_quote 是 Hermes Agent 最急需的两个命令
2. **Phase 2 紧随其后**：fetch_financial 和 fetch_indicators 是投研分析的核心数据
3. **Phase 3 需要先探测**：在实现 fetch_northbound 和 fetch_dragon_tiger 之前，先用 explore_qmt_data.py 确认 API 可用性
4. **Phase 4 可以并行**：fetch_sector 与其他任务无依赖，可以在任何时候实现
