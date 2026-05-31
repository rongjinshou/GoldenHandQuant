# ML 端到端收益预测 — 设计文档

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 子系统设计
**状态**: 草案
**所属项目**: GoldenHandQuant Phase 1 — 子项目 1.3 ML 因子挖掘与收益预测

---

## 一、项目背景

### 1.1 现状分析

GoldenHandQuant 已具备 ML 基础框架：

| 组件 | 路径 | 现状 | 局限 |
|------|------|------|------|
| 特征管道 | `infrastructure/ml_engine/feature_pipeline.py` | 从 Bar 序列提取 5 维特征 + 截面快照构建 | 特征维度少（5维），无标签生成 |
| 推理引擎 | `infrastructure/ml_engine/inference.py` | 支持 CatBoost 批量推理 | 仅支持分类（涨跌概率），无回归预测 |
| 模型加载 | `infrastructure/ml_engine/model_loader.py` | CatBoost / XGBoost 惰性缓存加载 | 无 LightGBM，无版本管理 |
| 因子库 | `domain/strategy/factors/` | 30 个因子（价值+质量+动量+波动+技术） | 因子权重人工设定，无法捕捉非线性关系 |
| 策略注册 | `domain/strategy/registry.py` | 3 个策略已注册 | 缺少 ML 驱动策略 |

### 1.2 目标

构建 **ML 驱动的端到端收益预测管道**，实现：

1. **数据管道**：从行情 + 基本面数据自动构建训练集（特征 + 标签）
2. **模型训练**：LightGBM 回归模型，Optuna 超参优化，时间序列交叉验证
3. **模型评估**：样本外 IC > 0.05，分层回测高分组年化 > 基准 + 10%
4. **策略集成**：ML 预测分数 -> 选股信号 -> 注册为策略
5. **模型可解释**：特征重要性分析 + SHAP 值

### 1.3 设计约束

- **Domain 红线**：ML 代码全部放在 `src/infrastructure/ml_engine/`，Domain 层仅通过策略接口交互
- **Python 3.13+**：使用 `list[X]`、`dict[K,V]`、`X | None` 语法
- **Dataclass**：值对象使用 `@dataclass(slots=True, kw_only=True)`
- **无未来信息泄露**：时间序列切分严格遵守时间顺序
- **可回测**：ML 策略必须能在现有回测框架中运行

---

## 二、架构设计

### 2.1 系统分层

```
┌─────────────────────────────────────────────────────────┐
│                    interfaces (CLI)                      │
│  ml_train / ml_predict / ml_evaluate 命令入口            │
├─────────────────────────────────────────────────────────┤
│                   application 层                         │
│  TrainPipelineService   EvaluationService               │
├─────────────────────────────────────────────────────────┤
│                 infrastructure/ml_engine/                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │ Dataset  │ │ Trainer  │ │ Model    │ │ Inference  │ │
│  │ Builder  │ │ (LGBM +  │ │ Registry │ │ Engine     │ │
│  │          │ │  Optuna) │ │          │ │            │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ Label    │ │ TimeCV   │ │ Evaluator│               │
│  │ Generator│ │ Splitter │ │ (IC/分层) │               │
│  └──────────┘ └──────────┘ └──────────┘               │
├─────────────────────────────────────────────────────────┤
│                    domain 层                              │
│  MLReturnPredictionStrategy (继承 CrossSectionalStrategy)│
│  零第三方依赖，仅依赖 Signal / StockSnapshot 等值对象      │
└─────────────────────────────────────────────────────────┘
```

### 2.2 核心设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 模型类型 | LightGBM（回归） | 表格数据 SOTA，训练快，支持缺失值，特征重要性内置 |
| 预测目标 | 未来 N 日收益率（回归） | 比分类保留更多信息；分类可作为下游变体 |
| 交叉验证 | Purged Walk-Forward | 防止时间序列泄露，gap 窗口消除标签重叠 |
| 超参优化 | Optuna TPE | 贝叶斯优化，比网格搜索效率高 10 倍+ |
| 模型格式 | joblib（LightGBM Booster） | 轻量，无需额外依赖 |
| 特征来源 | 复用 StockSnapshot 全部字段 + 衍生特征 | 30+ 现成因子，无需重新计算 |
| 策略集成 | 继承 CrossSectionalStrategy | 复用现有截面策略运行器，零改动接入回测 |

---

## 三、训练数据管道

### 3.1 数据集构建流程

```
Bar 历史数据 + FundamentalSnapshot
         │
         ▼
  FeaturePipeline.build_cross_section()
         │
         ▼
  StockSnapshot[] (每日截面)
         │
         ├── 特征提取 ──→ FeatureMatrix[date][symbol] = features[]
         │
         └── 标签生成 ──→ LabelVector[date][symbol] = future_return
         │
         ▼
  DatasetBuilder.build()
         │
         ▼
  DataFrame: columns=[date, symbol, f1, f2, ..., fn, label]
  存储: data/datasets/{name}_{start}_{end}.parquet
```

### 3.2 特征设计

#### 3.2.1 基础特征（来自 StockSnapshot）

直接从 `StockSnapshot` 提取的字段，共 35 维：

**价量特征（20 维）**：
- 收益率：`return_5d`, `return_20d`, `return_60d`
- 波动率：`volatility_20d`, `volatility_60d`
- 换手率：`turnover_rate`, `avg_turnover_20d`
- 动量：`rsi_14`, `macd`, `macd_signal`
- 均线：`ma_5`, `ma_20`, `ma_60`
- 区间：`high_20d`, `low_20d`
- 风险：`atr_14`, `skewness_20d`, `illiquidity_20d`
- 量价：`obv_slope_20d`

**基本面特征（11 维）**：
- 估值：`pe_ratio`, `pb_ratio`, `pcf_ratio`, `ps_ratio`
- 质量：`roe_ttm`, `roa_ttm`, `gross_margin`, `net_margin`
- 杠杆：`current_ratio`, `debt_to_equity`, `asset_turnover`
- 成长：`earnings_growth`, `dividend_yield`

**基础信息（4 维）**：
- `market_cap`（对数变换）
- `prev_close`

#### 3.2.2 衍生特征（DatasetBuilder 计算）

在基础特征之上构建高阶交互特征：

| 特征 | 公式 | 类型 |
|------|------|------|
| `close_to_ma5` | close / ma_5 - 1 | 偏离度 |
| `close_to_ma20` | close / ma_20 - 1 | 偏离度 |
| `close_to_ma60` | close / ma_60 - 1 | 偏离度 |
| `ma5_to_ma20` | ma_5 / ma_20 - 1 | 均线交叉 |
| `ma20_to_ma60` | ma_20 / ma_60 - 1 | 均线交叉 |
| `vol_ratio_5_20` | volatility_20d 中位数 vs 5d | 波动变化 |
| `turnover_zscore` | (turnover - avg20) / std20 | 异常换手 |
| `high_low_range` | (high_20d - low_20d) / close | 价格区间 |
| `close_position` | (close - low_20d) / (high_20d - low_20d) | 区间位置 |
| `macd_hist` | macd - macd_signal | MACD 柱 |
| `log_market_cap` | log(market_cap) | 规模 |
| `bp_ratio` | 1 / pb_ratio | 账面市值比 |

#### 3.2.3 截面标准化

每日截面内进行 Z-Score 标准化，消除量纲差异：

```python
# 每日截面标准化
for date in dates:
    cross = dataset[dataset.date == date]
    for col in feature_cols:
        mean, std = cross[col].mean(), cross[col].std()
        if std > 0:
            dataset.loc[cross.index, col] = (cross[col] - mean) / std
```

### 3.3 标签生成

#### 3.3.1 预测目标

| 标签类型 | 公式 | 用途 |
|----------|------|------|
| `fwd_return_5d` | `close[t+5] / close[t] - 1` | 主标签：5日前瞻收益 |
| `fwd_return_10d` | `close[t+10] / close[t] - 1` | 备选：10日前瞻收益 |
| `fwd_return_20d` | `close[t+20] / close[t] - 1` | 备选：20日前瞻收益 |
| `fwd_excess_5d` | `fwd_return_5d - benchmark_return_5d` | 超额收益（可选） |

#### 3.3.2 标签处理

- **去极值**：Winsorize 到 [1%, 99%] 分位，避免异常值干扰
- **缺失处理**：标签为 NaN 的行直接丢弃（股票停牌、上市不足 N 日）
- **标签偏移**：标签列与特征列严格错开 N 日，防止数据泄露

### 3.4 DatasetBuilder 接口设计

```python
# src/infrastructure/ml_engine/dataset_builder.py

@dataclass(slots=True, kw_only=True)
class DatasetConfig:
    """数据集构建配置。"""
    label_horizon: int = 5            # 前瞻天数
    label_type: str = "fwd_return"    # "fwd_return" | "fwd_excess"
    winsorize_quantile: float = 0.01  # 去极值分位
    cross_section_standardize: bool = True
    min_history_days: int = 60        # 最少历史天数（特征计算需要）
    extra_features: list[str] = field(default_factory=list)

class DatasetBuilder:
    """从行情数据构建 ML 训练数据集。"""

    def __init__(
        self,
        market_gateway: IBacktestMarketGateway,
        fundamental_registry: FundamentalRegistry,
        config: DatasetConfig,
    ) -> None: ...

    def build(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """构建训练数据集。

        Returns:
            DataFrame, columns=[date, symbol, feature_1, ..., feature_n, label]
        """
        ...

    def save(self, df: pd.DataFrame, path: str) -> None:
        """保存为 parquet。"""
        ...

    @staticmethod
    def load(path: str) -> pd.DataFrame:
        """从 parquet 加载。"""
        ...
```

---

## 四、时间序列交叉验证

### 4.1 问题陈述

标准 K-Fold 在时间序列上会导致**未来信息泄露**：模型在 t=100 的数据上训练，却在 t=50 的数据上测试。必须使用时间序列感知的切分方式。

### 4.2 Purged Walk-Forward 方案

```
时间轴: ──────────────────────────────────────────────>
        |<--- Train --->|<- Gap ->|<-- Test -->|
Fold 1: [2020-01 ~ 2021-06] [gap] [2021-09 ~ 2022-03]
Fold 2: [2020-01 ~ 2022-03] [gap] [2022-06 ~ 2022-12]
Fold 3: [2020-01 ~ 2022-12] [gap] [2023-03 ~ 2023-09]
Fold 4: [2020-01 ~ 2023-09] [gap] [2023-12 ~ 2024-06]
Fold 5: [2020-01 ~ 2024-06] [gap] [2024-09 ~ 2025-03]
```

**关键参数**：
- **Gap 窗口**：`label_horizon` 天（默认 5 天），防止标签重叠泄露
- **训练集**：扩展窗口（Expanding Window），保留所有历史数据
- **测试集**：滚动窗口（Rolling Window），每折 3-6 个月
- **最少训练期**：2 年（约 500 个交易日）

### 4.3 实现接口

```python
# src/infrastructure/ml_engine/time_series_cv.py

@dataclass(slots=True, kw_only=True)
class TimeSeriesCVConfig:
    """时间序列交叉验证配置。"""
    n_splits: int = 5
    test_size_months: int = 6
    gap_days: int = 5           # = label_horizon，防止泄露
    min_train_days: int = 500   # 最少训练天数

class PurgedWalkForwardCV:
    """Purged Walk-Forward 交叉验证器。"""

    def __init__(self, config: TimeSeriesCVConfig) -> None: ...

    def split(
        self, df: pd.DataFrame
    ) -> list[tuple[pd.Index, pd.Index]]:
        """生成 (train_idx, test_idx) 对。

        Args:
            df: 包含 'date' 列的数据集。

        Returns:
            list of (train_index, test_index)。
        """
        ...
```

### 4.4 防泄露检查清单

| 泄露类型 | 检查方法 |
|----------|----------|
| 标签泄露 | 确认 label = close[t+N]/close[t]-1，特征只用 <= t 的数据 |
| 截面泄露 | 每日标准化只用当日截面数据，不用全量统计 |
| 时序泄露 | Gap >= label_horizon，训练集最大日期 < 测试集最小日期 - gap |
| 特征泄露 | 衍生特征不使用任何未来数据（如 forward PE） |

---

## 五、LightGBM 训练管道

### 5.1 训练流程

```
Dataset (parquet)
      │
      ▼
PurgedWalkForwardCV.split()
      │
      ├── Fold 1: train / test ──→ Optuna 优化 ──→ 最优参数 ──→ 训练 ──→ 评估
      ├── Fold 2: train / test ──→ Optuna 优化 ──→ 最优参数 ──→ 训练 ──→ 评估
      ├── ...
      └── Fold N: train / test ──→ Optuna 优化 ──→ 最优参数 ──→ 训练 ──→ 评估
      │
      ▼
汇总评估指标（IC 均值、IC IR、分层收益）
      │
      ▼
用全部数据 + 最优参数重新训练最终模型
      │
      ▼
保存模型 + 元信息 → models/{name}/
```

### 5.2 LightGBM 参数空间

```python
# Optuna 搜索空间
PARAM_SPACE = {
    "objective": "regression",
    "metric": "mse",
    "verbosity": -1,
    "boosting_type": "gbdt",
    # Optuna 优化的超参
    "n_estimators": IntDistribution(100, 2000),
    "learning_rate": FloatDistribution(0.01, 0.3, log=True),
    "max_depth": IntDistribution(3, 10),
    "num_leaves": IntDistribution(15, 255),
    "min_child_samples": IntDistribution(5, 100),
    "subsample": FloatDistribution(0.5, 1.0),
    "colsample_bytree": FloatDistribution(0.3, 1.0),
    "reg_alpha": FloatDistribution(1e-8, 10.0, log=True),
    "reg_lambda": FloatDistribution(1e-8, 10.0, log=True),
}
```

### 5.3 Trainer 接口

```python
# src/infrastructure/ml_engine/trainer.py

@dataclass(slots=True, kw_only=True)
class TrainConfig:
    """训练配置。"""
    model_name: str
    n_optuna_trials: int = 50
    n_cv_splits: int = 5
    early_stopping_rounds: int = 50
    random_seed: int = 42
    feature_columns: list[str] = field(default_factory=list)
    label_column: str = "label"
    lgbm_params: dict = field(default_factory=dict)  # 覆盖默认参数

@dataclass(slots=True, kw_only=True)
class TrainResult:
    """训练结果。"""
    model_name: str
    best_params: dict
    cv_metrics: list[dict]      # 每折评估指标
    mean_ic: float              # 平均 IC
    ic_ir: float                # IC 信息比率 (IC / std(IC))
    feature_importance: dict[str, float]
    model_path: str             # 模型文件路径
    train_samples: int
    feature_count: int

class LightGBMTrainer:
    """LightGBM 训练器，集成 Optuna 超参优化 + 时间序列 CV。"""

    def __init__(self, config: TrainConfig) -> None: ...

    def train(self, dataset: pd.DataFrame) -> TrainResult:
        """执行完整训练流程。

        Steps:
        1. PurgedWalkForwardCV 切分
        2. Optuna 搜索最优超参（每折独立搜索 or 共享搜索）
        3. 用最优参数训练最终模型
        4. 计算特征重要性
        5. 保存模型到 models/{model_name}/
        """
        ...
```

### 5.4 优化目标函数

Optuna 的优化目标是 **交叉验证平均 IC**（而非 MSE）：

```python
def objective(trial, train_df, cv_splitter, feature_cols, label_col):
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 2000),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        # ... 其他超参
    }
    ics = []
    for train_idx, test_idx in cv_splitter.split(train_df):
        model = lgb.LGBMRegressor(**params)
        model.fit(
            train_df.loc[train_idx, feature_cols],
            train_df.loc[train_idx, label_col],
            eval_set=[(train_df.loc[test_idx, feature_cols], train_df.loc[test_idx, label_col])],
            callbacks=[lgb.early_stopping(50)],
        )
        preds = model.predict(train_df.loc[test_idx, feature_cols])
        actuals = train_df.loc[test_idx, label_col]
        ic = spearmanr(preds, actuals).correlation
        ics.append(ic)
    return np.mean(ics)  # 最大化平均 IC
```

---

## 六、模型评估体系

### 6.1 统计评估指标

| 指标 | 公式 | 目标阈值 | 含义 |
|------|------|----------|------|
| IC (Information Coefficient) | Spearman(pred, actual) | > 0.05 | 预测值与真实收益的秩相关 |
| IC IR | mean(IC) / std(IC) | > 0.5 | IC 的稳定性 |
| IC > 0 比例 | count(IC > 0) / total | > 60% | 预测方向的一致性 |
| Top 组超额 | Top quintile return - benchmark | > 10% 年化 | 选股能力 |
| 多空收益 | Top quintile - Bottom quintile | > 15% 年化 | 区分度 |

### 6.2 分层回测评估

将预测分数按分位数分 5 组（quintile），分别计算每组的回测表现：

```
预测分数排序 → Q1(最低) ... Q5(最高)
     │
     ▼
每组独立回测 → 年化收益 / 夏普 / 最大回撤
     │
     ▼
验证：Q5 > Q4 > Q3 > Q2 > Q1（单调性）
```

### 6.3 Evaluator 接口

```python
# src/infrastructure/ml_engine/evaluator.py

@dataclass(slots=True, kw_only=True)
class PredictionMetrics:
    """预测评估指标。"""
    ic: float
    ic_ir: float
    ic_positive_ratio: float
    rank_autocorrelation: float

@dataclass(slots=True, kw_only=True)
class QuintileResult:
    """分层回测结果。"""
    quintile: int
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    turnover: float

@dataclass(slots=True, kw_only=True)
class EvalReport:
    """完整评估报告。"""
    model_name: str
    eval_period: str
    prediction_metrics: PredictionMetrics
    quintile_results: list[QuintileResult]
    long_short_return: float
    feature_importance: dict[str, float]

class ModelEvaluator:
    """模型评估器。"""

    def evaluate_predictions(
        self,
        predictions: pd.DataFrame,  # columns: [date, symbol, pred, actual]
    ) -> PredictionMetrics: ...

    def evaluate_quintiles(
        self,
        predictions: pd.DataFrame,
        price_data: dict[str, pd.Series],
        n_quintiles: int = 5,
    ) -> list[QuintileResult]: ...

    def full_evaluation(
        self,
        model_name: str,
        predictions: pd.DataFrame,
        price_data: dict[str, pd.Series],
    ) -> EvalReport: ...
```

---

## 七、ML 策略集成

### 7.1 MLReturnPredictionStrategy

继承 `CrossSectionalStrategy`，将 ML 预测分数转化为选股信号：

```python
# src/domain/strategy/services/strategies/ml_return_prediction_strategy.py

class MLReturnPredictionStrategy(CrossSectionalStrategy):
    """ML 收益预测选股策略。"""

    def __init__(
        self,
        model_name: str,
        top_n: int = 10,
        min_score: float = 0.0,      # 最低预测分数阈值
        model_dir: str = "models/",
    ) -> None:
        self._model_name = model_name
        self._top_n = top_n
        self._min_score = min_score
        # 推理引擎在 infrastructure 层，策略通过接口调用
        self._inference: InferenceEngine | None = None

    @property
    def name(self) -> str:
        return f"MLReturnPrediction_{self._model_name}"

    def set_inference_engine(self, engine: InferenceEngine) -> None:
        """注入推理引擎（依赖注入，Domain 层不直接依赖 infrastructure）。"""
        self._inference = engine

    def generate_cross_sectional_signals(
        self,
        universe: list[StockSnapshot],
        current_positions: list[Position],
        current_date: datetime,
    ) -> list[Signal]:
        """ML 预测 → 排序 → Top N 买入 + 跌出持仓卖出。"""
        if not self._inference or not universe:
            return []

        # 1. 从 StockSnapshot 提取特征矩阵
        features, symbols = self._extract_features(universe)

        # 2. ML 推理
        scores = self._inference.predict_batch(self._model_name, features)

        # 3. 排序选取 Top N
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_symbols = [s for s, _ in ranked[:self._top_n] if _ >= self._min_score]
        top_set = set(top_symbols)

        # 4. 生成信号
        signals = []
        for i, (symbol, score) in enumerate(ranked[:self._top_n]):
            if score < self._min_score:
                continue
            signals.append(Signal(
                symbol=symbol,
                direction=SignalDirection.BUY,
                confidence_score=min(score, 1.0),
                strategy_name=self.name,
                reason=f"ML prediction rank #{i+1}, score={score:.4f}",
            ))

        for pos in current_positions:
            if pos.ticker not in top_set:
                signals.append(Signal(
                    symbol=pos.ticker,
                    direction=SignalDirection.SELL,
                    confidence_score=0.0,
                    strategy_name=self.name,
                    reason="Dropped from ML top_n",
                ))

        return signals
```

### 7.2 策略注册

在 `src/domain/strategy/registry.py` 中注册：

```python
def _build_ml_return_prediction(params: dict[str, Any]) -> BaseStrategy:
    from src.domain.strategy.services.strategies.ml_return_prediction_strategy import (
        MLReturnPredictionStrategy,
    )
    from src.infrastructure.ml_engine.inference import InferenceEngine
    from src.infrastructure.ml_engine.model_loader import ModelLoader

    model_name = params.get("model_name", "lgbm_return_5d")
    top_n = params.get("top_n", 10)
    model_dir = params.get("model_dir", "models/")

    strategy = MLReturnPredictionStrategy(
        model_name=model_name,
        top_n=top_n,
        model_dir=model_dir,
    )
    # 注入推理引擎
    loader = ModelLoader(model_dir=model_dir)
    loader.register_lightgbm()  # 扩展 ModelLoader 支持 LGBM
    engine = InferenceEngine(loader)
    strategy.set_inference_engine(engine)
    return strategy

_register(StrategyConfig(
    name="ml_return_prediction",
    factory=_build_ml_return_prediction,
    strategy_type="cross_section",
    description="ML 收益预测选股策略 (LightGBM)",
    default_params={
        "model_name": "lgbm_return_5d",
        "top_n": 10,
        "model_dir": "models/",
    },
))
```

### 7.3 与回测框架集成

ML 策略作为 `CrossSectionalStrategy` 的子类，**无需修改** `BacktestAppService` 或 `CrossSectionalStrategyRunner`：

```
BacktestAppService.run_backtest()
    │
    ├── _build_runner(strategy)
    │     └── isinstance(strategy, CrossSectionalStrategy) → CrossSectionalStrategyRunner
    │
    ├── runner.evaluate(context)
    │     ├── FeaturePipeline.build_cross_section() → universe
    │     ├── strategy.generate_cross_sectional_signals(universe, positions, date)
    │     │     └── InferenceEngine.predict_batch() → scores → signals
    │     └── sizer.calculate_targets() → OrderTarget[]
    │
    └── _execute_targets() → place_order()
```

---

## 八、模型版本管理与部署

### 8.1 模型目录结构

```
models/
├── lgbm_return_5d_v1/
│   ├── model.joblib          # LightGBM Booster
│   ├── metadata.json         # 训练元信息
│   ├── feature_importance.csv
│   └── config.json           # 训练配置（可复现）
├── lgbm_return_5d_v2/
│   └── ...
└── registry.json             # 模型注册表
```

### 8.2 元信息格式

```json
{
  "model_name": "lgbm_return_5d_v1",
  "model_type": "lightgbm",
  "created_at": "2026-05-31T10:00:00",
  "train_period": "2020-01-01 ~ 2024-12-31",
  "eval_period": "2025-01-01 ~ 2025-06-30",
  "label_horizon": 5,
  "feature_count": 47,
  "train_samples": 500000,
  "best_params": {
    "n_estimators": 800,
    "learning_rate": 0.05,
    "max_depth": 7,
    "num_leaves": 63
  },
  "cv_metrics": {
    "mean_ic": 0.068,
    "ic_ir": 0.72,
    "ic_positive_ratio": 0.65
  },
  "features": ["return_5d", "volatility_20d", "..."],
  "training_config": {
    "n_optuna_trials": 50,
    "n_cv_splits": 5,
    "random_seed": 42
  }
}
```

### 8.3 ModelRegistry 接口

```python
# src/infrastructure/ml_engine/model_registry.py

@dataclass(slots=True, kw_only=True)
class ModelMetadata:
    """模型元信息。"""
    model_name: str
    model_type: str
    created_at: str
    train_period: str
    eval_period: str
    label_horizon: int
    feature_count: int
    train_samples: int
    best_params: dict
    cv_metrics: dict
    features: list[str]
    model_path: str

class ModelRegistry:
    """模型版本管理。"""

    def __init__(self, models_dir: str = "models/") -> None: ...

    def register(self, metadata: ModelMetadata) -> None:
        """注册新模型版本。"""
        ...

    def get_latest(self, model_name: str) -> ModelMetadata:
        """获取最新版本。"""
        ...

    def list_models(self) -> list[ModelMetadata]:
        """列出所有已注册模型。"""
        ...

    def get_model_path(self, model_name: str, version: str = "latest") -> str:
        """获取模型文件路径。"""
        ...
```

### 8.4 部署流程

```
训练完成
    │
    ├── 1. 保存模型文件 → models/{name}/model.joblib
    ├── 2. 保存元信息 → models/{name}/metadata.json
    ├── 3. 保存特征重要性 → models/{name}/feature_importance.csv
    │
    ▼
评估验证
    │
    ├── 4. 样本外 IC > 0.05 ?  ── No ──→ 不部署，记录原因
    ├── 5. 分层单调性通过 ?    ── No ──→ 不部署
    │
    ▼
注册上线
    │
    ├── 6. ModelRegistry.register()
    ├── 7. 更新 registry.json 中的 active_model
    │
    ▼
策略使用
    │
    └── 8. MLReturnPredictionStrategy 通过 ModelLoader 加载最新模型
```

---

## 九、CLI 命令设计

### 9.1 训练命令

```bash
# 基础训练
python -m src.interfaces.cli.ml_train \
    --symbols "000300.SH" \
    --start-date 2020-01-01 \
    --end-date 2024-12-31 \
    --label-horizon 5 \
    --model-name lgbm_return_5d \
    --n-trials 50

# 高级配置
python -m src.interfaces.cli.ml_train \
    --config resources/ml_train.yaml
```

### 9.2 评估命令

```bash
# 模型评估
python -m src.interfaces.cli.ml_evaluate \
    --model-name lgbm_return_5d \
    --eval-start 2025-01-01 \
    --eval-end 2025-06-30 \
    --quintiles 5 \
    --plot
```

### 9.3 回测命令

```bash
# ML 策略回测（复用现有回测框架）
python -m src.interfaces.cli.run_backtest \
    --strategy ml_return_prediction \
    --strategy-params '{"model_name": "lgbm_return_5d_v1", "top_n": 10}' \
    --start-date 2025-01-01 \
    --end-date 2025-12-31
```

---

## 十、可解释性

### 10.1 特征重要性

LightGBM 内置两种重要性指标：
- **split**：特征被用于分裂的次数
- **gain**：特征带来的总增益

训练完成后自动输出 `feature_importance.csv`。

### 10.2 SHAP 分析（可选，Phase 1 后期）

```python
import shap

explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# 全局重要性
shap.summary_plot(shap_values, X_test)

# 单股票解释
shap.force_plot(explainer.expected_value, shap_values[0], X_test.iloc[0])
```

---

## 十一、依赖管理

### 11.1 新增依赖

在 `pyproject.toml` 中添加 `[project.optional-dependencies]`：

```toml
[project.optional-dependencies]
ml = [
    "lightgbm>=4.0",
    "scikit-learn>=1.3",
    "optuna>=3.5",
    "joblib>=1.3",
]
ml_explain = [
    "shap>=0.43",
]
```

### 11.2 依赖关系图

```
训练时（一次性）:
    lightgbm + scikit-learn + optuna + pandas + numpy

推理时（每次选股）:
    lightgbm + numpy（模型已加载到内存）

可选:
    shap（模型解释，非推理必需）
```

---

## 十二、文件结构规划

```
src/infrastructure/ml_engine/
├── __init__.py
├── feature_pipeline.py        # [现有] Bar → 特征
├── inference.py               # [现有] 推理引擎，需扩展支持 LGBM
├── model_loader.py            # [现有] 模型加载，需扩展支持 LGBM
├── dataset_builder.py         # [新增] 训练数据集构建
├── label_generator.py         # [新增] 标签生成
├── time_series_cv.py          # [新增] 时间序列交叉验证
├── trainer.py                 # [新增] LightGBM 训练器 + Optuna
├── evaluator.py               # [新增] 模型评估（IC / 分层）
├── model_registry.py          # [新增] 模型版本管理
└── feature_transforms.py      # [新增] 衍生特征 + 截面标准化

src/domain/strategy/services/strategies/
├── ml_return_prediction_strategy.py  # [新增] ML 收益预测策略

src/interfaces/cli/
├── ml_train.py                # [新增] 训练 CLI
├── ml_evaluate.py             # [新增] 评估 CLI

tests/infrastructure/ml_engine/
├── test_dataset_builder.py
├── test_label_generator.py
├── test_time_series_cv.py
├── test_trainer.py
├── test_evaluator.py
└── test_model_registry.py

tests/domain/strategy/
├── test_ml_return_prediction_strategy.py

resources/
└── ml_train.yaml              # [新增] 训练默认配置
```

---

## 十三、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 过拟合 | 样本外表现差 | Purged CV + 正则化 + 早停 |
| 标签噪声 | 模型学不到有效信号 | 多期标签平滑 + Winsorize |
| 特征泄露 | 回测虚高 | 严格时序切分 + 自动泄露检查 |
| 模型退化 | 实盘表现低于回测 | 定期重训 + IC 监控 + 策略熔断 |
| A 股特殊性 | 涨跌停、停牌 | 复用现有 StockStatusRegistry 过滤 |
| 计算资源 | 训练耗时 | Optuna n_trials 可调 + 并行 CV |

---

## 十四、里程碑

| 里程碑 | 交付物 | 验收标准 |
|--------|--------|----------|
| M1: 数据管道 | DatasetBuilder + LabelGenerator | 能从回测数据构建 parquet 训练集 |
| M2: CV 框架 | PurgedWalkForwardCV | 正确切分，无泄露 |
| M3: 训练器 | LightGBMTrainer + Optuna | 自动训练 + 超参优化 |
| M4: 评估器 | ModelEvaluator + 分层回测 | 输出 IC / 分层报告 |
| M5: 策略集成 | MLReturnPredictionStrategy + 注册 | 回测可运行 |
| M6: CLI + 端到端 | ml_train / ml_evaluate | 一键训练 → 评估 → 注册 |
