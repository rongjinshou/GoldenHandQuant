"""ML 模型训练 CLI。"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="ML 收益预测模型训练")
    parser.add_argument("--symbols", type=str, default="000300.SH", help="股票列表，逗号分隔")
    parser.add_argument("--start-date", type=str, required=True, help="训练开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, required=True, help="训练结束日期 (YYYY-MM-DD)")
    parser.add_argument("--label-horizon", type=int, default=5, help="前瞻天数")
    parser.add_argument("--model-name", type=str, default="lgbm_return_5d", help="模型名称")
    parser.add_argument("--n-trials", type=int, default=50, help="Optuna 搜索次数")
    parser.add_argument("--n-cv-splits", type=int, default=5, help="CV 折数")
    parser.add_argument("--top-n", type=int, default=10, help="选股 Top N")
    parser.add_argument("--config", type=str, default=None, help="YAML 配置文件路径")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]

    print(f"[ML Train] 模型: {args.model_name}")
    print(f"[ML Train] 标的: {symbols}")
    print(f"[ML Train] 区间: {args.start_date} ~ {args.end_date}")
    print(f"[ML Train] Optuna trials: {args.n_trials}, CV splits: {args.n_cv_splits}")

    # 步骤 1: 构建数据集
    print("\n[Step 1/4] 构建训练数据集...")
    print("  需要提供数据源 (market_gateway, fundamental_registry)")
    print("  示例: 从已有 parquet 加载或通过 QMT 获取数据")

    # 步骤 2: 训练
    print("\n[Step 2/4] 训练 LightGBM 模型...")
    from src.infrastructure.ml_engine.dataset_builder import DatasetBuilder
    from src.infrastructure.ml_engine.trainer import LightGBMTrainer, TrainConfig

    dataset_path = f"data/datasets/{args.model_name}_{args.start_date}_{args.end_date}.parquet"
    try:
        df = DatasetBuilder.load(dataset_path)
        print(f"  从 {dataset_path} 加载数据集: {len(df)} 行")
    except FileNotFoundError:
        print(f"  数据集不存在: {dataset_path}")
        print("  请先构建数据集或指定正确的路径")
        sys.exit(1)

    train_config = TrainConfig(
        model_name=args.model_name,
        n_optuna_trials=args.n_trials,
        n_cv_splits=args.n_cv_splits,
    )
    trainer = LightGBMTrainer(train_config)
    result = trainer.train(df)

    print("\n  训练完成:")
    print(f"    样本数: {result.train_samples}")
    print(f"    特征数: {result.feature_count}")
    print(f"    平均 IC: {result.mean_ic:.4f}")
    print(f"    IC IR: {result.ic_ir:.4f}")
    print(f"    最优参数: {result.best_params}")
    print(f"    模型路径: {result.model_path}")

    # 步骤 3: 评估
    print("\n[Step 3/4] 模型评估...")
    import joblib

    from src.infrastructure.ml_engine.evaluator import ModelEvaluator

    eval_size = max(100, len(df) // 5)
    eval_df = df.tail(eval_size).copy()

    model = joblib.load(result.model_path)
    feature_cols = [
        c for c in df.columns
        if c not in {"date", "symbol", "label", "actual_return"}
        and df[c].dtype in ("float64", "float32", "int64")
    ]

    eval_df["pred"] = model.predict(eval_df[feature_cols])
    eval_df["actual"] = eval_df["label"]

    evaluator = ModelEvaluator()
    pred_metrics = evaluator.evaluate_predictions(eval_df[["date", "symbol", "pred", "actual"]])

    print(f"    IC: {pred_metrics.ic:.4f}")
    print(f"    IC IR: {pred_metrics.ic_ir:.4f}")
    print(f"    IC > 0 比例: {pred_metrics.ic_positive_ratio:.2%}")

    # 步骤 4: 注册模型
    print("\n[Step 4/4] 注册模型...")
    from datetime import datetime

    from src.infrastructure.ml_engine.model_registry import ModelMetadata, ModelRegistry

    registry = ModelRegistry()
    metadata = ModelMetadata(
        model_name=args.model_name,
        model_type="lightgbm",
        created_at=datetime.now().isoformat(),
        train_period=f"{args.start_date} ~ {args.end_date}",
        eval_period="",
        label_horizon=args.label_horizon,
        feature_count=result.feature_count,
        train_samples=result.train_samples,
        best_params=result.best_params,
        cv_metrics={"mean_ic": result.mean_ic, "ic_ir": result.ic_ir},
        features=feature_cols,
        model_path=result.model_path,
    )
    registry.register(metadata)
    print(f"  模型已注册: {args.model_name}")

    print("\n[完成] ML 训练流程结束。")


if __name__ == "__main__":
    main()
