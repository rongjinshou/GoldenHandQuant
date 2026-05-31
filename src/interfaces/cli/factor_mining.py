"""因子挖掘 CLI — mine / evaluate / list / train。"""

from __future__ import annotations

import argparse
import sys
from datetime import date


def _cmd_mine(args: argparse.Namespace) -> None:
    """执行因子挖掘。"""
    from src.infrastructure.ml_engine.factor_miner import FactorMiner
    from src.infrastructure.ml_engine.factor_repository import FactorRepository

    print(f"[FactorMining] Loading data from {args.start} to {args.end} ...")

    # 加载数据（需用户提供数据加载方式，此处用空字典演示）
    snapshots_by_date: dict[date, list] = {}

    if not snapshots_by_date:
        print("[FactorMining] No snapshot data loaded.")
        print("  Please ensure historical snapshot data is available.")
        print("  You can use MLDataLoader or provide snapshots_by_date directly.")
        return

    repo = FactorRepository(data_dir=args.data_dir)
    miner = FactorMiner(repository=repo)

    print(f"[FactorMining] Mining with target_count={args.target}, strategy={args.strategy} ...")
    report = miner.mine(
        snapshots_by_date=snapshots_by_date,
        target_count=args.target,
        strategy=args.strategy,
    )

    print("\n[FactorMining] Mining Report:")
    print(f"  Total candidates: {report.total_candidates}")
    print(f"  Quick filtered:   {report.quick_filtered}")
    print(f"  Stored factors:   {report.deep_validated}")
    print(f"  Duration:         {report.duration_seconds:.1f}s")

    if report.stored_factors:
        print("\n  Stored factors:")
        for detail in report.details:
            print(f"    - {detail['name']}: IC={detail['ic_mean']:.4f}, IR={detail['ir']:.2f}")


def _cmd_evaluate(args: argparse.Namespace) -> None:
    """评估单个因子表达式。"""
    print(f"[FactorMining] Evaluating expression: {args.expr}")
    print(f"  Date range: {args.start} to {args.end}")

    # 需要加载数据才能评估
    snapshots_by_date: dict[date, list] = {}
    if not snapshots_by_date:
        print("[FactorMining] No snapshot data loaded for evaluation.")
        return

    print("[FactorMining] Generating features and evaluating ...")
    # 实际评估逻辑需要完整数据管道
    print("[FactorMining] Evaluation complete.")


def _cmd_list(args: argparse.Namespace) -> None:
    """列出已入库因子。"""
    from src.infrastructure.ml_engine.factor_repository import FactorRepository

    repo = FactorRepository(data_dir=args.data_dir)
    factors = repo.list_factors(status=args.status, min_ir=args.min_ir)

    if not factors:
        print(f"No factors found (status={args.status}, min_ir={args.min_ir})")
        return

    print(f"Found {len(factors)} factor(s):")
    print(f"{'Name':<40} {'IC':>8} {'IR':>8} {'Inverted':>10} {'Expression'}")
    print("-" * 100)
    for f in factors:
        m = f.get("metrics", {})
        inv = "Yes" if f.get("inverted") else "No"
        print(
            f"{f['name']:<40} "
            f"{m.get('ic_mean', 0):>8.4f} "
            f"{m.get('ir', 0):>8.2f} "
            f"{inv:>10} "
            f"{f.get('expression', '')}"
        )


def _cmd_train(args: argparse.Namespace) -> None:
    """训练 LightGBM 模型。"""
    from src.infrastructure.ml_engine.training_pipeline import TrainingPipeline

    print(f"[FactorMining] Training LightGBM model from {args.start} to {args.end}")

    snapshots_by_date: dict[date, list] = {}
    if not snapshots_by_date:
        print("[FactorMining] No snapshot data loaded for training.")
        return

    pipeline = TrainingPipeline()

    if args.optimize:
        print("[FactorMining] Running Optuna hyperparameter optimization ...")
        features, labels = pipeline.prepare_dataset(snapshots_by_date)
        if features.empty:
            print("[FactorMining] No valid training data.")
            return
        # 简单切分：前 80% 训练，后 20% 验证
        split_idx = int(len(features) * 0.8)
        feat_train, feat_val = features.iloc[:split_idx], features.iloc[split_idx:]
        label_train, label_val = labels.iloc[:split_idx], labels.iloc[split_idx:]
        best_config = pipeline.optimize_hyperparams(feat_train, label_train, feat_val, label_val)
        print(f"[FactorMining] Best config: {best_config}")
    else:
        print("[FactorMining] Running Walk-Forward training ...")
        results = pipeline.walk_forward_train(snapshots_by_date)
        for r in results:
            print(f"  Window {r.train_period} -> val_IC={r.val_ic:.4f}, test_IC={r.test_ic:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ML 因子挖掘引擎",
        prog="factor_mining",
    )
    parser.add_argument(
        "--data-dir", default="data/factors",
        help="因子数据目录 (default: data/factors)",
    )

    sub = parser.add_subparsers(dest="command")

    # mine
    mine_parser = sub.add_parser("mine", help="执行因子挖掘")
    mine_parser.add_argument("--start", required=True, help="起始日期 (YYYY-MM-DD)")
    mine_parser.add_argument("--end", required=True, help="结束日期 (YYYY-MM-DD)")
    mine_parser.add_argument("--target", type=int, default=10, help="目标挖掘数")
    mine_parser.add_argument(
        "--strategy", default="standard",
        choices=["standard", "aggressive", "conservative"],
        help="组合策略",
    )

    # evaluate
    eval_parser = sub.add_parser("evaluate", help="评估因子表达式")
    eval_parser.add_argument("--expr", required=True, help="因子表达式")
    eval_parser.add_argument("--start", required=True, help="起始日期")
    eval_parser.add_argument("--end", required=True, help="结束日期")

    # list
    list_parser = sub.add_parser("list", help="列出已入库因子")
    list_parser.add_argument("--status", default="active", help="因子状态过滤")
    list_parser.add_argument("--min-ir", type=float, default=0.0, help="最小 IR 过滤")

    # train
    train_parser = sub.add_parser("train", help="训练 LightGBM 模型")
    train_parser.add_argument("--start", required=True, help="起始日期")
    train_parser.add_argument("--end", required=True, help="结束日期")
    train_parser.add_argument("--optimize", action="store_true", help="启用 Optuna 超参优化")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "mine": _cmd_mine,
        "evaluate": _cmd_evaluate,
        "list": _cmd_list,
        "train": _cmd_train,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
