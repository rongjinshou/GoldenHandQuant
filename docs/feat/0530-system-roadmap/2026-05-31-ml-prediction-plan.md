# ML 端到端收益预测 — 实现计划

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 实现计划
**状态**: 草案
**设计文档**: `2026-05-31-ml-prediction-design.md`

---

## 一、总体节奏

**总工期**：6 个迭代（约 3-4 周）
**依赖关系**：T1 → T2 → T3 → T4 → T5 → T6（串行为主，T3 内部可并行）

```
T1: 依赖 + 数据管道   T2: CV 框架   T3: 训练器   T4: 评估器   T5: 策略集成   T6: CLI + 端到端
   [Day 1-3]          [Day 4-5]    [Day 6-9]    [Day 10-11]  [Day 12-13]    [Day 14-16]
```

---

## 二、任务分解

### T1: 依赖配置 + 数据集构建管道

**目标**：能从行情数据构建 ML 训练数据集（parquet 格式）。
**工期**：3 天
**验收**：运行 DatasetBuilder 输出含 date/symbol/features/label 列的 DataFrame。

#### T1.1: 依赖配置（0.5 天）

**文件**：`pyproject.toml`

- 添加 `[project.optional-dependencies] ml = ["lightgbm>=4.0", "scikit-learn>=1.3", "optuna>=3.5", "joblib>=1.3"]`
- 运行 `pip install -e ".[ml,dev]"` 验证安装

**验证**：`python -c "import lightgbm; import optuna; print('OK')"`

#### T1.2: 衍生特征计算器（1 天）

**文件**：`src/infrastructure/ml_engine/feature_transforms.py`

实现内容：
- `compute_derived_features(snapshots: list[StockSnapshot]) -> list[dict]`
- 衍生特征：close_to_ma5, close_to_ma20, close_to_ma60, ma5_to_ma20, ma20_to_ma60, high_low_range, close_position, macd_hist, log_market_cap, bp_ratio
- 截面 Z-Score 标准化函数 `cross_section_standardize(df, feature_cols, date_col)`

**测试**：`tests/infrastructure/ml_engine/test_feature_transforms.py`
- 给定手工构建的 StockSnapshot，验证衍生特征计算正确
- 验证标准化后均值 ~0，标准差 ~1

**依赖**：T1.1

#### T1.3: 标签生成器（0.5 天）

**文件**：`src/infrastructure/ml_engine/label_generator.py`

实现内容：
- `@dataclass LabelConfig(horizon=5, label_type="fwd_return", winsorize_quantile=0.01)`
- `generate_labels(df: pd.DataFrame, price_series: dict[str, pd.Series], config: LabelConfig) -> pd.Series`
- 计算 `close[t+N] / close[t] - 1`
- Winsorize 到 [1%, 99%] 分位
- 返回带 NaN 的 Series（停牌/数据不足的行保留 NaN）

**测试**：`tests/infrastructure/ml_engine/test_label_generator.py`
- 手工构造 10 天价格序列，验证 5 日前瞻收益计算
- 验证 Winsorize 截断极端值

**依赖**：无

#### T1.4: DatasetBuilder（1 天）

**文件**：`src/infrastructure/ml_engine/dataset_builder.py`

实现内容：
- `@dataclass DatasetConfig(label_horizon=5, label_type="fwd_return", winsorize_quantile=0.01, cross_section_standardize=True, min_history_days=60)`
- `DatasetBuilder.__init__(market_gateway, fundamental_registry, config)`
- `DatasetBuilder.build(symbols, start_date, end_date) -> pd.DataFrame`
  - 遍历日期，调用 `FeaturePipeline.build_cross_section()` 获取 StockSnapshot
  - 提取基础特征 + 调用 `compute_derived_features()`
  - 调用 `generate_labels()` 生成标签
  - 截面标准化
  - 丢弃 label 为 NaN 的行
- `DatasetBuilder.save(df, path)` / `DatasetBuilder.load(path)` — parquet 格式

**测试**：`tests/infrastructure/ml_engine/test_dataset_builder.py`
- 使用 MockMarketGateway + MockFundamentalRegistry 构建小型数据集
- 验证输出 DataFrame 列名、行数、无 NaN label

**依赖**：T1.2, T1.3

---

### T2: 时间序列交叉验证

**目标**：实现 Purged Walk-Forward CV，确保无未来信息泄露。
**工期**：2 天
**验收**：给定 DataFrame，正确输出 N 折 (train_idx, test_idx)，每折满足时序约束。

#### T2.1: PurgedWalkForwardCV 实现（1.5 天）

**文件**：`src/infrastructure/ml_engine/time_series_cv.py`

实现内容：
- `@dataclass TimeSeriesCVConfig(n_splits=5, test_size_months=6, gap_days=5, min_train_days=500)`
- `PurgedWalkForwardCV.__init__(config)`
- `PurgedWalkForwardCV.split(df) -> list[tuple[pd.Index, pd.Index]]`
  - 从 df['date'] 提取唯一日期序列
  - 按时间顺序切分测试窗口（滚动 6 个月）
  - 训练窗口为扩展式（包含所有历史）
  - Gap = gap_days 天（训练集末尾到测试集开头的间隔）
  - 丢弃不满足 min_train_days 的折

**测试**：`tests/infrastructure/ml_engine/test_time_series_cv.py`
- 构造 3 年日频数据，5 折 CV
- 验证每折：train_max_date < test_min_date - gap_days
- 验证训练集扩展（fold_i 的 train >= fold_{i-1} 的 train）
- 验证边界：数据不足 min_train_days 时折数减少

**依赖**：无

#### T2.2: 泄露检测工具（0.5 天）

**文件**：`src/infrastructure/ml_engine/time_series_cv.py`（追加）

实现内容：
- `validate_no_leakage(df, train_idx, test_idx, label_col, gap_days) -> bool`
  - 检查 train 最大日期 + gap <= test 最小日期
  - 检查 label 列在 train 中不包含 test 时间范围的值

**测试**：追加到 `test_time_series_cv.py`
- 构造有泄露的数据，验证检测到
- 构造无泄露的数据，验证通过

**依赖**：T2.1

---

### T3: LightGBM 训练器 + Optuna 超参优化

**目标**：自动训练 LightGBM 模型，Optuna 搜索最优超参。
**工期**：4 天
**验收**：给定 parquet 数据集，输出 TrainResult（模型文件 + 指标 + 特征重要性）。

#### T3.1: LightGBMTrainer 核心（2 天）

**文件**：`src/infrastructure/ml_engine/trainer.py`

实现内容：
- `@dataclass TrainConfig(model_name, n_optuna_trials=50, n_cv_splits=5, early_stopping_rounds=50, random_seed=42, feature_columns, label_column="label", lgbm_params={})`
- `@dataclass TrainResult(model_name, best_params, cv_metrics, mean_ic, ic_ir, feature_importance, model_path, train_samples, feature_count)`
- `LightGBMTrainer.__init__(config)`
- `LightGBMTrainer.train(dataset: pd.DataFrame) -> TrainResult`
  - 自动检测 feature_columns（排除 date, symbol, label）
  - 调用 PurgedWalkForwardCV.split()
  - 对每折：用最优参数训练，记录 IC
  - 汇总 mean_ic, ic_ir
  - 用全部数据 + 最优参数重新训练最终模型
  - 计算 feature_importance（gain 型）
  - 保存模型到 `models/{model_name}/model.joblib`
  - 保存 metadata.json

**关键实现细节**：
- 特征列自动检测：排除 `date`, `symbol`, `label`, `actual_return` 等非特征列
- Optuna 目标函数：最大化 CV 平均 IC（Spearman 相关系数）
- 早停：LightGBM 的 `lgb.early_stopping()` callback
- 模型保存：`joblib.dump(booster, path)`

**测试**：`tests/infrastructure/ml_engine/test_trainer.py`
- 构造小型合成数据集（1000 行，10 特征）
- 验证 TrainResult 字段完整
- 验证模型文件存在
- 验证 mean_ic 在合理范围（合成数据可能不高，但不应为 NaN）

**依赖**：T1.4, T2.1

#### T3.2: Optuna 超参搜索（1 天）

**文件**：`src/infrastructure/ml_engine/trainer.py`（追加）

实现内容：
- `_create_optuna_study(config) -> optuna.Study`
- `_objective(trial, df, cv_splitter, feature_cols, label_col) -> float`
  - 从 trial 中采样超参
  - 遍历每折 CV 训练 + 预测
  - 计算每折 IC
  - 返回平均 IC
- 超参空间：n_estimators, learning_rate, max_depth, num_leaves, min_child_samples, subsample, colsample_bytree, reg_alpha, reg_lambda

**测试**：追加到 `test_trainer.py`
- 小 n_trials=3，验证搜索完成不报错
- 验证 best_params 非空

**依赖**：T3.1

#### T3.3: 模型元信息 + 版本管理（1 天）

**文件**：`src/infrastructure/ml_engine/model_registry.py`

实现内容：
- `@dataclass ModelMetadata(model_name, model_type, created_at, train_period, eval_period, label_horizon, feature_count, train_samples, best_params, cv_metrics, features, model_path)`
- `ModelRegistry.__init__(models_dir="models/")`
- `ModelRegistry.register(metadata)` — 保存 metadata.json + 更新 registry.json
- `ModelRegistry.get_latest(model_name) -> ModelMetadata`
- `ModelRegistry.list_models() -> list[ModelMetadata]`
- `ModelRegistry.get_model_path(model_name, version="latest") -> str`

**测试**：`tests/infrastructure/ml_engine/test_model_registry.py`
- 注册一个模型，验证 registry.json 更新
- get_latest 返回正确元信息
- list_models 返回注册列表

**依赖**：无（可与 T3.1 并行）

---

### T4: 模型评估器

**目标**：评估模型预测质量（IC）和分层回测表现。
**工期**：2 天
**验收**：输入预测值 + 真实值，输出 EvalReport。

#### T4.1: 统计评估（IC 等）（1 天）

**文件**：`src/infrastructure/ml_engine/evaluator.py`

实现内容：
- `@dataclass PredictionMetrics(ic, ic_ir, ic_positive_ratio, rank_autocorrelation)`
- `ModelEvaluator.evaluate_predictions(predictions: pd.DataFrame) -> PredictionMetrics`
  - predictions 列: [date, symbol, pred, actual]
  - 按日期分组计算截面 IC（Spearman）
  - 汇总 mean_ic, ic_ir = mean/std, ic_positive_ratio

**测试**：`tests/infrastructure/ml_engine/test_evaluator.py`
- 构造已知相关性的数据，验证 IC 计算正确
- 验证 ic_ir 和 ic_positive_ratio 计算

**依赖**：无

#### T4.2: 分层回测评估（1 天）

**文件**：`src/infrastructure/ml_engine/evaluator.py`（追加）

实现内容：
- `@dataclass QuintileResult(quintile, annualized_return, sharpe_ratio, max_drawdown, turnover)`
- `@dataclass EvalReport(model_name, eval_period, prediction_metrics, quintile_results, long_short_return, feature_importance)`
- `ModelEvaluator.evaluate_quintiles(predictions, price_data, n_quintiles=5) -> list[QuintileResult]`
  - 每日按预测分数分 5 组
  - 计算每组等权组合收益
  - 汇总年化收益 / 夏普 / 最大回撤
- `ModelEvaluator.full_evaluation(model_name, predictions, price_data) -> EvalReport`

**测试**：追加到 `test_evaluator.py`
- 构造简单数据验证分层逻辑
- 验证 quintile_results 长度 = n_quintiles

**依赖**：T4.1

---

### T5: ML 策略集成

**目标**：创建 MLReturnPredictionStrategy 并注册到策略注册表。
**工期**：2 天
**验收**：策略可在回测框架中运行，生成 BUY/SELL 信号。

#### T5.1: MLReturnPredictionStrategy（1 天）

**文件**：`src/domain/strategy/services/strategies/ml_return_prediction_strategy.py`

实现内容：
- 继承 `CrossSectionalStrategy`
- `__init__(model_name, top_n=10, min_score=0.0, model_dir="models/")`
- `set_inference_engine(engine)` — 依赖注入
- `generate_cross_sectional_signals(universe, current_positions, current_date) -> list[Signal]`
  - 从 StockSnapshot 提取特征（调用 feature_transforms）
  - 调用 InferenceEngine.predict_batch()
  - 按预测分数排序，取 Top N 生成 BUY 信号
  - 持仓不在 Top N 中的生成 SELL 信号
- `_extract_features(universe) -> tuple[dict[str, np.ndarray], list[str]]`

**测试**：`tests/domain/strategy/test_ml_return_prediction_strategy.py`
- Mock InferenceEngine，验证信号生成逻辑
- 验证 Top N 买入 + 跌出卖出
- 验证 confidence_score 与预测分数对应

**依赖**：无（可与 T3/T4 并行）

#### T5.2: 扩展 ModelLoader + InferenceEngine（0.5 天）

**文件**：
- `src/infrastructure/ml_engine/model_loader.py` — 添加 `load_lightgbm()` 方法
- `src/infrastructure/ml_engine/inference.py` — 添加 LightGBM 推理路径

实现内容：
- `ModelLoader.load_lightgbm(model_name) -> lgb.Booster`
  - 使用 joblib 加载 .joblib 文件
  - 惰性缓存（复用现有 _cache 模式）
- `InferenceEngine.predict()` 扩展：根据模型类型选择 CatBoost 或 LightGBM

**测试**：追加到现有测试或新建
- 验证 LightGBM 模型加载 + 预测

**依赖**：无

#### T5.3: 策略注册（0.5 天）

**文件**：`src/domain/strategy/registry.py`

实现内容：
- 添加 `_build_ml_return_prediction(params)` 工厂函数
- 注册 `StrategyConfig(name="ml_return_prediction", ...)`
- default_params: `{"model_name": "lgbm_return_5d", "top_n": 10, "model_dir": "models/"}`

**测试**：验证 `create_strategy("ml_return_prediction")` 不报错

**依赖**：T5.1, T5.2

---

### T6: CLI + 端到端验证

**目标**：一键训练 → 评估 → 回测的完整流程。
**工期**：2 天
**验收**：运行 `ml_train` 命令完成训练 + 评估，输出报告。

#### T6.1: ml_train CLI（1 天）

**文件**：`src/interfaces/cli/ml_train.py`

实现内容：
- argparse 命令行参数：
  - `--symbols`：股票列表或指数成分
  - `--start-date` / `--end-date`
  - `--label-horizon`（默认 5）
  - `--model-name`（默认 "lgbm_return_5d"）
  - `--n-trials`（默认 50）
  - `--config`（可选，YAML 配置文件）
- 流程：
  1. 加载数据 → DatasetBuilder.build() → save parquet
  2. LightGBMTrainer.train() → TrainResult
  3. ModelEvaluator.full_evaluation() → EvalReport
  4. ModelRegistry.register()
  5. 打印报告摘要

**验证**：手动运行命令，检查输出模型文件和报告

**依赖**：T1-T5 全部

#### T6.2: ml_evaluate CLI（0.5 天）

**文件**：`src/interfaces/cli/ml_evaluate.py`

实现内容：
- argparse 参数：`--model-name`, `--eval-start`, `--eval-end`, `--quintiles`, `--plot`
- 流程：
  1. ModelRegistry.get_latest() 获取模型
  2. DatasetBuilder.build() 构建评估数据集
  3. InferenceEngine.predict_batch() 生成预测
  4. ModelEvaluator.full_evaluation() 输出报告

**验证**：运行命令检查报告输出

**依赖**：T6.1

#### T6.3: 端到端回测验证（0.5 天）

**目标**：ML 策略在现有回测框架中完整运行。

流程：
```bash
# 1. 训练模型
python -m src.interfaces.cli.ml_train --symbols "000300.SH" --start-date 2020-01-01 --end-date 2024-12-31

# 2. 回测验证
python -m src.interfaces.cli.run_backtest \
    --strategy ml_return_prediction \
    --strategy-params '{"model_name": "lgbm_return_5d", "top_n": 10}' \
    --start-date 2025-01-01 --end-date 2025-06-30

# 3. 检查回测报告
# - 年化收益率
# - 夏普比率
# - 最大回撤
```

**验证**：回测正常完成，报告包含有效数据（非全零）

**依赖**：T6.1, T5.3

---

## 三、测试策略

### 3.1 单元测试

| 测试文件 | 覆盖目标 | 测试数量（预估） |
|----------|----------|-----------------|
| `test_feature_transforms.py` | 衍生特征计算 + 标准化 | 6 |
| `test_label_generator.py` | 标签生成 + Winsorize | 4 |
| `test_time_series_cv.py` | CV 切分 + 泄露检测 | 6 |
| `test_dataset_builder.py` | 数据集构建全流程 | 4 |
| `test_trainer.py` | 训练 + Optuna | 4 |
| `test_evaluator.py` | IC 计算 + 分层 | 5 |
| `test_model_registry.py` | 注册/查询 | 4 |
| `test_ml_return_prediction_strategy.py` | 信号生成 | 5 |

**总计**：约 38 个测试用例

### 3.2 集成测试

- `test_ml_e2e_pipeline.py`：从合成数据 → 训练 → 评估 → 策略信号的完整流程
- 使用 Mock 数据，不依赖真实行情

### 3.3 测试运行

```bash
# 全部 ML 测试
python -m pytest tests/infrastructure/ml_engine/ -v

# 策略测试
python -m pytest tests/domain/strategy/test_ml_return_prediction_strategy.py -v

# 集成测试
python -m pytest tests/integration/test_ml_pipeline.py -v
```

---

## 四、风险与应急预案

| 风险 | 应急措施 |
|------|----------|
| Optuna 训练耗时过长 | n_trials 降至 20，或用 RandomSearch 替代 |
| IC 过低（< 0.02） | 增加特征维度，或调整 label_horizon |
| LightGBM 安装失败 | 降级到 XGBoost（已有 model_loader 支持） |
| 数据量不足 | 缩短 min_train_days，或扩展回测标的范围 |

---

## 五、交付检查清单

- [ ] `pip install -e ".[ml,dev]"` 安装成功
- [ ] `DatasetBuilder.build()` 输出有效 parquet
- [ ] `PurgedWalkForwardCV.split()` 时序无泄露
- [ ] `LightGBMTrainer.train()` 输出模型文件 + metadata.json
- [ ] `ModelEvaluator` 输出 IC / 分层报告
- [ ] `MLReturnPredictionStrategy` 在回测中生成有效信号
- [ ] `ml_train` CLI 端到端运行成功
- [ ] 所有单元测试通过（`pytest tests/infrastructure/ml_engine/`）
- [ ] 策略注册后 `create_strategy("ml_return_prediction")` 可用
- [ ] 设计文档中所有文件路径与实际一致
