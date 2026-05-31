# ML 因子挖掘引擎 — 设计文档

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 技术设计
**状态**: 草案
**关联文档**: `2026-05-30-system-roadmap-design.md` (子项目 1.4 + 1.5)

---

## 一、概述

### 1.1 目标

构建 ML 因子挖掘引擎，实现从基础特征自动生成候选因子、评估有效性、训练预测模型、将有效因子入库的全流程自动化。每周自动挖掘 10+ 个候选因子，筛选 1-2 个有效因子加入策略库。

### 1.2 与现有系统的关系

```
现有系统                          新增模块
─────────                        ─────────
StockSnapshot (50+ 字段)    ──→  AutoFeatureCombiner (生成 100+ 组合特征)
Factor Protocol              ←──  MinedFactor (适配器，自动注册)
FactorScorer                 ──→  复用 percentile_rank / weighted_combine
FeaturePipeline              ──→  扩展 _compute_bar_metrics（新增基础特征）
BacktestAppService           ←──  FactorValidator（调用回测验证因子)
MultiFactorStrategy          ←──  动态加载挖掘出的因子
ModelLoader                  ──→  扩展支持 LightGBM
InferenceEngine              ──→  复用预测能力
```

### 1.3 设计原则

- **Domain 红线不变**: ML 代码全部在 `src/infrastructure/ml_engine/`，domain 层零第三方依赖
- **渐进式集成**: 挖掘出的因子通过 `MinedFactor` 适配器适配现有 `Factor` Protocol，无需修改 `MultiFactorStrategy`
- **时间序列安全**: 所有训练/评估严格使用时间序列切分，杜绝未来信息泄露
- **轻量优先**: 首选 LightGBM（速度快、效果好），暂不引入 MLflow 等重依赖

---

## 二、系统架构

### 2.1 模块总览

```
src/infrastructure/ml_engine/
├── feature_pipeline.py          # 现有：基础特征提取
├── feature_combiner.py          # 新增：自动特征组合
├── factor_evaluator.py          # 新增：IC/IR/分层回测评估
├── factor_miner.py              # 新增：挖掘流程编排
├── training_pipeline.py         # 新增：LightGBM 训练管道
├── factor_repository.py         # 新增：因子存储与检索
├── inference.py                 # 现有：推理引擎
└── model_loader.py              # 现有：模型加载（扩展 LightGBM）

src/domain/strategy/factors/
├── base.py                      # 现有：Factor Protocol
└── mined_factor.py              # 新增：挖掘因子适配器
```

### 2.2 数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                     因子挖掘流程 (每周运行)                        │
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐          │
│  │ 历史数据  │──→│ 特征工程      │──→│ 候选因子生成    │          │
│  │ (Bar +   │    │ AutoFeature   │    │ 100+ 组合特征  │          │
│  │ Snapshot)│    │ Combiner      │    │               │          │
│  └──────────┘    └──────────────┘    └───────┬───────┘          │
│                                              │                  │
│                                              ▼                  │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐          │
│  │ 因子入库  │←──│ 深度验证      │←──│ 快速筛选       │          │
│  │ Repository│    │ Backtest      │    │ IC>0.03       │          │
│  │           │    │ Sharpe>1.0   │    │ IR>0.5        │          │
│  └──────────┘    └──────────────┘    └───────────────┘          │
│       │                                                        │
│       ▼                                                        │
│  ┌──────────┐    ┌──────────────┐                              │
│  │ 策略集成  │──→│ ML 预测模型   │                              │
│  │ MultiFactor│   │ LightGBM    │                              │
│  └──────────┘    └──────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、模块设计

### 3.1 AutoFeatureCombiner — 自动特征组合

**职责**: 从 `StockSnapshot` 的 50+ 字段自动生成 100+ 组合特征。

#### 3.1.1 基础特征池

从 `StockSnapshot` 提取所有数值字段作为基础特征（当前约 50 个）：

```python
# 价格类: open, high, low, close, prev_close
# 成交量: volume
# 基本面: market_cap, roe_ttm, ocf_ttm, pe_ratio, pb_ratio,
#         roa_ttm, gross_margin, net_margin, asset_turnover,
#         current_ratio, debt_to_equity, pcf_ratio, ps_ratio,
#         dividend_yield, earnings_growth, revenue_growth
# 技术指标: return_5d, return_20d, return_60d,
#           volatility_20d, volatility_60d, turnover_rate,
#           avg_turnover_20d, rsi_14, macd, macd_signal,
#           ma_5, ma_20, ma_60, high_20d, low_20d,
#           atr_14, skewness_20d, illiquidity_20d, obv_slope_20d
# 衍生: high_low_range, close_position, gap
```

#### 3.1.2 组合算子

| 类别 | 算子 | 示例 | 预计生成数 |
|------|------|------|-----------|
| 算术 | `+`, `-`, `*`, `/` | `return_5d / pe_ratio` | ~50 |
| 排名 | `rank(x)` | `rank(roe_ttm)` | ~50 |
| 变化率 | `delta(x, n)` | `delta(pe_ratio, 20)` | ~20 |
| 移动平均 | `ma(x, n)` | `ma(rsi_14, 5)` | ~20 |
| 标准化 | `zscore(x)` | `zscore(volatility_20d)` | ~20 |
| 交互 | `x * y` | `roe_ttm * earnings_growth` | ~30 |

**总计**: 约 200 个候选特征（基础 50 + 组合 150）。

#### 3.1.3 组合策略

采用**分层组合**而非穷举：

1. **同域组合**: 基本面 x 基本面、技术 x 技术（语义相近，组合意义大）
2. **跨域组合**: 基本面 x 技术（捕捉估值与动量的交互效应）
3. **排名组合**: `rank(A) + rank(B)`（消除量纲差异）
4. **比率组合**: `A / B`（标准化后的相对值）

**不做的组合**（避免噪声）：
- 不做三元及以上组合（A op B op C）
- 不做同类指标的冗余组合（如 `ma_5 / ma_20` 已由 `ma5_cross` 覆盖）

#### 3.1.4 接口设计

```python
class AutoFeatureCombiner:
    """自动特征组合器。"""

    def generate_combinations(
        self,
        snapshots: list[StockSnapshot],
        strategy: str = "standard",  # "standard" | "aggressive" | "conservative"
    ) -> pd.DataFrame:
        """生成组合特征矩阵。

        Args:
            snapshots: 某一日的全市场快照。
            strategy: 组合策略，控制生成数量。

        Returns:
            DataFrame, index=symbol, columns=feature_name, values=feature_value。
        """
        ...

    def get_feature_names(self) -> list[str]:
        """返回所有生成的特征名称。"""
        ...
```

#### 3.1.5 性能约束

- 单次组合生成 < 5 秒（全市场 5000 只股票）
- 内存占用 < 500MB（使用 float32 而非 float64）
- 使用 numpy 向量化运算，禁止 Python 循环遍历股票

---

### 3.2 FactorEvaluator — 因子有效性评估

**职责**: 计算 IC/IR、执行分层回测、生成因子评估报告。

#### 3.2.1 IC（信息系数）计算

```python
IC_t = SpearmanRank(Factor_t, Return_{t+1..t+N})
```

- 使用 **Spearman 秩相关**（对异常值鲁棒）
- 计算每期截面 IC，取时间序列均值
- 前瞻期 N = 5/10/20 日（默认 20 日）

#### 3.2.2 IR（信息比率）计算

```python
IR = mean(IC) / std(IC)
```

- IR > 0.5 表示因子有稳定预测能力
- IR > 1.0 表示因子优秀

#### 3.2.3 分层回测

将股票按因子值分为 5 组（quintile），计算每组的：
- 年化收益率
- 夏普比率
- 最大回撤
- 组间收益单调性

**单调性检验**: 高分组收益 > 中分组收益 > 低分组收益，且差异显著。

#### 3.2.4 因子衰减分析

计算因子在不同前瞻期（5/10/20/60 日）的 IC，绘制衰减曲线：
- 快速衰减：短线因子（适合月度调仓）
- 缓慢衰减：长线因子（适合季度调仓）

#### 3.2.5 接口设计

```python
@dataclass(slots=True, kw_only=True)
class FactorEvalResult:
    """因子评估结果。"""
    factor_name: str
    ic_mean: float           # 平均 IC
    ic_std: float            # IC 标准差
    ir: float                # 信息比率
    ic_positive_ratio: float # IC > 0 的比例
    monotonicity: float      # 分层单调性评分 (0-1)
    sharpe_by_group: list[float]  # 每组夏普比率
    annual_return_by_group: list[float]
    ic_decay: dict[int, float]    # {前瞻期: IC} 衰减曲线
    is_effective: bool       # 是否通过筛选阈值


class FactorEvaluator:
    """因子有效性评估器。"""

    def evaluate_single(
        self,
        factor_values: pd.DataFrame,    # index=date, columns=symbol
        forward_returns: pd.DataFrame,  # index=date, columns=symbol
        forward_days: int = 20,
    ) -> FactorEvalResult:
        """评估单个因子的有效性。"""
        ...

    def evaluate_batch(
        self,
        factor_matrix: pd.DataFrame,    # 多因子列
        forward_returns: pd.DataFrame,
        top_n: int = 20,
    ) -> list[FactorEvalResult]:
        """批量评估，返回按 IR 排序的 top_n 结果。"""
        ...
```

#### 3.2.6 筛选阈值

| 阶段 | 指标 | 阈值 | 说明 |
|------|------|------|------|
| 快速筛选 | IC mean | > 0.03 | 基本有效性 |
| 快速筛选 | IR | > 0.5 | 稳定性 |
| 快速筛选 | IC positive ratio | > 55% | 方向一致性 |
| 深度验证 | 分层夏普 | > 1.0 (top组) | 可交易性 |
| 深度验证 | 单调性 | > 0.8 | 因子逻辑一致性 |
| 深度验证 | 最大回撤 | < 30% (top组) | 风险可控 |

---

### 3.3 TrainingPipeline — LightGBM 训练管道

**职责**: 训练 LightGBM 模型预测未来收益。

#### 3.3.1 标签设计

```python
# 分类标签（二分类：涨/跌）
label = 1 if forward_return > 0 else 0

# 回归标签（连续收益）
label = forward_return

# 分位标签（五分类）
label = quintile_rank(forward_return)  # 0, 1, 2, 3, 4
```

**首选**: 二分类（涨/跌），输出概率作为排序依据。

#### 3.3.2 数据切分

采用**滚动时间窗口**（Walk-Forward），杜绝未来信息泄露：

```
|←── 训练集 (3年) ──→|←─ 验证集 (6月) ─→|←─ 测试集 (6月) ─→|
|  2020-01  ~ 2022-12 | 2023-01 ~ 2023-06 | 2023-07 ~ 2023-12 |
                     →|                   |→
          滚动 6 个月 →|                   |→
|←── 训练集 (3年) ──→|←─ 验证集 (6月) ─→|←─ 测试集 (6月) ─→|
|  2020-07  ~ 2023-06 | 2023-07 ~ 2023-12 | 2024-01 ~ 2024-06 |
```

- 训练窗口: 3 年（约 750 个交易日）
- 验证窗口: 6 个月
- 测试窗口: 6 个月
- 滚动步长: 6 个月

#### 3.3.3 超参数优化

使用 Optuna 贝叶斯优化：

```python
@dataclass(slots=True, kw_only=True)
class LGBMConfig:
    """LightGBM 训练配置。"""
    n_estimators: int = 500
    learning_rate: float = 0.05
    max_depth: int = 6
    num_leaves: int = 31
    min_child_samples: int = 50
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.1
    reg_lambda: float = 0.1
    random_state: int = 42
```

Optuna 搜索空间:
- `n_estimators`: [100, 1000]
- `learning_rate`: [0.01, 0.1]
- `max_depth`: [3, 8]
- `num_leaves`: [15, 63]
- `min_child_samples`: [20, 200]
- `subsample`: [0.6, 1.0]
- `colsample_bytree`: [0.6, 1.0]

优化目标: 验证集 IC（而非准确率，因为我们要的是排序能力）。

#### 3.3.4 模型评估

| 指标 | 阈值 | 说明 |
|------|------|------|
| 样本外 IC | > 0.05 | 预测准确性 |
| 分层夏普 (top组) | > 1.5 | 可交易性 |
| 特征重要性 Top10 | 可解释 | 不全是噪声特征 |
| 训练/验证 IC 差异 | < 50% | 过拟合检测 |

#### 3.3.5 接口设计

```python
class TrainingPipeline:
    """LightGBM 训练管道。"""

    def __init__(self, config: LGBMConfig | None = None) -> None: ...

    def prepare_dataset(
        self,
        snapshots_by_date: dict[date, list[StockSnapshot]],
        forward_days: int = 20,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """准备训练数据集: 特征矩阵 + 标签。"""
        ...

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ) -> lgb.LGBMClassifier:
        """训练模型。"""
        ...

    def optimize_hyperparams(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        n_trials: int = 50,
    ) -> LGBMConfig:
        """Optuna 超参数优化。"""
        ...

    def walk_forward_train(
        self,
        snapshots_by_date: dict[date, list[StockSnapshot]],
        train_years: int = 3,
        val_months: int = 6,
        test_months: int = 6,
        step_months: int = 6,
    ) -> list[WalkForwardResult]:
        """滚动窗口训练 + 评估。"""
        ...
```

---

### 3.4 FactorRepository — 因子存储与检索

**职责**: 持久化存储挖掘出的因子，提供检索和加载能力。

#### 3.4.1 存储结构

```
data/factors/
├── registry.json              # 因子注册表（元数据）
├── mined/                     # 挖掘因子的特征值
│   ├── factor_001.parquet     # 每个因子一个 parquet
│   ├── factor_002.parquet
│   └── ...
└── models/                    # 训练好的模型
    ├── lgbm_v001.pkl
    └── ...
```

#### 3.4.2 registry.json 结构

```json
{
  "version": 1,
  "factors": {
    "mined_return_5d_div_pe": {
      "name": "mined_return_5d_div_pe",
      "expression": "return_5d / pe_ratio",
      "category": "cross_domain",
      "created_at": "2026-06-01",
      "metrics": {
        "ic_mean": 0.058,
        "ir": 1.2,
        "sharpe_top_group": 1.5,
        "monotonicity": 0.85
      },
      "status": "active",
      "inverted": false,
      "parquet_path": "mined/factor_001.parquet"
    }
  }
}
```

#### 3.4.3 接口设计

```python
class FactorRepository:
    """因子存储与检索。"""

    def __init__(self, data_dir: str = "data/factors") -> None: ...

    def save_factor(
        self,
        name: str,
        expression: str,
        factor_values: pd.DataFrame,
        metrics: FactorEvalResult,
    ) -> None:
        """保存挖掘出的因子。"""
        ...

    def load_factor(self, name: str) -> pd.DataFrame:
        """加载因子值。"""
        ...

    def list_factors(
        self,
        status: str = "active",
        min_ir: float = 0.0,
    ) -> list[dict]:
        """列出因子。"""
        ...

    def deactivate_factor(self, name: str, reason: str) -> None:
        """停用因子（衰减或失效时）。"""
        ...

    def to_domain_factor(self, name: str) -> Factor:
        """将存储的因子转换为 domain Factor Protocol 实例。"""
        ...
```

---

### 3.5 MinedFactor — Domain 适配器

**职责**: 将挖掘出的因子适配为 `Factor` Protocol，使 `MultiFactorStrategy` 无需修改即可使用。

```python
# src/domain/strategy/factors/mined_factor.py

class MinedFactor:
    """挖掘因子适配器 — 从预计算的 parquet 加载因子值。"""

    def __init__(self, name: str, values_by_date: dict[str, dict[str, float]]) -> None:
        self.name = name
        self._values_by_date = values_by_date

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        """从预计算值中查找当日因子值。"""
        if not snapshots:
            return {}
        date_key = snapshots[0].date.strftime("%Y-%m-%d")
        return self._values_by_date.get(date_key, {})
```

**关键约束**: `MinedFactor` 在 domain 层，不依赖 pandas/numpy，仅使用标准字典操作。

---

### 3.6 FactorMiner — 挖掘流程编排

**职责**: 串联特征组合 → 快速筛选 → 深度验证 → 因子入库的完整流程。

```python
class FactorMiner:
    """因子挖掘主流程。"""

    def __init__(
        self,
        combiner: AutoFeatureCombiner,
        evaluator: FactorEvaluator,
        validator: FactorValidator,
        repository: FactorRepository,
    ) -> None: ...

    def mine(
        self,
        snapshots_by_date: dict[date, list[StockSnapshot]],
        target_count: int = 10,
    ) -> MiningReport:
        """执行一次完整的因子挖掘。

        流程:
        1. AutoFeatureCombiner 生成候选特征 (200+)
        2. FactorEvaluator 快速筛选 (IC>0.03, IR>0.5) → ~20 候选
        3. FactorValidator 深度验证 (分层回测, Sharpe>1.0) → ~3 候选
        4. FactorRepository 入库

        Returns:
            MiningReport: 挖掘报告（候选数、通过数、入库因子列表）。
        """
        ...
```

---

### 3.7 ModelLoader 扩展

在现有 `ModelLoader` 中增加 LightGBM 支持：

```python
def load_lightgbm(self, model_name: str) -> Any:
    """加载 LightGBM 模型（惰性缓存）。"""
    import lightgbm as lgb
    if model_name not in self._cache:
        path = self._model_dir / f"{model_name}.pkl"
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        self._cache[model_name] = lgb.Booster(model_file=str(path))
    return self._cache[model_name]
```

---

## 四、与现有系统的集成方案

### 4.1 因子自动注册

挖掘出的因子通过以下流程自动注册到 `MultiFactorStrategy`：

```
FactorRepository.save_factor()
    → 生成 MinedFactor 实例
    → 更新 registry.json
    → 下次 create_strategy("multi_factor") 时自动加载
```

修改 `_build_multi_factor` 函数，增加从 `FactorRepository` 加载挖掘因子的逻辑：

```python
def _build_multi_factor(params: dict[str, Any]) -> BaseStrategy:
    # ... 现有 30 个因子的加载逻辑不变 ...

    # 新增：加载挖掘因子
    try:
        repo = FactorRepository()
        mined_factors = repo.list_factors(status="active", min_ir=0.5)
        for info in mined_factors:
            factor = repo.to_domain_factor(info["name"])
            factor_map[info["name"]] = factor
            default_weight = info.get("metrics", {}).get("ir", 1.0)
            weights_dict.setdefault(info["name"], default_weight)
    except Exception:
        pass  # 仓库不存在时静默跳过

    # ... 后续逻辑不变 ...
```

### 4.2 INVERT_FACTORS 扩展

挖掘因子的 `inverted` 属性存储在 `registry.json` 中。评估阶段自动判断：
- 如果 IC < 0，说明因子方向与收益负相关，标记 `inverted = True`
- `MinedFactor.compute()` 返回原始值，由 `FactorScorer.percentile_rank(invert=...)` 处理

### 4.3 回测验证复用

`FactorValidator` 复用 `BacktestAppService.run_backtest()`：

```python
class FactorValidator:
    """通过分层回测验证因子有效性。"""

    def validate_with_backtest(
        self,
        factor: Factor,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        market_gateway: IBacktestMarketGateway,
        trade_gateway: IBacktestBroker,
    ) -> BacktestReport:
        """使用因子构建简单策略进行回测验证。"""
        strategy = MultiFactorStrategy(
            factors=[factor], weights=[1.0], top_n=10,
        )
        # ... 调用 BacktestAppService ...
```

---

## 五、数据需求

### 5.1 输入数据

| 数据类型 | 来源 | 时间跨度 | 更新频率 |
|---------|------|---------|---------|
| 日线 OHLCV | QMT/Tushare | 5 年+ | 每日 |
| 基本面数据 | Tushare | 5 年+ | 季度 |
| 复权因子 | QMT/Tushare | 5 年+ | 每日 |

### 5.2 存储估算

| 数据项 | 大小 |
|--------|------|
| 原始特征矩阵 (5000股 x 50特征 x 1250日) | ~2.5 GB (float32) |
| 组合特征矩阵 (5000股 x 200特征 x 1250日) | ~10 GB (float32) |
| 因子值 parquet (单个因子) | ~25 MB |
| LightGBM 模型 | ~5 MB |
| 总存储需求 | ~15 GB |

---

## 六、依赖项

### 6.1 新增 Python 依赖

```toml
[project.optional-dependencies]
ml = [
    "lightgbm>=4.0",
    "optuna>=3.0",
    "scipy>=1.10",     # spearmanr
]
```

### 6.2 不引入的依赖（暂不需要）

- ~~MLflow~~: 初期用 registry.json 管理模型版本，Phase 2 再考虑
- ~~DVC~~: 数据量不大，git + parquet 足够
- ~~XGBoost~~: LightGBM 足够，作为备选保留 model_loader 中的实现

---

## 七、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 过拟合 | 挖掘出的因子实盘失效 | 严格时间序列切分 + 样本外验证 + 定期衰减检查 |
| 特征泄露 | 未来信息污染训练数据 | 标签计算使用 shift(-N)，确保因果关系 |
| 计算量大 | 全市场 5 年数据组合耗时 | 分批计算 + parquet 缓存 + float32 |
| 因子失效 | 市场环境变化导致因子失效 | 每月重新评估入库因子 + 自动停用机制 |
| 数据质量 | 基本面数据缺失/延迟 | 数据校验 + 缺失值填充策略 |

---

## 八、成功标准

| 指标 | 目标值 | 验证方式 |
|------|--------|---------|
| 候选因子生成数 | > 100 个/次 | 每次挖掘日志 |
| 快速筛选通过率 | 5-10% (5-20 个) | 筛选报告 |
| 深度验证通过率 | 10-20% (1-3 个) | 验证报告 |
| 入库因子 IC | > 0.05 | 持续监控 |
| 入库因子 IR | > 1.0 | 持续监控 |
| 挖掘全流程耗时 | < 2 小时 | 性能日志 |
| ML 模型样本外 IC | > 0.05 | Walk-Forward 评估 |

---

**文档结束**
