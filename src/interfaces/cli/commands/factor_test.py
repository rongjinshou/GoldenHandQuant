"""quant factor-test 子命令实现 — 接通 FactorTestRunner 引擎。"""

import argparse
import json


def run_factor_test(args: argparse.Namespace) -> None:
    """执行因子假设测试。"""
    from src.domain.strategy.factor_test.factor_catalog import resolve_factors

    factor_str: str = args.factors
    start_date: str = args.start_date
    end_date: str = args.end_date
    split_date: str | None = args.split_date
    num_layers: int = args.num_layers
    rebalance_days: int = args.rebalance_days
    output_path: str | None = args.output
    config_path: str = args.config

    # 1. 解析因子列表
    try:
        hypotheses = resolve_factors(factor_str)
    except ValueError as e:
        print(f"Error: {e}")
        return

    print("=== Factor Hypothesis Test ===")
    print(f"Factors: {', '.join(f'{h.factor_id}({h.name})' for h in hypotheses)}")
    print(f"Period:  {start_date} → {end_date}")
    if split_date:
        print(f"Split:   IS={start_date}→{split_date} | OOS={split_date}→{end_date}")
    print(f"Layers:  {num_layers}")
    print(f"Rebalance: 每 {rebalance_days} 个交易日调仓")
    if len(hypotheses) > 1 and not split_date:
        print("⚠️  多重检验提醒: 同时测多个因子且无样本外切分 → 单个'显著'很可能是噪声; "
              "强烈建议加 --split 用样本外定夺。")
    print()

    # 2. 组装数据服务（store + fetchers）与全市场股票池
    from src.interfaces.cli.commands._data_wiring import build_data_wiring, resolve_universe

    wiring = build_data_wiring(config_path)
    symbols = resolve_universe(wiring)

    # 3. 截面因子测试需要足够宽的股票池
    if len(symbols) <= 5:
        print(f"Warning: Only {len(symbols)} symbols. Factor testing works best with 200+ stocks.")
        print(f"Consider configuring more symbols in {config_path} or use the QMT data source.")

    # 4. 创建服务并执行（默认 DB 快路径; --no-store 回退旧内存路径）
    from src.application.factor_test_app import FactorTestAppService

    use_store = not getattr(args, "no_store", False)
    if not use_store:
        print("(--no-store: 使用旧内存管道)")
    service = FactorTestAppService(
        history_fetcher=wiring.history_fetcher,
        fundamental_fetcher=wiring.fundamental_fetcher,
        market_data=wiring.market_data if use_store else None,
    )

    print(f"[Step 1] Preparing data ({len(symbols)} symbols)...")
    try:
        snapshots_by_date, returns_by_date, prices_by_date = service.prepare_snapshots(
            symbols, start_date, end_date,
        )
    except Exception as e:
        print(f"Error preparing data: {e}")
        return

    print(f"  → {len(snapshots_by_date)} trading days, "
          f"avg {sum(len(v) for v in snapshots_by_date.values()) / max(len(snapshots_by_date), 1):.0f} stocks/day")

    print("\n[Step 2] Running factor tests...")
    results = service.run_batch(
        hypotheses=hypotheses,
        snapshots_by_date=snapshots_by_date,
        returns_by_date=returns_by_date,
        prices_by_date=prices_by_date,
        test_period=(start_date, end_date),
        split_date=split_date,
        num_layers=num_layers,
        rebalance_days=rebalance_days,
    )

    # 6. 输出汇总
    print(f"\n{'=' * 80}")
    print(f"{'FACTOR VERDICT SUMMARY':^80}")
    print(f"{'=' * 80}")
    print(f"{'ID':<5} {'Name':<12} {'IC':>8} {'IR':>8} {'Mono':>6} {'L/S':>8} {'Score':>6} {'Grade':>6} {'Verdict':>8}")
    print(f"{'-' * 80}")

    passed_count = 0
    for r in results:
        v = r.verdict
        status = "PASS" if v.passed else "FAIL"
        if v.passed:
            passed_count += 1
        print(f"{v.factor_id:<5} {v.factor_name:<12} {v.ic_mean:>8.4f} {v.ir:>8.3f} "
              f"{v.monotonicity_score:>6.2f} {v.long_short_return:>8.2%} "
              f"{v.score:>6.0f} {v.grade:>6} {status:>8}")

    print(f"{'-' * 80}")
    print(f"Passed: {passed_count}/{len(results)}")

    # 7. 详细判决原因
    print(f"\n{'DETAILED VERDICTS':^80}")
    for r in results:
        v = r.verdict
        status = "PASS" if v.passed else "FAIL"
        print(f"\n[{v.factor_id}] {v.factor_name} — {status}")
        for reason in v.reasons:
            print(f"  {reason}")

    # 8. 判决留痕: JSON (可选) + factor_verdicts 入库 (总是)
    verdict_rows = []
    for r in results:
        v = r.verdict
        verdict_rows.append({
            "factor_id": v.factor_id,
            "factor_name": v.factor_name,
            "expression": v.expression,
            "ic_mean": v.ic_mean,
            "ir": v.ir,
            "ic_positive_rate": v.ic_positive_rate,
            "monotonicity_score": v.monotonicity_score,
            "long_short_return": v.long_short_return,
            "score": v.score,
            "grade": v.grade,
            "oos_ic_mean": v.oos_ic_mean,
            "oos_ir": v.oos_ir,
            "oos_long_short_return": v.oos_long_short_return,
            "passed": v.passed,
            "reasons": v.reasons,
        })

    if output_path:
        output = {
            "test_period": [start_date, end_date],
            "split_date": split_date,
            "num_layers": num_layers,
            "rebalance_days": rebalance_days,
            "results": verdict_rows,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to {output_path}")

    from datetime import datetime

    from src.domain.market.services.feature_engine import FEATURE_VERSION

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_params = {
        "start": start_date, "end": end_date, "split": split_date,
        "rebalance_days": rebalance_days, "num_layers": num_layers,
        "feature_version": FEATURE_VERSION, "universe_count": len(symbols),
        "store_path": "memory" if not use_store else "db",
    }
    try:
        wiring.store.insert_verdicts(run_id, run_params, verdict_rows)
        print(f"Verdicts persisted to factor_verdicts (run_id={run_id})")
    except Exception as e:
        print(f"Warning: 判决入库失败 ({e}); JSON/终端输出不受影响。")
