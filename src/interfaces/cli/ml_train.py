"""ML 模型训练 CLI。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(args: argparse.Namespace | None = None) -> None:
    """ML 模型训练入口。

    Args:
        args: 预解析的参数（quant 子命令调用时传入）。为 None 时从 sys.argv 解析。
    """
    if args is None:
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
    from src.infrastructure.ml_engine.dataset_builder import DatasetBuilder

    dataset_path = f"data/datasets/{args.model_name}_{args.start_date}_{args.end_date}.parquet"

    try:
        df = DatasetBuilder.load(dataset_path)
        print(f"  从 {dataset_path} 加载数据集: {len(df)} 行")
    except FileNotFoundError:
        print(f"  数据集不存在: {dataset_path}")
        print("  自动从 QMT 数据构建数据集...")
        df = _build_dataset_from_qmt(
            symbols=symbols,
            start_date=args.start_date,
            end_date=args.end_date,
            label_horizon=args.label_horizon,
            dataset_path=dataset_path,
        )

    # 步骤 2: 训练
    print("\n[Step 2/4] 训练 LightGBM 模型...")
    from src.infrastructure.ml_engine.trainer import LightGBMTrainer, TrainConfig

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


def _build_dataset_from_qmt(
    symbols: list[str],
    start_date: str,
    end_date: str,
    label_horizon: int,
    dataset_path: str,
):
    """从 QMT 数据自动构建 parquet 数据集。"""
    import pandas as pd

    from src.domain.market.services.fundamental_registry import FundamentalRegistry
    from src.infrastructure.ml_engine.dataset_builder import DatasetBuilder, DatasetConfig

    # 如果 symbols 包含指数代码，替换为成分股
    actual_symbols = _resolve_symbols(symbols)
    print(f"  获取 {len(actual_symbols)} 只股票数据...")

    # 获取历史数据
    print("  [1/3] 获取历史 K 线数据...")
    from src.infrastructure.gateway.qmt_history_data import QmtHistoryDataFetcher

    history_fetcher = QmtHistoryDataFetcher()
    bars_by_symbol = history_fetcher.fetch(
        symbols=actual_symbols, start_date=start_date, end_date=end_date,
    )
    print(f"  获取到 {len(bars_by_symbol)} 只股票历史数据")

    if not bars_by_symbol:
        print("  错误: 无法获取历史数据")
        sys.exit(1)

    # 获取基本面数据
    print("  [2/3] 获取基本面数据...")
    from src.infrastructure.gateway.qmt_fundamental_fetcher import QmtFundamentalFetcher

    fund_fetcher = QmtFundamentalFetcher()
    fund_snapshots = fund_fetcher.fetch_by_range(start_date, end_date, symbols=actual_symbols)
    print(f"  获取到 {len(fund_snapshots)} 条基本面快照")

    # 构建截面数据
    print("  [3/3] 构建数据集...")
    from src.infrastructure.ml_engine.feature_pipeline import FeaturePipeline

    registry = FundamentalRegistry()
    registry.load_snapshots(fund_snapshots)

    # 构建 snapshots_by_date 和 price_series
    from datetime import datetime as dt

    snapshots_by_date: dict[dt, list] = {}
    price_series_map: dict[str, pd.Series] = {}

    # 按日期分组 bars
    all_dates: set[dt] = set()
    for symbol, bars in bars_by_symbol.items():
        prices = {}
        for bar in bars:
            d = bar.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            all_dates.add(d)
            prices[d] = bar.close
        if prices:
            price_series_map[symbol] = pd.Series(prices)

    for d in sorted(all_dates):
        bars_on_date = {}
        bar_history = {}
        for symbol, bars in bars_by_symbol.items():
            hist = [b for b in bars if b.timestamp.replace(hour=0, minute=0, second=0, microsecond=0) <= d]
            if hist:
                bar_history[symbol] = hist
                for b in bars:
                    if b.timestamp.replace(hour=0, minute=0, second=0, microsecond=0) == d:
                        bars_on_date[symbol] = b
                        break

        if bars_on_date:
            cross = FeaturePipeline.build_cross_section(
                date=d, bars=bars_on_date, registry=registry, bar_history=bar_history,
            )
            if cross:
                snapshots_by_date[d] = cross

    if not snapshots_by_date:
        print("  错误: 无法构建截面数据")
        sys.exit(1)

    # 构建并保存数据集
    config = DatasetConfig(label_horizon=label_horizon)
    builder = DatasetBuilder(config)
    df = builder.build(snapshots_by_date, price_series_map)

    if df.empty:
        print("  错误: 构建的数据集为空")
        sys.exit(1)

    Path(dataset_path).parent.mkdir(parents=True, exist_ok=True)
    DatasetBuilder.save(df, dataset_path)
    print(f"  数据集已保存: {dataset_path} ({len(df)} 行)")

    return df


def _resolve_symbols(symbols: list[str]) -> list[str]:
    """解析符号列表，将指数代码替换为成分股。"""
    result: list[str] = []
    for sym in symbols:
        # 如果是指数代码（如 000300.SH），替换为沪深A股
        if sym in ("000300.SH", "000905.SH", "000001.SH", "000852.SH"):
            try:
                from src.infrastructure.gateway.xtquant_client import xtdata
                stocks = xtdata.get_stock_list_in_sector("沪深A股")
                # 限制数量避免过慢
                result.extend(sorted(stocks)[:500])
                print(f"  指数 {sym} 已展开为 {min(len(stocks), 500)} 只股票")
            except Exception:
                result.append(sym)
        else:
            result.append(sym)

    # 去重并限制数量
    result = sorted(set(result))
    if len(result) > 500:
        print(f"  股票数量 {len(result)} 超过 500，截取前 500 只")
        result = result[:500]

    return result if result else symbols


if __name__ == "__main__":
    main()
