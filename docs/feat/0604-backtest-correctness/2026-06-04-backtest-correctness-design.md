# Spec 1 · 回测引擎正确性修复 — 设计文档

| 项 | 值 |
|---|---|
| **状态** | Draft(待用户评审) |
| **创建日期** | 2026-06-04 |
| **文档类型** | 技术设计 / SDD Spec |
| **所属 Epic** | GoldenHandQuant 系统重构(Spec 1 / 3) |
| **后继** | Spec 2 架构治理、Spec 3 广度瘦身(各自独立迭代) |

---

## 一、背景与动机

一次系统诊断(沿「信号 → 成交 → 估值 → 指标」全链路实读源码)发现:回测引擎的**工程骨架**(DDD 分层、A 股规则、~1420 测试全绿)是科班水准,但**量化正确性**存在系统性缺陷,导致部分回测结果不可信。测试全绿恰恰掩盖了问题——单元测试只保证"实现一致性",保证不了"量化方法论正确性"。

### 1.1 现状缺陷清单(带证据定位)

| 编号 | 缺陷 | 证据位置 | 后果 |
|---|---|---|---|
| **P0-1** | 截面策略前视偏差(未来函数) | `application/strategy_runner.py:157-166` + `infrastructure/ml_engine/feature_pipeline.py:56-80` | 用 T 日 close/volume 算因子选股,却用 T 日 open 成交 → **系统性高估** `micro_value` 等核心截面策略收益 |
| **P0-2** | 复权口径割裂 | 成交 `mock_trade.py:141-149`(不复权)vs 估值 `backtest_app.py:397`(前复权) | 成本按不复权记、市值按前复权估;含除权标的建仓即虚假浮盈亏,污染净值曲线与全部指标 |
| **P1-1** | `MockTradeGateway` 无视 `order.price` | `mock_trade.py:141` | runner 算的前复权 open 成交价被丢弃,实际按不复权 close 成交,`order.price` 仅用于 limit 校验 |
| **P1-2** | Sortino 公式错误 | `backtest_report.py:66-79` | 对截断序列减自身均值算样本方差,无正确统计意义 |
| **P1-3** | `realized_pnl` 不含买入费用 | `position.py:46-47` + `mock_trade.py:298-310` | `average_cost` 不计买入佣金 → 单笔盈亏只扣卖出费 → `win_rate`/盈亏比系统性偏乐观 |
| **P1-4** | 涨跌停一律 10%,不分板块 | `mock_trade.py:167`(用 `calculate_price_limits` 默认值) | 创业板/科创板(20%)被错误拒单,ST(5%)被错误成交 |

> P0-1 的铁证:同文件的 `SingleStrategyRunner`(`strategy_runner.py:76`)用 `all_bars[:-1]` **正确剔除了当前 bar**。两个 runner 实现不一致 → 这是疏漏而非有意设计,根因是"两套尺子"。

### 1.2 本 Spec 的定位

本 Spec 是重构 Epic 的**地基**(Spec 1)。回测数字不可信时,其上的任何 ML、架构、功能都是空中楼阁。因此**正确性优先**,且必须建立**金标准测试网**防止缺陷复发。架构治理(DIP、EventBus、domain 因子计算归位)归 Spec 2;广度功能裁剪归 Spec 3。

---

## 二、目标与非目标

### 2.1 目标(Goals)

1. 消除两个 P0 量化正确性缺陷,使回测产出的收益率 / 夏普 / 索提诺 / 回撤 / 胜率**可信**。
2. 修复四个 P1 局部缺陷(成交价语义、Sortino、买入费用、板块涨跌停)。
3. 建立**金标准测试网**(前视、复权)+ 各修复的单元测试,防回归。
4. 在不引入抽象层的前提下,把"信息边界 / 成交时点"收敛成单一职责点,为将来 T+0 留出干净的扩展位。

### 2.2 非目标(Non-Goals,白纸黑字不做)

- ❌ **T+0 / 日内交易**:独立未来 Spec。本次仅保证成交假设边界干净,**不建抽象层、不加配置开关、不写投机性参数**。
- ❌ **不复权 + 分红送股事件**的账本级精度:已决策走前复权研究级(见 DD-1)。
- ❌ **分红 / 送转股事件建模**。
- ❌ 架构治理:DIP 解耦、EventBus 空架子去留、domain 手写高斯消元归位 → **Spec 2**。
- ❌ 广度功能裁剪(ML / 微服务 / Dashboard / 事件溯源)→ **Spec 3**。

---

## 三、关键设计决策(Design Decisions)

### DD-1 · 复权口径:全程前复权

**决策**:回测全链路(因子、成交、成本、估值、涨跌停)统一使用**前复权**价格;退役 `unadjusted_close` 在回测路径的使用。

**理由**:
- 回测器的天职是**评估策略**,不是**与券商对账**。账本级对账是将来实盘网关(`QmtTradeGateway` 从真实账户拉数据)的职责,DDD 接口隔离让二者天然分离。
- 前复权是统一线性缩放,在同一坐标系内**收益率正确、口径自洽**,且**分红已被编码进价格**(无需单独建模分红再投资)。
- 数据层早已是前复权(CLAUDE.md 规定 `get_market_data_ex(dividend_type='front')`),前复权是阻力最小、最不易错的路径。

**否决的替代方案**:
- *不复权 + 分红事件*:实盘账本级精度,但需分红送转股数据 + 除权日事件处理,研究阶段是纯负担,工作量超出本 Spec。
- *不复权 + 不处理分红*:仅消除"不一致"却未消除"不正确"(除权日仍有跳空式虚假盈亏)。

### DD-2 · 成交时点:方案 A(信息 bar / 成交 bar 分离)

**决策**:回测推进到 T 这根 bar 时,显式区分:
- **信息边界** `info_bars = recent[:-1]`:策略 / 因子只能看到截至 **T-1** 收盘的数据。
- **成交 bar** `exec_bar = recent[-1]`:T 日。成交价 = `exec_bar.open`(前复权),估值价 = `exec_bar.close`(前复权)。

语义:**T-1 收盘信息 → T 开盘成交**,信息时点严格早于成交时点,无前视。

**理由**:与已正确的 `SingleStrategyRunner` 语义一致;改动最小;"信息 bar / 成交 bar 分离"恰好是为 T+0 预留的单一职责点。

**否决的替代方案**:*方案 B(保留当前 bar 算因子,成交推到 T+1 开盘)*——与 A 在结果上等价(都是"昨收信息→次日开盘成交"),但需改回测主循环结构、预取下一根 bar,复杂度高一截,YAGNI。

### DD-3 · 成交价语义:`MockTradeGateway` 尊重 `order.price`

**决策**:`place_order` 用 runner 传入的 `order.price`(前复权 open)计算成交价(再叠加滑点),移除 `unadjusted_close` 成交分支;涨跌停校验改用前复权 `prev_close`。

**理由**:DD-1 + DD-2 的必然推论。前复权下涨跌停的**比例判断不变**,且除权日前复权序列连续(反映剔除除权后的真实涨跌),涨跌停判断**自动正确**,无需不复权价。

### DD-4 · 两个 runner 统一:提取极简共享单元

**决策**:把"从 `recent` 派生 `(info_bars, exec_bar, 成交价, 估值价)`"的约定,提取为一个**极简共享单元**(纯值对象 + 派生函数),两个 runner 共用。

**理由**:诊断实锤的病根是"两套尺子"——两个 runner 各写各的派生逻辑才让截面 runner 跑偏。只修截面 runner 是治标;把约定收敛到一处才治本,且这一处就是 T+0 的扩展点。

**约束(守住不过度设计)**:该单元**无配置、无开关、无策略模式**,仅把已重复且已出错的约定归一(DRY),不是投机抽象。

**否决的替代方案**:*只改截面 runner*(治标,留"两套尺子"隐患);*两 runner 各自显式命名但不提取*(仍是两段代码,易再次跑偏)。

### DD-5 · 买入费用计入 `average_cost`

**决策**:`Position.on_buy_filled` 增 `fee` 参数(默认 `0.0`),成本基 = `volume * price + fee`。买入费用(佣金 + 过户费)计入持仓成本。

**理由**:让 `realized_pnl = (sell_price − average_cost)×vol − 卖出费` 天然反映**双边费用**,是标准的移动加权成本做法。`fee` 默认 0 保证向后兼容。

### DD-6 · 板块涨跌停按代码前缀识别;ST 降级

**决策**:新增 domain 纯函数 `get_price_limit_ratio(symbol, is_st=False)`,按代码前缀返回限幅。ST(5%)因需 `is_st` 数据源、而 `mock_trade` 当前不持有基本面,**本次降级**:`is_st` 默认 `False`,留 TODO,作为已知限制(见 §6)。

**理由**:按代码前缀的板块识别(科创/创业/北交所/主板)是最常见的错误来源且数据完全可得;ST 限幅依赖数据源,不应阻塞本 Spec。

### DD-7 · 实施编排:核心 → 指标 → 测试,每批 TDD

**决策**:分三批,每批内严格 TDD(先写会失败的复现测试,再修复转绿):
1. **批次①** 成交假设统一(P0-1 / P0-2 / P1-1 / DD-4 共享单元)——高度耦合,一起改。
2. **批次②** 独立指标修正(P1-2 / P1-3 / P1-4)——逐个清。
3. **批次③** 金标准防回归测试 + 现有测试预期更新。

**理由**:耦合的合并改(避免反复改同一段代码)、独立的拆开改(风险隔离),测试加固收尾。

---

## 四、详细设计

### 4.1 批次①:成交假设统一

#### 4.1.1 数据流:修复前 → 修复后

```
【修复前】recent[-1] 一根 bar 既算因子又当成交价
  因子    : build_cross_section(history = recent  ← 含当前 bar)   用 T 日 close   ❌ 前视
  成交价  : recent[-1].open → Order(price) → MockGateway 丢弃,改用 unadjusted_close  ❌ 无视 + 不复权
  估值    : recent[-1].close(前复权)                                              ❌ 与成交口径割裂

【修复后】信息 bar / 成交 bar 分离,全程前复权
  info_bars = recent[:-1]  (截至 T-1)      exec_bar = recent[-1]  (T 日)
  因子    : build_cross_section(history = info_bars)              用 T-1 及之前   ✅ 无前视
  成交价  : exec_bar.open(前复权) → Order(price) → MockGateway 用 order.price       ✅ 尊重 + 前复权
  估值    : exec_bar.close(前复权)                                                ✅ 同坐标系
  涨跌停  : 前复权 prev_close 算 limit, 前复权 exec_price 比较                       ✅ 同坐标系
```

> **截面 runner 传参映射**(消除歧义):修复后 `build_cross_section` 的 `bars = {sym: window.info_bars[-1]}`(T-1 快照)、`bar_history = {sym: window.info_bars}`(止于 T-1)——当前快照与价量因子历史**均不含成交 bar**。

#### 4.1.2 共享单元(DD-4 的落地形态,实现时可微调)

放置于 `src/domain/backtest/value_objects/bar_window.py`(domain 纯逻辑,守红线;被 application 层 runner 使用,依赖方向正确):

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BarWindow:
    """从一段连续 bar 派生回测决策所需的价格视图,统一信息边界与成交时点。

    信息边界(info_bars)严格早于成交时点(exec_bar),消除前视偏差。
    这是将来 T+0 / 日内交易的单一职责扩展点。
    """
    info_bars: list[Bar]   # 决策可见:截至 T-1(不含成交 bar)
    exec_bar: Bar          # 成交 bar:T 日

    @property
    def exec_price(self) -> float:   # 成交参考价:T 开盘(前复权)
        return self.exec_bar.open

    @property
    def mark_price(self) -> float:   # 估值价:T 收盘(前复权)
        return self.exec_bar.close


def make_bar_window(recent: list[Bar]) -> BarWindow | None:
    """recent 至少需 2 根(1 根成交 + ≥1 根信息),否则返回 None 由调用方跳过。"""
    if len(recent) < 2:
        return None
    return BarWindow(info_bars=recent[:-1], exec_bar=recent[-1])
```

#### 4.1.3 改动文件

| 文件 | 改动 | 性质 |
|---|---|---|
| `domain/backtest/value_objects/bar_window.py` | 新增 `BarWindow` + `make_bar_window` | 新增 |
| `application/strategy_runner.py` | `CrossSectionalStrategyRunner.evaluate`:经 `BarWindow` 取 `info_bars` 喂因子、`exec_price`/`mark_price` 成交估值;`SingleStrategyRunner` 改用同一单元(行为等价重构) | 修 bug + 归一 |
| `infrastructure/mock/mock_trade.py` | `place_order` 用 `order.price` 成交;涨跌停校验改前复权 `prev_close`;删 `unadjusted_close` 成交分支 | 修 bug |
| `domain/market/value_objects/bar.py` | `unadjusted_close` 字段**退役**;物理删除前须 grep 确认 `data_loader` / `history_fetcher` 等加载层无消费者,否则保留字段仅不在回测路径使用 | 可选清理 |

> `feature_pipeline.py:build_cross_section` **不改**——它只是接收 `bars`/`bar_history`,修正的是 runner 传给它的内容。

### 4.2 批次②:指标修正

#### P1-2 · Sortino(`backtest_report.py`)

```python
# 修正:标准下行偏差,目标 MAR = 0,分母用全样本 N
downside_dev = math.sqrt(sum(min(r, 0) ** 2 for r in self.daily_returns) / len(self.daily_returns))
if downside_dev == 0:
    return 0.0
return (mean_return / downside_dev) * math.sqrt(252)
```
**顺手清理**(同文件同类瑕疵):删除 `sharpe_ratio` 中多余的 `if mean_return == 0: return 0.0` 浮点早返回。

#### P1-3 · 买入费用入成本

```python
# domain/account/entities/position.py
def on_buy_filled(self, volume: int, price: float, fee: float = 0.0) -> None:
    ...
    new_cost_basis = volume * price + fee          # 成本含买入费
# infrastructure/mock/mock_trade.py:_simulate_fill 买入分支
position.on_buy_filled(volume, price, fee=commission + transfer_fee)   # 买入无印花税
```

#### P1-4 · 板块涨跌停(`domain/market/value_objects/price_limit.py`)

新增纯函数:

| 代码前缀 | 板块 | 幅度 |
|---|---|---|
| `60*.SH` / `00*.SZ` | 主板 | 10% |
| `688*.SH` | 科创板 | 20% |
| `300* / 301*.SZ` | 创业板 | 20% |
| `8* / 4* / 92*.BJ` | 北交所 | 30% |
| ST / *ST(任意板块) | — | 5%(见 §6 已知限制) |

`mock_trade.place_order` 调用 `get_price_limit_ratio(order.ticker)` 取幅度后再 `calculate_price_limits(prev_close, ratio)`。

### 4.3 批次③:测试网

#### 金标准(守住两个 P0)

| 测试 | 构造 | 断言 |
|---|---|---|
| `test_no_lookahead` | 合成数据:某股仅在 **T 日 close** 跳涨;一个"按当日 close 选股"的策略 | 修复前会买到(偷看),修复后**买不到**;成交不依赖当日 close |
| `test_no_phantom_jump_on_dividend` | 含除权的**前复权连续序列**,买入持有 | 净值曲线无虚假跳空;`total_return` = 手算前复权收益 |

#### 单元测试(各 P1 一个)

- Sortino:给定 `[-0.01, 0.02, -0.03, 0.01]`,手算下行偏差对比 `@property` 输出。
- 买入费用:买 100@10(含费)→ 卖 100@11(含费),断言 `realized_pnl` 含双边费用。
- 板块涨跌停:688 / 300 / 8x / 60 各构造一单触及 ±20% / 10%,断言接受 / 拒绝。
- 成交价语义:断言成交价源自 `order.price`(前复权)而非 `unadjusted_close`。

#### 回归

更新少数锁定旧错误行为的现有测试(截面策略收益、mock 成交价、含费成本、`average_cost` 预期)。测试目录镜像 `src/`;domain 层测试不用 mock。

---

## 五、成功标准(验收清单)

- [ ] `test_no_lookahead` 通过:前视策略修复后超额收益 ≈ 0
- [ ] `test_no_phantom_jump_on_dividend` 通过:含除权净值曲线无虚假跳空
- [ ] 截面策略与单标的策略共用同一 `BarWindow`,无"两套尺子"
- [ ] `MockTradeGateway` 成交价 = `order.price`(前复权);`unadjusted_close` 退出回测路径
- [ ] Sortino = 手算下行偏差值;`sharpe` 多余早返回已清
- [ ] `realized_pnl` 含双边费用;`win_rate`/盈亏比不再虚高
- [ ] 688 / 300 / 8x / 60 板块涨跌停限幅正确
- [ ] 全套测试(更新预期后)绿;`ruff check src/` 无新增告警

---

## 六、已知限制

- **ST 5% 限幅未生效**:`mock_trade` 无 `is_st` 数据源,`get_price_limit_ratio` 的 `is_st` 暂默认 `False`,ST 股按所在板块限幅。代码留 TODO,待数据层提供 `is_st` 后补。**不影响非 ST 标的的正确性**。
- **前复权 ≠ 真实成交价**:成交价是复权价而非历史真实价,刻意接受(DD-1)——评估策略足够,账本对账由实盘网关负责。

---

## 七、风险与缓解

| 风险 | 缓解 |
|---|---|
| 成交价语义变更后大量回测数值变化,现有快照/集成测试预期失效 | 批次③统一更新预期;金标准测试锚定正确性,确保"变化"是变对而非变错 |
| 提取共享单元波及已正确的 `SingleStrategyRunner` | 行为等价重构,现有测试守护;先确认重构后全绿再继续 |
| 删除 `unadjusted_close` 字段破坏数据加载层 | 先退役"使用",物理删除前 grep 全量消费者;有消费者则保留字段仅停用 |
| `on_buy_filled` 签名变更破坏调用方/测试 | `fee` 默认 `0.0` 向后兼容;统一更新 `mock_trade` 调用点与断言 |

---

## 八、未来扩展(Out of Scope,已登记)

- **T+0 / 日内交易**:在 `BarWindow` 这一单一职责点上扩展(日内 bar 序列 + 成交时点),不动其余结构。
- **账本级精度**:实盘对账需求明确时,作为不复权 + 分红事件的独立增强。
- **Spec 2 架构治理 / Spec 3 广度瘦身**:本 Epic 后续迭代。
