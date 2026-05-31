"""ML 模型评估 CLI。"""

from __future__ import annotations

import argparse
import sys


def main(args: argparse.Namespace | None = None) -> None:
    """ML 模型评估入口。

    Args:
        args: 预解析的参数（quant 子命令调用时传入）。为 None 时从 sys.argv 解析。
    """
    if args is None:
        parser = argparse.ArgumentParser(description="ML 收益预测模型评估")
        parser.add_argument("--model-name", type=str, required=True, help="模型名称")
        parser.add_argument("--eval-start", type=str, required=True, help="评估开始日期")
        parser.add_argument("--eval-end", type=str, required=True, help="评估结束日期")
        parser.add_argument("--quintiles", type=int, default=5, help="分层数")
        parser.add_argument("--plot", action="store_true", help="绘制图表")
        args = parser.parse_args()

    print(f"[ML Evaluate] 模型: {args.model_name}")
    print(f"[ML Evaluate] 评估区间: {args.eval_start} ~ {args.eval_end}")

    from src.infrastructure.ml_engine.model_registry import ModelRegistry

    registry = ModelRegistry()
    try:
        metadata = registry.get_latest(args.model_name)
    except KeyError:
        print(f"  模型未注册: {args.model_name}")
        sys.exit(1)

    print(f"  模型路径: {metadata.model_path}")
    print(f"  特征数: {metadata.feature_count}")

    import joblib

    model = joblib.load(metadata.model_path)

    dataset_path = f"data/datasets/{args.model_name}_{args.eval_start}_{args.eval_end}.parquet"
    from src.infrastructure.ml_engine.dataset_builder import DatasetBuilder

    try:
        df = DatasetBuilder.load(dataset_path)
        print(f"  从 {dataset_path} 加载数据集: {len(df)} 行")
    except FileNotFoundError:
        print(f"  数据集不存在: {dataset_path}")
        print("  请先构建评估数据集")
        sys.exit(1)

    feature_cols = metadata.features or [
        c for c in df.columns
        if c not in {"date", "symbol", "label", "actual_return"}
        and df[c].dtype in ("float64", "float32", "int64")
    ]

    df["pred"] = model.predict(df[feature_cols])
    df["actual"] = df["label"]

    from src.infrastructure.ml_engine.evaluator import ModelEvaluator

    evaluator = ModelEvaluator()
    report = evaluator.full_evaluation(
        model_name=args.model_name,
        predictions=df[["date", "symbol", "pred", "actual"]],
        price_data={},
        feature_importance=dict(zip(metadata.features, [0.0] * len(metadata.features))),
    )

    print("\n" + "=" * 60)
    print(f"模型评估报告: {report.model_name}")
    print(f"评估区间: {report.eval_period}")
    print("=" * 60)

    pm = report.prediction_metrics
    print("\n[预测指标]")
    print(f"  IC: {pm.ic:.4f}")
    print(f"  IC IR: {pm.ic_ir:.4f}")
    print(f"  IC > 0 比例: {pm.ic_positive_ratio:.2%}")
    print(f"  IC 自相关: {pm.rank_autocorrelation:.4f}")

    print("\n[分层回测]")
    for qr in report.quintile_results:
        print(
            f"  Q{qr.quintile}: 年化收益={qr.annualized_return:.2%}, "
            f"夏普={qr.sharpe_ratio:.2f}, 最大回撤={qr.max_drawdown:.2%}"
        )

    print(f"\n  多空收益: {report.long_short_return:.2%}")

    if report.feature_importance:
        print("\n[特征重要性 Top 10]")
        sorted_fi = sorted(report.feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
        for fname, imp in sorted_fi:
            print(f"  {fname}: {imp:.4f}")

    print("\n[完成]")


if __name__ == "__main__":
    main()
