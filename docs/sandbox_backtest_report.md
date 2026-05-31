# 微盘价值质量增强策略 — 沙盒回测端到端打通报告

> 时间: 2026-05-03 ~ 2026-05-04
> 回测区间: 2024-01-01 ~ 2024-04-30
> 数据源: QMT (xtquant.xtdata)
> 策略: MicroValueStrategy (top_n=9)

---

## 一、Phase 0: 架构理解

### 1.1 截面策略工作流

```
QMT xtdata → FundamentalRegistry (by ann_date 双索引)
     ↓
MockMarketGateway.load_bars() ← QmtHistoryDataFetcher
     ↓
CrossSectionalStrategyRunner.evaluate() [每日循环]
     ├─ FeaturePipeline.build_cross_section() → list[StockSnapshot]
     ├─ SystemRiskGate.check_gate() → GateResult (中证1000 MA20 门禁)
     ├─ MicroValueStrategy.generate_cross_sectional_signals()
     │   └─ 日历熔断(1/4月空仓) → 错峰调仓(仅周二) → 过滤链 → 市值排序取top9
     ├─ RiskSignalGenerator.evaluate() → SELL信号 (止损/破板)
     ├─ 信号合并 + 门禁过滤BUY
     ├─ EqualWeightSizer.calculate_targets() → list[OrderTarget]
     └─ SELL优先排序 → OrderExecutionEngine → MockTradeGateway撮合
```

### 1.2 关键设计要点

- **FundamentalRegistry 双索引**: 以 `ann_date`（公告日期）而非 `end_date`（报告期）为时间轴，杜绝未来函数
- **风控双机制**: SystemRiskGate（盘前门禁，仅过滤BUY）+ RiskSignalGenerator（盘后主动产出SELL）
- **A股规则严格执行**: T+1结算、100股整手、涨跌停限制、滑点、流动性限制（单笔≤10%成交量）
- **截面vs时序双轨**: CrossSectionalStrategyRunner 专为截面策略设计

---

## 二、Phase 1: 数据血脉打通

### 2.1 数据源选择

最初尝试 Tushare，但用户 Token 积分不足（~120分），大量接口被拒：

| 接口 | 用途 | 状态 | 所需积分 |
|------|------|------|----------|
| `daily_basic` | 市值 | 无权限 | 2000 |
| `fina_indicator` | ROE/OCF | 无权限 | 2000 |
| `index_weight` | 成分股 | 无权限 | 2000 |
| `index_daily` | 指数日线 | 无权限 | 2000 |
| `stock_basic` | 股票列表 | 限频 1次/小时 | 120 |
| `pro_bar` | K线 | 限频 50次/分钟 | 120 |

**决策**: 用户转向 QMT 本地数据源（xtquant.xtdata），完全绕过 Tushare 限制。

### 2.2 QMT 环境搭建

**问题**: xtquant SDK 未安装，`ModuleNotFoundError: No module named 'xtquant'`

**解决**:
1. 在用户 Downloads 目录找到 xtquant: `C:\Users\11492\Downloads\xtquant_250807\xtquant`
2. 复制到项目 `libs/xtquant/` 目录
3. `xtquant_client.py` 已有路径检测逻辑，自动加载

**教训**: xtquant 不在 PyPI，需要从 QMT 客户端安装目录或官方下载获取。

### 2.3 基本面数据加载 (QmtFundamentalFetcher)

**问题1**: 全市场 5202 只股票一次性拉取，速度极慢

**解决**: 在 `run_backtest.py` 中限制为 500 只随机抽样：
```python
max_stocks = 500
if len(stock_universe) > max_stocks:
    random.seed(42)
    stock_universe = sorted(random.sample(stock_universe, max_stocks))
```

**问题2**: `download_financial_data` 同步版卡死

**现象**: 调用 `xtdata.download_financial_data(stock_list=[sym])` 后程序永久阻塞。

**解决**: 跳过财务数据下载，直接调用 `get_financial_data`。QMT 本地已有缓存数据，无需下载：
```python
# 2. 财务数据: 直接获取（QMT 本地已有，无需下载）
# 注意: download_financial_data 同步版会卡死，已跳过
```

**问题3**: `get_market_data_ex` 返回空数据

**现象**: 不调用 `download_history_data` 时，`get_market_data_ex` 返回空 DataFrame。

**解决**: 在获取收盘价前，先调用同步下载：
```python
for sym in batch:
    xtdata.download_history_data(
        stock_code=sym, period='1d',
        start_time=qmt_start, end_time=qmt_end,
    )
```

**最终结果**: 500 只股票 → 484 只有数据 → 37,694 条快照

### 2.4 K线数据加载 (QmtHistoryDataFetcher)

**问题1**: `fill_data=True` 导致返回空数据

**现象**: `get_market_data_ex(fill_data=True)` 返回空，但 `fill_data=False` 正常返回 78 行。

**测试验证**:
```
dividend_type='none',  fill_data=True  → NO DATA
dividend_type='none',  fill_data=False → NO DATA
dividend_type='front', fill_data=True  → NO DATA  ← 问题所在
dividend_type='front', fill_data=False → 78 rows  ← 正常
```

**根因**: QMT 的前复权数据在 `fill_data=True` 时可能触发异常的填充逻辑，导致返回空。

**解决**: 将所有 `fill_data=True` 改为 `fill_data=False`。

**教训**: QMT API 的 `fill_data` 参数行为不一致，建议始终使用 `False`。

**问题2**: 大部分股票返回 "No data found"

**根因**: `fill_data=True` 在 `QmtHistoryDataFetcher` 中有两处（`get_market_data_ex` 调用），第一次 `replace_all` 编辑只替换了缩进匹配的实例，第二处遗漏。

**解决**: 手动逐一检查并修复所有 `fill_data=True` 实例。

**教训**: `replace_all` 对缩进敏感，不同缩进层级的相同文本不会被同时替换。编辑后必须验证。

### 2.5 配置适配

**问题1**: `BacktestSettings` 缺少 `benchmark` 字段
```
TypeError: BacktestSettings.__init__() got an unexpected keyword argument 'benchmark'
```

**解决**: 在 `settings.py` 中添加字段：
```python
class BacktestSettings:
    benchmark: str = "000852.SH"

class StrategySettings:
    top_n: int = 9
```

**问题2**: `symbols` 只有指数，策略无法选股

**解决**: 修改 `run_backtest.py`，从 `FundamentalRegistry` 提取股票列表作为回测标的：
```python
stock_universe = sorted({s.symbol for s in snapshots})
backtest_symbols = stock_universe if stock_universe else symbols
```

### 2.6 数据加载最终结果

| 指标 | 数值 |
|------|------|
| 股票池 | 500 只（随机抽样） |
| 基本面快照 | 37,694 条（78 个交易日） |
| K线成功 | 484 只 |
| K线缺失 | 16 只（QMT 无数据） |
| 交叉验证 | 通过（截面 30 只匹配） |

---

## 三、Phase 2: 配置组装与订单排序逻辑

### 3.1 成本配置验证

`backtest.yaml` 已正确配置：
```yaml
costs:
  commission_rate: 0.0002  # 万二佣金
  tax_rate: 0.001          # 千一印花税
  min_commission: 5.0      # 最低5元
  slippage: 0.003          # 千三滑点
```

### 3.2 SELL 优先排序

**已有实现** (`strategy_runner.py:175`):
```python
targets.sort(key=lambda t: 0 if t.direction == OrderDirection.SELL else 1)
```

**问题**: 虽然 SELL 排在 BUY 前面，但 `_execute_targets` 顺序执行所有订单，SELL 资金未即时释放，BUY 仍因资金不足被拒。

**解决**: 修改 `_execute_targets`，显式分离 SELL 和 BUY：
```python
def _execute_targets(self, targets, current_time, account_id):
    sell_targets = [t for t in targets if t.direction == OrderDirection.SELL]
    buy_targets = [t for t in targets if t.direction == OrderDirection.BUY]
    for target in sell_targets + buy_targets:
        # ... 执行订单
```

**效果**: Phase 1 回测中 03-19 仍有 "Insufficient funds" 错误，但这是因为 T+1 结算（卖出资金次日才可用），而非排序问题。

---

## 四、Phase 3: 沙盒回测执行与观测点验证

### 4.1 回测核心指标

| 指标 | 数值 |
|------|------|
| 初始资金 | 1,000,000.00 |
| 最终资金 | 973,393.54 |
| 总收益率 | -2.66% |
| 年化收益率 | -7.88% |
| 最大回撤 | 5.22% |
| 胜率 | 0.00% |
| 总交易次数 | 54 |
| 夏普比率 | -0.86 |
| 索提诺比率 | -1.12 |
| 卡尔马比率 | -1.51 |

### 4.2 观测点验证

#### [观测点1-调仓节奏] ✅ 通过

- 1月/4月无任何 BUY 订单（日历熔断生效）
- 所有 BUY 订单均在周二触发：
  - 02-20(周二)、02-27(周二)、03-05(周二)、03-12(周二)、03-19(周二)
- 策略严格遵守"仅周二调仓"规则

#### [观测点2-组合构建] ✅ 部分通过

- 首批建仓(02-20)：精准买入 9 只股票，股数均为 100 的整数倍
  - 3800, 19200, 800, 700, 1100, 2000, 3300, 2300, 3200
- 后续调仓：部分股票因资金不足未买入
- SELL 订单正确清理旧持仓（02-28/03-01 有卖出）

#### [观测点3-系统熔断] ⚠️ 无法完全验证

- 1月下旬至2月初无任何交易，表明系统拦截了 BUY 信号
- 但 000852.SH 指数数据在 QMT 中未获取到
- SystemRiskGate 可能因指数数据缺失而降级为"始终拦截"

**待修复**: 需要在 QMT 中单独下载 000852.SH 指数数据

#### [观测点4-主动止损] ✅ 通过

- 02-28/03-01 集中卖出 6 只股票，全部亏损：
  - 603931.SH: -1422.09
  - 605133.SH: -2866.82
  - 605287.SH: -1307.60
  - 605319.SH: -3760.17
  - 605166.SH: -646.79
  - 605098.SH: -1179.89
- 这些是非调仓日的 SELL，符合止损/破板行为
- 03-22 至 04-23 持续卖出清理仓位

#### [观测点5-日历与红线过滤] ✅ 通过

- 4月份：仅执行 SELL 订单（04-10 至 04-23 共 8 笔卖出），无任何 BUY
- 日历熔断（4月空仓）正确生效
- 1月份同样无交易

---

## 五、问题清单与解决方案汇总

| # | 问题 | 根因 | 解决方案 | 影响文件 |
|---|------|------|----------|----------|
| 1 | xtquant 未安装 | SDK 在 Downloads 目录 | 复制到 `libs/xtquant/` | - |
| 2 | 全市场 5202 只太慢 | 无限制拉取 | 限制 500 只随机抽样 | `run_backtest.py` |
| 3 | `download_financial_data` 卡死 | QMT 同步版阻塞 | 跳过下载，直接获取 | `qmt_fundamental_fetcher.py` |
| 4 | `get_market_data_ex` 返回空 | 未先调用 `download_history_data` | 获取前先下载 | `qmt_fundamental_fetcher.py` |
| 5 | `fill_data=True` 返回空 | QMT 前复权填充异常 | 改为 `fill_data=False` | `qmt_history_data.py` |
| 6 | `replace_all` 漏替换 | 缩进不同不匹配 | 手动逐一修复 | `qmt_history_data.py` |
| 7 | `BacktestSettings` 缺字段 | YAML 新增字段未同步 | 添加 `benchmark`/`top_n` | `settings.py` |
| 8 | symbols 只有指数 | 配置未包含股票 | 从 Registry 提取股票 | `run_backtest.py` |
| 9 | SELL 资金未即时释放 | 顺序执行所有订单 | 分离 SELL/BUY 执行 | `backtest_app.py` |
| 10 | 指数数据缺失 | QMT 未下载 000852.SH | 待修复 | - |

---

## 六、架构变更记录

### 新增文件
- `src/infrastructure/gateway/qmt_fundamental_fetcher.py` — QMT 基本面数据获取器
- `src/interfaces/cli/data_loader.py` — Tushare 数据加载器（已弃用）
- `src/interfaces/cli/explore_qmt_data.py` — QMT 数据探路脚本

### 修改文件
- `resources/backtest.yaml` — 更新日期范围、数据源为 QMT
- `src/infrastructure/config/settings.py` — 添加 `benchmark`、`top_n` 字段
- `src/infrastructure/gateway/qmt_history_data.py` — 修复 `fill_data`、添加下载步骤
- `src/interfaces/cli/run_backtest.py` — 支持 QMT 数据源、股票列表管理
- `src/application/backtest_app.py` — SELL 优先执行、添加 OrderDirection 导入
- `src/domain/market/services/fundamental_registry.py` — 添加 `load_snapshots` 方法

---

## 七、后续待办

1. **指数数据**: 在 QMT 中单独下载 000852.SH 指数数据，验证 SystemRiskGate
2. **资金管理**: 优化 EqualWeightSizer，考虑可用资金约束
3. **T+1 冲突**: 在 BUY 前检查 SELL 是否已结算（或使用日内结算）
4. **股票池**: 替换为真实中证500成分股（需 QMT 板块数据）
5. **财务数据口径**: QMT 的 `equity_roe` 是季报原始值，非 TTM 滚动，需确认策略兼容性
