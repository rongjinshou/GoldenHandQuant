# Agent Team v2 CLI 数据接口 — 设计文档

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 详细设计 / 技术方案
**状态**: 草案
**关联需求**: `docs/feat/0520-agent-team-v2/2026-05-20-agent-team-v2-issues.md` 第二节

---

## 一、需求概述

### 1.1 背景

Agent Team v2 的 Hermes Agent 在执行投研任务时，需要获取 GoldenHandQuant 的实时数据（账户、持仓、行情、财务、技术指标等）。当前方式是通过 web_search 搜索公开数据，存在数据不准确、效率低、无法获取私有数据等问题。

### 1.2 核心能力

| # | 能力 | 优先级 | 命令 |
|---|------|--------|------|
| 1 | 账户资金 + 持仓查询 | P0 | `fetch_account` |
| 2 | 单只标的实时行情 | P0 | `fetch_quote` |
| 3 | 单只标的财务数据 | P1 | `fetch_financial` |
| 4 | 单只标的技术指标 | P1 | `fetch_indicators` |
| 5 | 北向资金数据 | P2 | `fetch_northbound` |
| 6 | 龙虎榜数据 | P2 | `fetch_dragon_tiger` |
| 7 | 行业板块数据 | P3 | `fetch_sector` |

### 1.3 约束

1. **底层依赖 xtquant**：只能在 Windows Python 环境中运行
2. **WSL 调用方式**：`/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe -m src.interfaces.cli.fetch_xxx`
3. **超时控制**：每个命令 30 秒超时
4. **输出格式**：JSON（stdout），状态日志（stderr）

---

## 二、现有架构分析

### 2.1 现有能力盘点

| 组件 | 文件 | 现有能力 | 缺口 |
|------|------|---------|------|
| fetch_account | `src/interfaces/cli/fetch_account.py` | 获取账户资金+持仓，组装 Markdown 投研任务 | 输出非 JSON，缺少 `--json` 模式 |
| QmtTradeGateway | `src/infrastructure/gateway/qmt_trade.py` | `get_asset()` / `get_positions()` | 功能完整 |
| QmtMarketGateway | `src/infrastructure/gateway/qmt_market.py` | `get_recent_bars()` 获取 K 线 | 缺少实时快照（最新价/涨跌幅/成交量） |
| QmtFundamentalFetcher | `src/infrastructure/gateway/qmt_fundamental_fetcher.py` | 财务数据（ROE/OCF/EPS/BPS）、指数日线 | 功能完整，可直接复用 |
| xtquant_client | `src/infrastructure/gateway/xtquant_client.py` | xtdata/xttrader 封装 | 功能完整 |
| explore_qmt_data | `src/interfaces/cli/explore_qmt_data.py` | 探测 xtdata 字段结构 | 仅用于开发探测 |

### 2.2 xtdata API 映射

| 数据类型 | xtdata API | 关键参数 |
|---------|-----------|---------|
| 实时行情快照 | `xtdata.get_full_tick([symbol])` | 返回最新价/开高低/成交量/成交额 |
| 历史 K 线 | `xtdata.get_market_data_ex()` | `field_list`, `period`, `dividend_type='front'` |
| 财务数据 | `xtdata.get_financial_data()` | `table_list=['Balance','Income','CashFlow','PershareIndex']` |
| 合约详情 | `xtdata.get_instrument_detail(symbol)` | 股票名称/上市日期/总股本 |
| 板块成分 | `xtdata.get_stock_list_in_sector(sector)` | 板块名称 |
| 北向资金 | `xtdata.get_market_data_ex()` + 沪深港通专用接口 | 需确认 API 可用性 |
| 龙虎榜 | `xtdata.get_market_data_ex()` 或额外接口 | 需确认 API 可用性 |

---

## 三、统一框架设计

### 3.1 设计原则

1. **CLI 层极薄**：仅负责参数解析、调用 fetcher、输出 JSON
2. **Fetcher 层封装数据逻辑**：每个 fetcher 是一个独立函数/类，可被 CLI 和 Application 层复用
3. **复用现有 Gateway**：不重复实现，直接调用 `QmtTradeGateway`、`QmtMarketGateway`、`QmtFundamentalFetcher`
4. **统一 JSON 信封**：所有命令使用相同的输出格式

### 3.2 架构分层

```
Interfaces (CLI)
    ├── fetch_account.py     → 调用 QmtTradeGateway
    ├── fetch_quote.py       → 调用 xtdata.get_full_tick + get_market_data_ex
    ├── fetch_financial.py   → 调用 QmtFundamentalFetcher / xtdata.get_financial_data
    ├── fetch_indicators.py  → 调用 xtdata.get_market_data_ex → 计算技术指标
    ├── fetch_northbound.py  → 调用 xtdata 北向接口
    ├── fetch_dragon_tiger.py→ 调用 xtdata 龙虎榜接口
    └── fetch_sector.py      → 调用 xtdata.get_stock_list_in_sector
         ↓
Infrastructure (Gateway / Fetcher)
    ├── QmtTradeGateway      (已有)
    ├── QmtMarketGateway     (已有)
    ├── QmtFundamentalFetcher(已有)
    └── xtquant_client       (已有)
```

**注意**：CLI 层直接调用 Infrastructure 层，不经过 Application 层。这是因为 CLI 数据接口是简单的数据查询，不需要用例编排。

### 3.3 统一 CLI 模板

所有 fetcher CLI 遵循统一模式：

```python
"""获取 XXX 数据。

使用方式:
    python -m src.interfaces.cli.fetch_xxx --symbol 600519.SH
"""

import argparse
import json
import signal
import sys
from datetime import datetime

TIMEOUT_SECONDS = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="获取 XXX 数据")
    parser.add_argument("--symbol", "-s", type=str, help="标的代码")
    parser.add_argument("--config", "-c", type=str, default="resources/trading.yaml")
    return parser.parse_args()


def timeout_handler(signum, frame):
    raise TimeoutError(f"请求超时 ({TIMEOUT_SECONDS}s)")


def output_json(data: dict) -> None:
    """统一 JSON 输出到 stdout。"""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def output_error(message: str) -> None:
    """统一错误输出到 stderr，并输出 JSON 错误到 stdout。"""
    print(f"ERROR: {message}", file=sys.stderr)
    output_json({"success": False, "error": message, "timestamp": datetime.now().isoformat()})


def main() -> None:
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(TIMEOUT_SECONDS)

    args = parse_args()
    try:
        data = fetch_data(args)
        output_json({"success": True, "data": data, "timestamp": datetime.now().isoformat()})
    except TimeoutError:
        output_error(f"请求超时 ({TIMEOUT_SECONDS}s)")
        sys.exit(1)
    except Exception as e:
        output_error(str(e))
        sys.exit(1)
    finally:
        signal.alarm(0)
```

---

## 四、JSON 输出格式规范

### 4.1 信封结构

所有命令输出统一的 JSON 信封：

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": "2026-05-31T10:30:00+08:00"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | `bool` | 请求是否成功 |
| `data` | `object \| null` | 成功时返回数据，失败时为 null |
| `error` | `string \| null` | 失败时返回错误信息，成功时为 null |
| `timestamp` | `string` | ISO 8601 格式的时间戳 |

### 4.2 各命令的 data 结构

#### fetch_account

```json
{
  "success": true,
  "data": {
    "account_id": "12345678",
    "total_asset": 1050000.00,
    "available_cash": 50000.00,
    "frozen_cash": 0.00,
    "market_value": 1000000.00,
    "positions": [
      {
        "ticker": "600519.SH",
        "total_volume": 100,
        "available_volume": 100,
        "average_cost": 1800.00
      }
    ]
  },
  "timestamp": "..."
}
```

#### fetch_quote

```json
{
  "success": true,
  "data": {
    "symbol": "600519.SH",
    "name": "贵州茅台",
    "price": 1850.00,
    "open": 1835.00,
    "high": 1860.00,
    "low": 1830.00,
    "pre_close": 1840.00,
    "change": 10.00,
    "change_pct": 0.54,
    "volume": 12345678,
    "amount": 22834567890.00,
    "turnover_rate": 0.98,
    "pe_ratio": 33.5,
    "pb_ratio": 10.2,
    "market_cap": 2324500000000.00,
    "total_shares": 1256197800
  },
  "timestamp": "..."
}
```

#### fetch_financial

```json
{
  "success": true,
  "data": {
    "symbol": "600519.SH",
    "name": "贵州茅台",
    "list_date": "2001-08-27",
    "latest_report": {
      "report_date": "2025-03-31",
      "roe": 8.92,
      "eps": 21.56,
      "bps": 185.30,
      "ocf_per_share": 15.23,
      "gross_margin": 91.5,
      "net_margin": 52.3,
      "revenue_growth": 10.5,
      "net_profit_growth": 11.2,
      "debt_ratio": 25.3,
      "current_ratio": 3.85
    },
    "quarters": [
      {
        "report_date": "2025-03-31",
        "roe": 8.92,
        "eps": 21.56,
        "revenue_growth": 10.5
      }
    ]
  },
  "timestamp": "..."
}
```

#### fetch_indicators

```json
{
  "success": true,
  "data": {
    "symbol": "600519.SH",
    "period": "1d",
    "latest_date": "2025-05-30",
    "indicators": {
      "ma5": 1845.00,
      "ma10": 1838.00,
      "ma20": 1820.00,
      "ma60": 1790.00,
      "rsi_6": 62.5,
      "rsi_14": 58.3,
      "macd": 15.2,
      "macd_signal": 12.8,
      "macd_hist": 2.4,
      "boll_upper": 1890.00,
      "boll_middle": 1835.00,
      "boll_lower": 1780.00,
      "kdj_k": 65.3,
      "kdj_d": 58.7,
      "kdj_j": 78.5,
      "atr_14": 25.6,
      "vol_ratio": 1.2
    },
    "recent_bars": [
      {
        "date": "2025-05-30",
        "open": 1835.00,
        "high": 1860.00,
        "low": 1830.00,
        "close": 1850.00,
        "volume": 12345678
      }
    ]
  },
  "timestamp": "..."
}
```

#### fetch_northbound

```json
{
  "success": true,
  "data": {
    "date": "2025-05-30",
    "total_net_buy": 5230000000.00,
    "sh_net_buy": 3120000000.00,
    "sz_net_buy": 2110000000.00,
    "top_buy": [
      {"symbol": "600519.SH", "name": "贵州茅台", "net_buy": 520000000.00}
    ],
    "top_sell": [
      {"symbol": "000858.SZ", "name": "五粮液", "net_sell": -310000000.00}
    ]
  },
  "timestamp": "..."
}
```

#### fetch_dragon_tiger

```json
{
  "success": true,
  "data": {
    "date": "2025-05-30",
    "items": [
      {
        "symbol": "600519.SH",
        "name": "贵州茅台",
        "close": 1850.00,
        "change_pct": 5.2,
        "turnover_rate": 3.5,
        "net_buy": 120000000.00,
        "buy_seats": ["机构专用", "沪股通专用"],
        "sell_seats": ["中信证券上海分公司"]
      }
    ]
  },
  "timestamp": "..."
}
```

#### fetch_sector

```json
{
  "success": true,
  "data": {
    "sector": "semiconductor",
    "sector_name": "半导体",
    "stock_count": 85,
    "stocks": [
      {
        "symbol": "688981.SH",
        "name": "中芯国际",
        "price": 85.50,
        "change_pct": 2.3
      }
    ],
    "sector_change_pct": 1.8
  },
  "timestamp": "..."
}
```

---

## 五、错误处理设计

### 5.1 错误分类

| 错误类型 | 场景 | HTTP 类比 | 处理方式 |
|---------|------|----------|---------|
| 连接失败 | QMT 客户端未启动 | 503 | 返回 `success: false` + 明确错误信息 |
| 参数错误 | symbol 格式不对、缺少必填参数 | 400 | 返回 `success: false` + 参数提示 |
| 数据不存在 | 股票代码不存在、停牌无数据 | 404 | 返回 `success: true` + data 为 null 或空 |
| 超时 | QMT 响应慢 | 504 | 30 秒后 TimeoutError，返回错误 |
| 内部错误 | xtdata 抛出未知异常 | 500 | 返回 `success: false` + 异常信息 |

### 5.2 错误输出示例

```json
{
  "success": false,
  "data": null,
  "error": "QMT 客户端未连接，请先启动 MiniQMT",
  "timestamp": "2026-05-31T10:30:00+08:00"
}
```

### 5.3 超时机制

- 使用 `signal.SIGALRM` 实现 30 秒超时（仅 Unix/WSL）
- Windows 原生环境使用 `threading.Timer` + `ctypes` 异常注入
- 超时后清理资源，返回超时错误

### 5.4 QMT 连接检测

在每个 fetcher 执行前，检测 QMT 连接状态：

```python
def check_qmt_connection() -> bool:
    """检测 QMT 客户端是否可用。"""
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata
        # 尝试获取一个已知标的的详情来检测连接
        detail = xtdata.get_instrument_detail("000001.SZ")
        return detail is not None and len(detail) > 0
    except Exception:
        return False
```

---

## 六、各命令详细设计

### 6.1 fetch_account（P0，改造现有）

**变更**：
- 新增 `--json` 模式，输出 JSON 到 stdout
- 保留默认模式的 Markdown 输出（向后兼容）
- 从 `QmtTradeGateway.get_asset()` + `get_positions()` 获取数据

**数据流**：
```
CLI args → load_trading_config → QmtTradeGateway → get_asset() + get_positions() → JSON
```

### 6.2 fetch_quote（P0，新增）

**数据源**：
- 实时快照：`xtdata.get_full_tick([symbol])` — 最新价/开高低/量额
- 合约详情：`xtdata.get_instrument_detail(symbol)` — 名称/总股本
- 财务指标：`xtdata.get_financial_data(stock_list=[symbol], table_list=['PershareIndex'])` — PE/PB

**数据流**：
```
CLI args → xtdata.get_full_tick → xtdata.get_instrument_detail → xtdata.get_financial_data → 组装 → JSON
```

**注意**：`get_full_tick` 需要 QMT 客户端处于实时行情连接状态。若 QMT 未连接，降级为 `get_market_data_ex` 获取最近一个交易日的收盘数据。

### 6.3 fetch_financial（P1，新增）

**数据源**：
- 财务报表：`xtdata.get_financial_data(stock_list=[symbol], table_list=['Balance','Income','CashFlow','PershareIndex'])`
- 合约详情：`xtdata.get_instrument_detail(symbol)`

**数据流**：
```
CLI args → xtdata.download_financial_data → xtdata.get_financial_data → 解析/组装 → JSON
```

**关键字段映射**（来自 `QmtFundamentalFetcher` 已有探索）：
- `PershareIndex` 表：`equity_roe`, `s_fa_ocfps`, `s_fa_eps_basic`, `s_fa_bps`, `gear_ratio`, `gross_profit`, `net_profit`, `inc_revenue_rate`, `inc_net_profit_rate`
- 公告日期字段：`m_anntime`

### 6.4 fetch_indicators（P1，新增）

**数据源**：
- K 线数据：`xtdata.get_market_data_ex(field_list=['open','high','low','close','volume'], period=period)`

**技术指标计算**（纯 Python，不依赖 ta-lib）：
- MA（5/10/20/60）：简单移动平均
- RSI（6/14）：相对强弱指标
- MACD（12,26,9）：指数平滑异同移动平均线
- Bollinger Bands（20,2）：布林带
- KDJ（9,3,3）：随机指标
- ATR（14）：平均真实波幅
- 量比：当日成交量 / 过去 5 日平均成交量

**实现位置**：技术指标计算放在 `src/infrastructure/indicators/` 或直接在 CLI 文件内计算（轻量实现）。

### 6.5 fetch_northbound（P2，新增）

**数据源**：需确认 xtdata 是否提供北向资金专用接口。若无，降级方案：
- 从 `xtdata.get_market_data_ex()` 获取沪股通/深股通成分股的资金流向
- 或通过 `xtdata.get_financial_data()` 获取 Top10FlowHolder 等数据

**待确认**：xtdata 北向资金 API 可用性，需要在 `explore_qmt_data.py` 中补充探测。

### 6.6 fetch_dragon_tiger（P2，新增）

**数据源**：需确认 xtdata 是否提供龙虎榜专用接口。

**待确认**：xtdata 龙虎榜 API 可用性。

### 6.7 fetch_sector（P3，新增）

**数据源**：
- 板块成分：`xtdata.get_stock_list_in_sector(sector)`
- 成分股行情：`xtdata.get_full_tick(stocks)` 或 `xtdata.get_market_data_ex()`

**板块名称映射**：
```python
SECTOR_MAP = {
    "semiconductor": "半导体",
    "new_energy": "新能源",
    "pharma": "医药",
    "consumer": "消费",
    "finance": "金融",
    "tech": "科技",
    # ...
}
```

---

## 七、技术指标算法设计

### 7.1 约束

- CLI 层可使用 pandas（仅在 infrastructure 层），但为保持轻量，优先使用纯 Python + list 实现
- 若 xtdata 返回 DataFrame，在 CLI 层转换为 list[dict] 后计算

### 7.2 核心算法

**MA（简单移动平均）**：
```
MA(n) = sum(close[-n:]) / n
```

**RSI（相对强弱指标）**：
```
delta[i] = close[i] - close[i-1]
gain = avg([d for d in delta[-n:] if d > 0])
loss = avg([-d for d in delta[-n:] if d < 0])
RSI = 100 - 100 / (1 + gain/loss)
```

**MACD**：
```
EMA(n) = close * 2/(n+1) + prev_EMA * (n-1)/(n+1)
DIF = EMA(12) - EMA(26)
DEA = DIF * 2/(9+1) + prev_DEA * (9-1)/(9+1)
MACD_HIST = (DIF - DEA) * 2
```

**Bollinger Bands**：
```
MIDDLE = MA(20)
STD = stddev(close[-20:])
UPPER = MIDDLE + 2 * STD
LOWER = MIDDLE - 2 * STD
```

**KDJ**：
```
RSV = (close - lowest_low(9)) / (highest_high(9) - lowest_low(9)) * 100
K = prev_K * 2/3 + RSV * 1/3
D = prev_D * 2/3 + K * 1/3
J = 3 * K - 2 * D
```

**ATR**：
```
TR = max(high-low, abs(high-prev_close), abs(low-prev_close))
ATR(14) = SMA(TR, 14)
```

---

## 八、层职责划分

| 层 | 组件 | 职责 |
|----|------|------|
| Interfaces | `fetch_account.py` | CLI 入口，参数解析，JSON 输出 |
| Interfaces | `fetch_quote.py` | CLI 入口，参数解析，JSON 输出 |
| Interfaces | `fetch_financial.py` | CLI 入口，参数解析，JSON 输出 |
| Interfaces | `fetch_indicators.py` | CLI 入口，参数解析，技术指标计算，JSON 输出 |
| Interfaces | `fetch_northbound.py` | CLI 入口，参数解析，JSON 输出 |
| Interfaces | `fetch_dragon_tiger.py` | CLI 入口，参数解析，JSON 输出 |
| Interfaces | `fetch_sector.py` | CLI 入口，参数解析，JSON 输出 |
| Infrastructure | `QmtTradeGateway` | 复用，获取账户/持仓 |
| Infrastructure | `QmtMarketGateway` | 复用，获取 K 线 |
| Infrastructure | `QmtFundamentalFetcher` | 复用，获取财务数据 |
| Infrastructure | `xtquant_client` | 复用，xtdata 底层调用 |

---

## 九、Hermes Agent 集成方式

### 9.1 调用方式

Hermes Agent 通过 terminal 工具调用 CLI 命令：

```
terminal(
  command="cd /mnt/c/Codes/GoldenHandQuant && "
          "/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe "
          "-m src.interfaces.cli.fetch_quote --symbol 600519.SH"
)
```

### 9.2 响应解析

Agent 解析 stdout 的 JSON 输出：
1. 检查 `success` 字段
2. 若 `success: true`，读取 `data` 字段
3. 若 `success: false`，读取 `error` 字段并报告

### 9.3 错误恢复

- 若 QMT 未连接（`success: false, error: "QMT 客户端未连接"`），Agent 应提示用户启动 QMT
- 若超时，Agent 应重试一次，仍失败则报告

---

## 十、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| xtdata 北向/龙虎榜 API 不可用 | P2 命令无法实现 | 降级为返回空数据 + 说明信息 |
| get_full_tick 需要实时连接 | 非交易时间无法获取实时数据 | 降级为最近交易日收盘数据 |
| signal.SIGALRM 在 Windows 不可用 | 超时机制失效 | 使用 threading.Timer 替代 |
| 技术指标计算精度 | 与专业库有微小差异 | 对齐 xtquant 内置指标，误差 < 0.1% |
| fetch_account 改造破坏现有功能 | Hermes 任务组装失败 | 保留默认 Markdown 模式，JSON 为新增模式 |
