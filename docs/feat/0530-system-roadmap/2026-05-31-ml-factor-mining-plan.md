# ML 因子挖掘引擎 — 实现计划

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 实现计划
**状态**: 草案
**关联文档**: `2026-05-31-ml-factor-mining-design.md`

---

## 一、总体排期

**总工期**: 8 周（Phase 1 中的 ML 部分）
**每周投入**: 15-20 小时
**代码量预估**: ~1,200 行业务代码 + ~600 行测试代码

| 周次 | 任务 | 交付物 | 验证标准 |
|------|------|--------|---------|
| W1-W2 | 基础设施 + 特征工程 | AutoFeatureCombiner + 单元测试 | 生成 100+ 组合特征，耗时 < 5s |
| W3-W4 | 因子评估系统 | FactorEvaluator + 单元测试 | IC/IR 计算正确，分层回测可用 |
| W5-W6 | 训练管道 | TrainingPipeline + LightGBM 训练 | Walk-Forward 训练可用，样本外 IC > 0.03 |
| W7 | 因子存储 + 适配器 | FactorRepository + MinedFactor + 注册集成 | 因子入库 → MultiFactorStrategy 自动加载 |
| W8 | 端到端集成 + CLI | FactorMiner 编排 + CLI 命令 | 一键挖掘 → 入库全流程可用 |

---

## 二、详细任务分解

### W1: 基础设施 + 依赖配置

#### Task 1.1: 新增 ML 依赖
- **文件**: `pyproject.toml`
- **操作**: 在 `[project.optional-dependencies]` 中新增 `ml` 组
- **内容**:
  ```toml
  ml = [
      "lightgbm>=4.0",
      "optuna>=3.0",
      "scipy>=1.10",
  ]
  ```
- **验证**: `pip install -e ".[ml]"` 成功

#### Task 1.2: 数据准备工具
- **文件**: `src/infrastructure/ml_engine/data_loader.py`（新建）
- **职责**: 将分散的历史数据（Bar + FundamentalSnapshot）整合为 `dict[date, list[StockSnapshot]]` 格式
- **接口**:
  ```python
  class MLDataLoader:
      """ML 训练数据加载器。"""

      def load_snapshots_by_date(
          self,
          symbols: list[str],
          start_date: str,
          end_date: str,
      ) -> dict[date, list[StockSnapshot]]:
          """加载指定时间范围的全市场日频快照。"""
          ...

      def compute_forward_returns(
          self,
          snapshots_by_date: dict[date, list[StockSnapshot]],
          forward_days: int = 20,
      ) -> pd.DataFrame:
          """计算前瞻收益率标签。

          Returns:
              DataFrame, index=date, columns=symbol, values=forward_return。
          """
          ...
  ```
- **测试**: `tests/infrastructure/ml_engine/test_data_loader.py`
  - 测试快照加载完整性
  - 测试前瞻收益率计算无未来泄露（shift(-N)）
  - 测试缺失数据处理
- **验证**: 加载 3 年数据，确认快照日期连续、收益率标签正确

#### Task 1.3: 基础特征扩展
- **文件**: `src/infrastructure/ml_engine/feature_pipeline.py`（修改）
- **操作**: 在 `_compute_bar_metrics` 中新增以下基础特征
- **新增特征**:
  ```python
  # 布林带
  kw["boll_upper"] = ma_20 + 2 * std_20
  kw["boll_lower"] = ma_20 - 2 * std_20
  kw["boll_width"] = (boll_upper - boll_lower) / ma_20

  # KDJ
  kw["kdj_k"] = ...  # 9 日随机指标
  kw["kdj_d"] = ...
  kw["kdj_j"] = ...

  # 成交量变化率
  kw["volume_change_5d"] = (volumes[-1] - volumes[-6]) / volumes[-6]
  kw["volume_change_20d"] = ...

  # 价格位置
  kw["close_to_high_20d"] = (closes[-1] - highs_max_20) / highs_max_20
  kw["close_to_low_20d"] = (closes[-1] - lows_min_20) / lows_min_20
  ```
- **同步更新**: `src/domain/market/value_objects/stock_snapshot.py` 新增对应字段
- **测试**: 验证新特征计算正确性（手动计算对比）
- **验证**: 基础特征池达到 60+ 个

---

### W2: AutoFeatureCombiner — 自动特征组合

#### Task 2.1: 组合算子实现
- **文件**: `src/infrastructure/ml_engine/feature_combiner.py`（新建）
- **核心类**:
  ```python
  class FeatureOperator(Enum):
      """特征组合算子。"""
      ADD = "add"        # A + B
      SUB = "sub"        # A - B
      MUL = "mul"        # A * B
      DIV = "div"        # A / B
      RANK = "rank"      # rank(A)
      ZSCORE = "zscore"  # (A - mean) / std

  @dataclass(slots=True, kw_only=True)
  class CombinationRule:
      """组合规则定义。"""
      name: str              # 组合特征名
      operator: FeatureOperator
      feature_a: str         # 基础特征名 A
      feature_b: str | None  # 基础特征名 B（单目算子时为 None）
      category: str          # "same_domain" | "cross_domain" | "transform"

  class AutoFeatureCombiner:
      """自动特征组合器。"""

      # 预定义的组合规则集
      SAME_DOMAIN_RULES: list[CombinationRule]  # 同域组合
      CROSS_DOMAIN_RULES: list[CombinationRule] # 跨域组合
      TRANSFORM_RULES: list[CombinationRule]    # 变换（排名、标准化）

      def generate_combinations(
          self,
          snapshots: list[StockSnapshot],
          strategy: str = "standard",
      ) -> pd.DataFrame:
          """生成组合特征矩阵。"""
          ...

      def _apply_operator(
          self,
          values_a: np.ndarray,
          values_b: np.ndarray | None,
          operator: FeatureOperator,
      ) -> np.ndarray:
          """应用组合算子。"""
          ...

      def _generate_rules(
          self,
          feature_names: list[str],
          strategy: str,
      ) -> list[CombinationRule]:
          """根据策略生成组合规则。"""
          ...
  ```
- **组合规则集设计**:
  - **同域组合** (50 条): 基本面/基本面、技术/技术
    - `return_5d / pe_ratio`（动量/估值）
    - `roe_ttm * earnings_growth`（质量 x 成长）
    - `rank(pe_ratio) + rank(pb_ratio)`（估值排名合成）
    - `volatility_20d / turnover_rate`（波动/流动性）
  - **跨域组合** (30 条): 基本面 x 技术
    - `rsi_14 * (1 / pe_ratio)`（超卖 x 低估值）
    - `return_60d / debt_to_equity`（动量/杠杆）
    - `rank(market_cap) + rank(volatility_20d)`（市值 x 波动排名）
  - **变换** (20 条): 排名、标准化
    - `rank(roe_ttm)`, `zscore(volatility_20d)` 等
- **测试**: `tests/infrastructure/ml_engine/test_feature_combiner.py`
  - 测试每种算子的正确性（除零、NaN 处理）
  - 测试组合规则生成数量
  - 测试 `strategy="conservative"` 时规则数 < `standard` < `aggressive`
  - 测试全市场 5000 股场景耗时 < 5s
- **验证**: 生成 100+ 组合特征，无 NaN 列，列名无重复

#### Task 2.2: 基础特征池注册
- **文件**: `src/infrastructure/ml_engine/feature_combiner.py`（补充）
- **操作**: 定义 `BASE_FEATURES` 常量，列出所有可用基础特征名及其域分类
  ```python
  FUNDAMENTAL_FEATURES = [
      "pe_ratio", "pb_ratio", "market_cap", "roe_ttm", "ocf_ttm",
      "roa_ttm", "gross_margin", "net_margin", "asset_turnover",
      "current_ratio", "debt_to_equity", "pcf_ratio", "ps_ratio",
      "dividend_yield", "earnings_growth", "revenue_growth",
  ]

  PRICE_FEATURES = [
      "return_5d", "return_20d", "return_60d",
      "volatility_20d", "volatility_60d", "turnover_rate",
      "avg_turnover_20d", "rsi_14", "macd", "macd_signal",
      "atr_14", "skewness_20d", "illiquidity_20d", "obv_slope_20d",
      "boll_width", "kdj_k", "kdj_d", "kdj_j",
      "volume_change_5d", "volume_change_20d",
      "close_to_high_20d", "close_to_low_20d",
  ]

  DERIVED_FEATURES = [
      "high_low_range", "close_position", "gap",
      "ma5_cross", "ma20_cross", "ma60_cross",
      "high_20d_proximity", "low_20d_proximity", "price_range",
  ]
  ```

---

### W3: FactorEvaluator — IC/IR 计算

#### Task 3.1: IC 计算引擎
- **文件**: `src/infrastructure/ml_engine/factor_evaluator.py`（新建）
- **核心实现**:
  ```python
  import numpy as np
  from scipy.stats import spearmanr
  from dataclasses import dataclass

  @dataclass(slots=True, kw_only=True)
  class FactorEvalResult:
      """因子评估结果。"""
      factor_name: str
      ic_mean: float
      ic_std: float
      ir: float
      ic_positive_ratio: float
      monotonicity: float
      sharpe_by_group: list[float]
      annual_return_by_group: list[float]
      ic_decay: dict[int, float]
      is_effective: bool

  class FactorEvaluator:
      """因子有效性评估器。"""

      # 筛选阈值
      IC_THRESHOLD = 0.03
      IR_THRESHOLD = 0.5
      IC_POSITIVE_THRESHOLD = 0.55
      SHARPE_THRESHOLD = 1.0
      MONOTONICITY_THRESHOLD = 0.8

      def compute_ic_series(
          self,
          factor_values: pd.DataFrame,
          forward_returns: pd.DataFrame,
      ) -> pd.Series:
          """计算每期截面 IC 时间序列。

          Args:
              factor_values: index=date, columns=symbol
              forward_returns: index=date, columns=symbol

          Returns:
              Series, index=date, values=IC (Spearman rank correlation)
          """
          ...

      def evaluate_single(
          self,
          factor_values: pd.DataFrame,
          forward_returns: pd.DataFrame,
          forward_days: int = 20,
      ) -> FactorEvalResult:
          """评估单个因子。"""
          ic_series = self.compute_ic_series(factor_values, forward_returns)
          # 计算 IC mean, std, IR, positive_ratio
          # 计算分层回测
          # 计算单调性
          ...

      def evaluate_batch(
          self,
          factor_dict: dict[str, pd.DataFrame],
          forward_returns: pd.DataFrame,
          top_n: int = 20,
      ) -> list[FactorEvalResult]:
          """批量评估，返回按 |IR| 排序的 top_n。"""
          ...
  ```
- **IC 计算关键细节**:
  - 每期取截面数据，计算 `spearmanr(factor, return)`
  - 处理 NaN: 丢弃 NaN 对后再计算
  - 处理样本不足: 截面股票数 < 30 时跳过该期
- **测试**: `tests/infrastructure/ml_engine/test_factor_evaluator.py`
  - 测试 IC 计算正确性（构造已知数据，验证 spearmanr 结果）
  - 测试 IR 计算（IC 均值/标准差）
  - 测试 IC 正向比例
  - 测试空数据、全 NaN 等边界条件
- **验证**: 用已知有效因子（如 `return_5d` 反转因子）验证 IC 应为负且 IR > 0.5

#### Task 3.2: 分层回测
- **文件**: `src/infrastructure/ml_engine/factor_evaluator.py`（补充）
- **实现**:
  ```python
  def _compute_quintile_returns(
      self,
      factor_values: pd.DataFrame,
      forward_returns: pd.DataFrame,
      n_groups: int = 5,
  ) -> pd.DataFrame:
      """按因子值分 N 组，计算每组的平均前瞻收益。

      Returns:
          DataFrame, index=date, columns=group_0..group_4
      """
      ...

  def _compute_monotonicity(
      self,
      group_returns: pd.DataFrame,
  ) -> float:
      """计算分层单调性评分 (0-1)。

      单调性 = 相邻组收益递增的比例
      """
      ...

  def _compute_sharpe_by_group(
      self,
      group_returns: pd.DataFrame,
  ) -> list[float]:
      """计算每组的年化夏普比率。"""
      ...
  ```

#### Task 3.3: IC 衰减分析
- **文件**: `src/infrastructure/ml_engine/factor_evaluator.py`（补充）
- **实现**:
  ```python
  def compute_ic_decay(
      self,
      factor_values: pd.DataFrame,
      snapshots_by_date: dict[date, list[StockSnapshot]],
      forward_days_list: list[int] = [5, 10, 20, 60],
  ) -> dict[int, float]:
      """计算不同前瞻期的平均 IC，绘制衰减曲线。"""
      ...
  ```

---

### W4: 快速筛选 + 深度验证

#### Task 4.1: 快速筛选逻辑
- **文件**: `src/infrastructure/ml_engine/factor_evaluator.py`（补充）
- **实现**: 在 `evaluate_single` 中计算 `is_effective`
  ```python
  @property
  def is_effective(self) -> bool:
      return (
          abs(self.ic_mean) > FactorEvaluator.IC_THRESHOLD
          and abs(self.ir) > FactorEvaluator.IR_THRESHOLD
          and self.ic_positive_ratio > FactorEvaluator.IC_POSITIVE_THRESHOLD
      )
  ```

#### Task 4.2: FactorValidator — 深度回测验证
- **文件**: `src/infrastructure/ml_engine/factor_validator.py`（新建）
- **职责**: 通过分层回测验证因子的可交易性
- **接口**:
  ```python
  class FactorValidator:
      """因子深度验证器 — 使用回测框架验证因子可交易性。"""

      def validate(
          self,
          factor: Factor,
          snapshots_by_date: dict[date, list[StockSnapshot]],
          symbols: list[str],
          start_date: datetime,
          end_date: datetime,
      ) -> ValidationReport:
          """执行分层回测验证。

          流程:
          1. 构建单因子 MultiFactorStrategy
          2. 运行回测
          3. 评估 top 组夏普比率、最大回撤
          4. 判断是否通过验证

          Returns:
              ValidationReport: 包含夏普、回撤、通过/不通过
          """
          ...

  @dataclass(slots=True, kw_only=True)
  class ValidationReport:
      """验证报告。"""
      factor_name: str
      sharpe_ratio: float
      max_drawdown: float
      annual_return: float
      win_rate: float
      passed: bool
      reason: str
  ```
- **测试**: `tests/infrastructure/ml_engine/test_factor_validator.py`
  - 测试验证流程完整性
  - 测试通过/不通过的判断逻辑
- **验证**: 用已知有效因子（如 `roe_quality`）验证应通过

---

### W5-W6: TrainingPipeline — LightGBM 训练

#### Task 5.1: 训练配置
- **文件**: `src/infrastructure/ml_engine/training_pipeline.py`（新建）
- **实现**:
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
      objective: str = "binary"  # "binary" | "regression"
      metric: str = "auc"        # "auc" | "rmse"

  @dataclass(slots=True, kw_only=True)
  class WalkForwardResult:
      """Walk-Forward 训练结果。"""
      train_period: tuple[date, date]
      val_period: tuple[date, date]
      test_period: tuple[date, date]
      val_ic: float
      test_ic: float
      feature_importance: dict[str, float]
      model_path: str
  ```

#### Task 5.2: 数据准备
- **文件**: `src/infrastructure/ml_engine/training_pipeline.py`（补充）
- **实现**:
  ```python
  class TrainingPipeline:
      """LightGBM 训练管道。"""

      def prepare_dataset(
          self,
          snapshots_by_date: dict[date, list[StockSnapshot]],
          forward_days: int = 20,
      ) -> tuple[pd.DataFrame, pd.Series]:
          """准备训练数据集。

          流程:
          1. 对每个日期，用 AutoFeatureCombiner 生成特征
          2. 计算前瞻收益率标签
          3. 合并为大矩阵
          4. 处理 NaN (前向填充 + 中位数填充)

          Returns:
              (X, y): 特征矩阵, 标签
          """
          ...
  ```
- **关键细节**:
  - 标签计算: `y = (forward_return > 0).astype(int)` 二分类
  - NaN 处理: 前向填充 → 中位数填充 → 丢弃剩余 NaN 行
  - 特征标准化: 不在训练前标准化（LightGBM 不需要），但记录均值/标准差供推理用
- **测试**: `tests/infrastructure/ml_engine/test_training_pipeline.py`
  - 测试标签无未来泄露（检查 shift 方向）
  - 测试 NaN 处理后无 NaN 残留
  - 测试特征矩阵形状正确

#### Task 5.3: 训练与 Walk-Forward
- **文件**: `src/infrastructure/ml_engine/training_pipeline.py`（补充）
- **实现**:
  ```python
      def train(
          self,
          X_train: pd.DataFrame,
          y_train: pd.Series,
          X_val: pd.DataFrame,
          y_val: pd.Series,
          config: LGBMConfig | None = None,
      ) -> lgb.LGBMClassifier:
          """训练 LightGBM 模型。"""
          ...

      def walk_forward_train(
          self,
          snapshots_by_date: dict[date, list[StockSnapshot]],
          train_years: int = 3,
          val_months: int = 6,
          test_months: int = 6,
          step_months: int = 6,
      ) -> list[WalkForwardResult]:
          """Walk-Forward 滚动训练。

          每个窗口:
          1. 准备训练/验证/测试数据
          2. 训练模型
          3. 计算验证集 IC 和测试集 IC
          4. 保存模型和结果

          Returns:
              WalkForwardResult 列表
          """
          ...
  ```

#### Task 5.4: 超参数优化
- **文件**: `src/infrastructure/ml_engine/training_pipeline.py`（补充）
- **实现**:
  ```python
      def optimize_hyperparams(
          self,
          X_train: pd.DataFrame,
          y_train: pd.Series,
          X_val: pd.DataFrame,
          y_val: pd.Series,
          n_trials: int = 50,
      ) -> LGBMConfig:
          """Optuna 超参数优化。

          优化目标: 验证集 IC（而非准确率）。
          """
          import optuna

          def objective(trial):
              config = LGBMConfig(
                  n_estimators=trial.suggest_int("n_estimators", 100, 1000),
                  learning_rate=trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
                  max_depth=trial.suggest_int("max_depth", 3, 8),
                  num_leaves=trial.suggest_int("num_leaves", 15, 63),
                  min_child_samples=trial.suggest_int("min_child_samples", 20, 200),
                  subsample=trial.suggest_float("subsample", 0.6, 1.0),
                  colsample_bytree=trial.suggest_float("colsample_bytree", 0.6, 1.0),
                  reg_alpha=trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
                  reg_lambda=trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
              )
              model = self.train(X_train, y_train, X_val, y_val, config)
              # 计算验证集 IC 作为目标
              preds = model.predict_proba(X_val)[:, 1]
              ic, _ = spearmanr(preds, y_val)
              return abs(ic)

          study = optuna.create_study(direction="maximize")
          study.optimize(objective, n_trials=n_trials)
          return LGBMConfig(**study.best_params)
  ```
- **验证**: 优化后验证集 IC > 未优化的默认配置

---

### W7: 因子存储 + 适配器 + 注册集成

#### Task 7.1: FactorRepository
- **文件**: `src/infrastructure/ml_engine/factor_repository.py`（新建）
- **实现**:
  ```python
  import json
  from pathlib import Path

  import pandas as pd

  class FactorRepository:
      """因子存储与检索。"""

      def __init__(self, data_dir: str = "data/factors") -> None:
          self._dir = Path(data_dir)
          self._dir.mkdir(parents=True, exist_ok=True)
          self._mined_dir = self._dir / "mined"
          self._mined_dir.mkdir(exist_ok=True)
          self._registry_path = self._dir / "registry.json"
          self._registry = self._load_registry()

      def _load_registry(self) -> dict:
          if self._registry_path.exists():
              return json.loads(self._registry_path.read_text())
          return {"version": 1, "factors": {}}

      def _save_registry(self) -> None:
          self._registry_path.write_text(
              json.dumps(self._registry, indent=2, ensure_ascii=False)
          )

      def save_factor(
          self,
          name: str,
          expression: str,
          factor_values: pd.DataFrame,
          metrics: dict,
      ) -> None:
          """保存挖掘因子。"""
          # 保存 parquet
          path = self._mined_dir / f"{name}.parquet"
          factor_values.to_parquet(path, engine="pyarrow")
          # 更新 registry
          self._registry["factors"][name] = {
              "name": name,
              "expression": expression,
              "created_at": date.today().isoformat(),
              "metrics": metrics,
              "status": "active",
              "inverted": metrics.get("ic_mean", 0) < 0,
              "parquet_path": str(path.relative_to(self._dir)),
          }
          self._save_registry()

      def list_factors(
          self,
          status: str = "active",
          min_ir: float = 0.0,
      ) -> list[dict]:
          """列出符合条件的因子。"""
          ...

      def load_factor_values(self, name: str) -> pd.DataFrame:
          """加载因子值 parquet。"""
          ...

      def to_domain_factor(self, name: str) -> "MinedFactor":
          """转换为 domain Factor 实例。"""
          ...

      def deactivate_factor(self, name: str, reason: str) -> None:
          """停用因子。"""
          ...
  ```
- **测试**: `tests/infrastructure/ml_engine/test_factor_repository.py`
  - 测试保存 → 加载 roundtrip
  - 测试 registry.json 正确更新
  - 测试 list_factors 过滤
  - 测试 deactivate 后不再出现在 active 列表

#### Task 7.2: MinedFactor 适配器
- **文件**: `src/domain/strategy/factors/mined_factor.py`（新建）
- **实现**:
  ```python
  from src.domain.market.value_objects.stock_snapshot import StockSnapshot

  class MinedFactor:
      """挖掘因子适配器 — 适配 Factor Protocol。

      不依赖 pandas/numpy，仅使用标准字典。
      """

      def __init__(
          self,
          name: str,
          values_by_date: dict[str, dict[str, float]],
          inverted: bool = False,
      ) -> None:
          self.name = name
          self._values_by_date = values_by_date
          self.inverted = inverted

      def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
          if not snapshots:
              return {}
          date_key = snapshots[0].date.strftime("%Y-%m-%d")
          day_values = self._values_by_date.get(date_key, {})
          return {
              s.symbol: day_values[s.symbol]
              for s in snapshots
              if s.symbol in day_values
          }
  ```
- **测试**: `tests/domain/strategy/factors/test_mined_factor.py`
  - 测试 compute 返回正确值
  - 测试日期不匹配时返回空
  - 测试 MinedFactor 满足 Factor Protocol

#### Task 7.3: 策略注册集成
- **文件**: `src/domain/strategy/registry.py`（修改）
- **操作**: 修改 `_build_multi_factor`，增加从 FactorRepository 加载挖掘因子的逻辑
- **改动范围**: 仅增加 ~15 行 try/except 代码块，不改变现有因子加载逻辑
- **测试**: 验证现有 30 因子不受影响，挖掘因子可正确加载

---

### W8: 端到端集成 + CLI

#### Task 8.1: FactorMiner 编排
- **文件**: `src/infrastructure/ml_engine/factor_miner.py`（新建）
- **实现**:
  ```python
  from dataclasses import dataclass

  @dataclass(slots=True, kw_only=True)
  class MiningReport:
      """挖掘报告。"""
      total_candidates: int
      quick_filtered: int
      deep_validated: int
      stored_factors: list[str]
      duration_seconds: float
      details: list[dict]  # 每个候选因子的评估结果

  class FactorMiner:
      """因子挖掘主流程。"""

      def __init__(
          self,
          combiner: AutoFeatureCombiner | None = None,
          evaluator: FactorEvaluator | None = None,
          validator: FactorValidator | None = None,
          repository: FactorRepository | None = None,
      ) -> None:
          self._combiner = combiner or AutoFeatureCombiner()
          self._evaluator = evaluator or FactorEvaluator()
          self._validator = validator or FactorValidator()
          self._repository = repository or FactorRepository()

      def mine(
          self,
          snapshots_by_date: dict[date, list[StockSnapshot]],
          forward_days: int = 20,
          target_count: int = 10,
      ) -> MiningReport:
          """执行一次完整的因子挖掘。"""
          import time
          start = time.time()

          # Step 1: 生成候选特征
          all_combinations = {}
          for d, snapshots in snapshots_by_date.items():
              df = self._combiner.generate_combinations(snapshots)
              all_combinations[d] = df

          # Step 2: 计算前瞻收益
          forward_returns = self._compute_forward_returns(
              snapshots_by_date, forward_days
          )

          # Step 3: 快速筛选 (IC/IR)
          factor_dict = self._stack_factors(all_combinations)
          eval_results = self._evaluator.evaluate_batch(
              factor_dict, forward_returns, top_n=target_count
          )
          quick_passed = [r for r in eval_results if r.is_effective]

          # Step 4: 深度验证
          deep_passed = []
          for result in quick_passed:
              factor = self._build_temp_factor(result.factor_name, all_combinations)
              report = self._validator.validate(factor, ...)
              if report.passed:
                  deep_passed.append((result, report))

          # Step 5: 入库
          stored = []
          for eval_result, val_report in deep_passed:
              self._repository.save_factor(
                  name=eval_result.factor_name,
                  expression=self._combiner.get_expression(eval_result.factor_name),
                  factor_values=factor_dict[eval_result.factor_name],
                  metrics={
                      "ic_mean": eval_result.ic_mean,
                      "ir": eval_result.ir,
                      "sharpe_top_group": val_report.sharpe_ratio,
                      "monotonicity": eval_result.monotonicity,
                  },
              )
              stored.append(eval_result.factor_name)

          duration = time.time() - start
          return MiningReport(
              total_candidates=len(factor_dict),
              quick_filtered=len(quick_passed),
              deep_validated=len(deep_passed),
              stored_factors=stored,
              duration_seconds=duration,
              details=[...],
          )
  ```
- **测试**: `tests/infrastructure/ml_engine/test_factor_miner.py`
  - 端到端测试（使用小型模拟数据）
  - 测试每一步的输出格式正确

#### Task 8.2: CLI 命令
- **文件**: `src/interfaces/cli/factor_mining.py`（新建）
- **实现**:
  ```python
  """因子挖掘 CLI。"""

  import argparse
  from datetime import datetime

  def main():
      parser = argparse.ArgumentParser(description="ML 因子挖掘引擎")
      sub = parser.add_subparsers(dest="command")

      # mine: 执行一次挖掘
      mine_parser = sub.add_parser("mine", help="执行因子挖掘")
      mine_parser.add_argument("--start", required=True, help="起始日期 (YYYY-MM-DD)")
      mine_parser.add_argument("--end", required=True, help="结束日期 (YYYY-MM-DD)")
      mine_parser.add_argument("--symbols", default="all", help="股票池 (all / file path)")
      mine_parser.add_argument("--target", type=int, default=10, help="目标挖掘数")

      # evaluate: 评估单个因子表达式
      eval_parser = sub.add_parser("evaluate", help="评估因子表达式")
      eval_parser.add_argument("--expr", required=True, help="因子表达式 (如 return_5d / pe_ratio)")
      eval_parser.add_argument("--start", required=True)
      eval_parser.add_argument("--end", required=True)

      # list: 列出已入库因子
      sub.add_parser("list", help="列出已入库因子")

      # train: 训练 ML 模型
      train_parser = sub.add_parser("train", help="训练 LightGBM 模型")
      train_parser.add_argument("--start", required=True)
      train_parser.add_argument("--end", required=True)
      train_parser.add_argument("--optimize", action="store_true", help="启用 Optuna 超参优化")

      args = parser.parse_args()
      # ... dispatch to appropriate handler ...

  if __name__ == "__main__":
      main()
  ```
- **使用示例**:
  ```bash
  # 执行因子挖掘
  python -m src.interfaces.cli.factor_mining mine \
      --start 2021-01-01 --end 2024-01-01 --target 10

  # 评估单个因子
  python -m src.interfaces.cli.factor_mining evaluate \
      --expr "return_5d / pe_ratio" --start 2021-01-01 --end 2024-01-01

  # 列出已入库因子
  python -m src.interfaces.cli.factor_mining list

  # 训练 ML 模型
  python -m src.interfaces.cli.factor_mining train \
      --start 2021-01-01 --end 2024-01-01 --optimize
  ```

#### Task 8.3: ModelLoader 扩展
- **文件**: `src/infrastructure/ml_engine/model_loader.py`（修改）
- **操作**: 新增 `load_lightgbm` 方法（约 10 行）
- **验证**: 加载已保存的 LightGBM 模型文件

#### Task 8.4: 端到端验证
- **操作**: 使用 3 年历史数据运行完整挖掘流程
- **验证标准**:
  - 全流程耗时 < 2 小时
  - 生成 100+ 候选因子
  - 快速筛选通过 5-20 个
  - 深度验证通过 1-3 个
  - 入库因子可在 MultiFactorStrategy 中使用
  - 回测入库因子的夏普比率 > 1.0

---

## 三、新增文件清单

| 文件 | 类型 | 行数估算 | 职责 |
|------|------|---------|------|
| `src/infrastructure/ml_engine/data_loader.py` | 新建 | ~120 | 数据加载与标签计算 |
| `src/infrastructure/ml_engine/feature_combiner.py` | 新建 | ~250 | 自动特征组合 |
| `src/infrastructure/ml_engine/factor_evaluator.py` | 新建 | ~200 | IC/IR/分层回测 |
| `src/infrastructure/ml_engine/factor_validator.py` | 新建 | ~100 | 深度回测验证 |
| `src/infrastructure/ml_engine/training_pipeline.py` | 新建 | ~250 | LightGBM 训练管道 |
| `src/infrastructure/ml_engine/factor_repository.py` | 新建 | ~150 | 因子存储与检索 |
| `src/infrastructure/ml_engine/factor_miner.py` | 新建 | ~150 | 挖掘流程编排 |
| `src/domain/strategy/factors/mined_factor.py` | 新建 | ~40 | 挖掘因子适配器 |
| `src/interfaces/cli/factor_mining.py` | 新建 | ~100 | CLI 入口 |
| **小计** | | **~1,360** | |

## 四、修改文件清单

| 文件 | 改动量 | 改动内容 |
|------|--------|---------|
| `pyproject.toml` | +5 行 | 新增 `[ml]` 依赖组 |
| `src/infrastructure/ml_engine/feature_pipeline.py` | +40 行 | 新增布林带、KDJ、成交量变化率等基础特征 |
| `src/infrastructure/ml_engine/model_loader.py` | +10 行 | 新增 `load_lightgbm` 方法 |
| `src/domain/market/value_objects/stock_snapshot.py` | +10 行 | 新增基础特征字段 |
| `src/domain/strategy/registry.py` | +15 行 | 加载挖掘因子 |
| **小计** | **+80 行** | |

## 五、新增测试清单

| 测试文件 | 行数估算 | 覆盖模块 |
|---------|---------|---------|
| `tests/infrastructure/ml_engine/test_data_loader.py` | ~80 | data_loader |
| `tests/infrastructure/ml_engine/test_feature_combiner.py` | ~120 | feature_combiner |
| `tests/infrastructure/ml_engine/test_factor_evaluator.py` | ~150 | factor_evaluator |
| `tests/infrastructure/ml_engine/test_factor_validator.py` | ~80 | factor_validator |
| `tests/infrastructure/ml_engine/test_training_pipeline.py` | ~100 | training_pipeline |
| `tests/infrastructure/ml_engine/test_factor_repository.py` | ~80 | factor_repository |
| `tests/infrastructure/ml_engine/test_factor_miner.py` | ~60 | factor_miner |
| `tests/domain/strategy/factors/test_mined_factor.py` | ~40 | mined_factor |
| **小计** | **~710** | |

---

## 六、里程碑验收

| 里程碑 | 时间 | 验收标准 |
|--------|------|---------|
| M1: 特征工程 | W2 末 | 生成 100+ 组合特征，单次 < 5s，测试全绿 |
| M2: 因子评估 | W4 末 | IC/IR 计算正确，分层回测可用，快速筛选可用 |
| M3: 训练管道 | W6 末 | Walk-Forward 训练可用，样本外 IC > 0.03 |
| M4: 因子入库 | W7 末 | 因子入库 → MultiFactorStrategy 自动加载 |
| M5: 端到端 | W8 末 | 一键挖掘全流程可用，CLI 命令可用 |

---

## 七、后续迭代方向

| 方向 | 优先级 | 说明 |
|------|--------|------|
| 因子衰减监控 | P1 | 每月重新评估入库因子，自动停用失效因子 |
| 表达式语言 | P2 | 支持 `return_5d / pe_ratio` 这样的字符串表达式直接生成因子 |
| MLflow 集成 | P2 | 模型版本管理、实验追踪 |
| 深度学习模型 | P3 | LSTM / Transformer 捕捉时序模式 |
| 在线学习 | P3 | 增量更新模型，无需全量重训练 |

---

**文档结束**
