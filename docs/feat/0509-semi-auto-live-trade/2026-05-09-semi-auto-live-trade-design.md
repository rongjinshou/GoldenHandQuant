# 半自动 CLI 交易系统 设计文档

> **目标:** 打通实盘链路的第一步——策略出信号，人工确认后下单。
> **策略:** 支持通过注册表快速切换，首批接入 DualMaStrategy 和 MicroValueStrategy。

## 1. 背景与动机

项目当前状态：
- 回测框架完整（行情推进 → 策略信号 → 风控链 → 撮合 → 结算）
- QMT 交易/行情网关已有基本实现
- 策略、风控、仓位管理等 domain 层组件齐全
- **缺失：** 实盘交易的"最后一公里"——没有主循环、没有信号展示、没有人工确认流程

目标：先跑通半自动链路，验证信号质量，再逐步自动化。

## 2. 核心流程

```
用户运行命令
    ↓
拉取实时行情（QMT get_market_data_ex）
    ↓
策略生成信号（通过 StrategyRegistry 选择策略）
    ↓
风控预检（仓位限制、涨跌停、停牌等）
    ↓
展示信号表格（终端 rich 表格）
    ↓
用户输入序号确认
    ↓
二次确认（逐笔 y/N）
    ↓
下单（QMT place_order）
    ↓
显示订单结果
```

## 3. 信号展示设计

参考专业终端（Bloomberg、掘金量化），信号表格包含以下字段：

| 字段 | 说明 | 来源 |
|------|------|------|
| 序号 | 用户确认用的编号 | 自动生成 |
| 标的代码 | 如 600000.SH | 信号 |
| 方向 | BUY/SELL，带颜色 | 信号 |
| 当前价 | 最新收盘价 | 行情 |
| 挂单价 | 限价单价格（买入上浮 0.1%，卖出下浮 0.1%） | 计算 |
| 止损价 | 策略提供的止损参考（可选） | 策略/风控 |
| 数量 | Sizer 计算的目标数量 | 仓位管理 |
| 所需资金 | 买入时的资金占用 | 计算 |
| 触发原因 | 信号产生的原因说明 | 信号 |
| 策略来源 | 哪个策略产出的 | 信号 |
| 置信度 | 信号强度 | 信号 |

底部状态栏显示：当前策略名、可用资金、当前持仓数量。

## 4. 策略注册表

### 4.1 设计

新增 `src/domain/strategy/registry.py`，解耦策略选择与初始化：

```python
STRATEGY_REGISTRY: dict[str, StrategyConfig] = {
    "dual_ma": StrategyConfig(
        factory=lambda params: DualMaStrategy(),
        strategy_type="bar",
        description="双均线策略 (MA5/MA10 金叉死叉)",
    ),
    "micro_value": StrategyConfig(
        factory=lambda params: MicroValueStrategy(top_n=params.get("top_n", 9)),
        strategy_type="cross_section",
        description="微盘价值质量增强策略",
    ),
}
```

- `strategy_type` 区分策略类别：`bar`（基于 K 线）vs `cross_section`（需要全市场截面数据）
- `factory` 封装初始化逻辑，调用方只需传策略名和参数
- 新增策略只需注册一行，不改调用方代码

### 4.2 两种策略类型的数据需求

**Bar 策略（DualMaStrategy）：**
- 输入：每个 symbol 的最近 N 根 K 线
- 数据来源：`QmtMarketGateway.get_recent_bars()`

**截面策略（MicroValueStrategy）：**
- 输入：全市场股票的当日基本面快照（市值、ROE、现金流等）
- 数据来源：`QmtFundamentalFetcher` + `FundamentalRegistry`
- 额外要求：需要获取股票池列表（沪深 A 股）

## 5. 风控接入

半自动模式下，风控作为"预检"环节，在信号展示前过滤掉不合格的信号：

- **涨跌停检查：** 涨停不追买，跌停不卖出
- **停牌检查：** 停牌标的跳过
- **仓位限制：** 单只不超过总资产的 N%（可配置）
- **资金检查：** 买入时检查可用资金

不通过风控的信号不展示，或以灰色标注"风控拦截"。

## 6. 交互流程

```
$ python -m src.interfaces.cli.live_trade --strategy dual_ma --symbols 600000.SH,000001.SZ

正在加载策略: DualMaStrategy (双均线策略)
正在拉取行情数据...

╔══════════════════════════════════════════════════════════════════════════════════════╗
║  QuantFlow 半自动交易信号                                      2026-05-09 14:30:00  ║
╠═════╤───────────╤──────┬─────────┬─────────┬─────────┬────────┬────────┬────────────╣
│ 序号 │   标的     │ 方向 │  当前价  │  挂单价  │  止损价  │ 数量   │ 所需资金 │   触发原因  │
╞═════╪═══════════╪══════╪═════════╪═════════╪═════════╪════════╪════════╪════════════╡
│  1  │ 600000.SH │ BUY  │  12.50  │  12.52  │  11.88  │  500   │  6,260 │ MA5>MA10   │
│  2  │ 000001.SZ │ SELL │  15.30  │  15.28  │    -    │  300   │  4,584 │ MA5<MA10   │
╚═════╧═══════════╧══════╧═════════╧═════════╧═════════╧════════╧════════╧════════════╝
策略: DualMaStrategy  |  可用资金: 500,000  |  当前持仓: 3 只

输入序号确认 (逗号分隔, a=全部, q=退出): 1

⚠ 确认下单: BUY 600000.SH 500股 @ 12.52 (约 ¥6,260)? [y/N]: y
✅ 订单已提交: order_id=12345

输入序号确认 (...): q
已退出，未执行剩余信号。
```

## 7. 文件结构

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/domain/strategy/registry.py` | 策略注册表，统一策略发现与初始化 |
| `src/application/live_signal_service.py` | 编排服务：拉行情 → 跑策略 → 过风控 → 产出展示信号 |
| `src/interfaces/cli/live_trade.py` | CLI 入口：参数解析、信号展示、交互确认、下单 |
| `config/live_trade.yaml` | 实盘配置（QMT 路径、账号、默认持仓比例等） |
| `tests/domain/strategy/test_registry.py` | 策略注册表单元测试 |
| `tests/application/test_live_signal_service.py` | 信号服务单元测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/interfaces/cli/run_backtest.py` | 重构为使用 StrategyRegistry 替代 if/else |

## 8. 不做的事（YAGNI）

- **不做 daemon/定时循环：** 半自动模式由人驱动，跑一次退出，想看信号再运行
- **不做持仓持久化：** QMT 是持仓的唯一真实来源，直接查询最可靠
- **不做止损止盈自动单：** 半自动阶段由人判断
- **不做 Web/消息推送：** 后续迭代

## 9. 配置文件设计

```yaml
# config/live_trade.yaml

qmt:
  path: "C:/国金QMT/userdata_mini"
  session_id: 1
  account_id: "your_account_id"
  account_type: "STOCK"

trading:
  default_position_ratio: 0.1  # 单只默认仓位比例
  slippage_buy: 0.001          # 买入滑点 0.1%
  slippage_sell: 0.001         # 卖出滑点 0.1%

strategy:
  name: "dual_ma"              # 默认策略
  params: {}
  # micro_value 可配置:
  # params:
  #   top_n: 9
```

## 10. 验收标准

1. `python -m src.interfaces.cli.live_trade --strategy dual_ma --symbols 600000.SH` 能运行
2. 信号表格正确展示（方向、价格、数量、原因）
3. 输入序号 → 二次确认 → 下单成功（或 QMT 未连接时优雅报错）
4. 策略切换 `--strategy micro_value` 能正常工作
5. 所有新代码有单元测试，现有测试不被破坏
6. `ruff check` 通过
