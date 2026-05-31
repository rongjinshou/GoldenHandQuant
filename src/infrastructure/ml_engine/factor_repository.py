"""因子存储与检索 — parquet 存储 + registry.json。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd


class FactorRepository:
    """因子存储与检索。"""

    def __init__(self, data_dir: str = "data/factors") -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._mined_dir = self._dir / "mined"
        self._mined_dir.mkdir(exist_ok=True)
        self._models_dir = self._dir / "models"
        self._models_dir.mkdir(exist_ok=True)
        self._registry_path = self._dir / "registry.json"
        self._registry = self._load_registry()

    def _load_registry(self) -> dict:
        if self._registry_path.exists():
            return json.loads(self._registry_path.read_text(encoding="utf-8"))
        return {"version": 1, "factors": {}}

    def _save_registry(self) -> None:
        self._registry_path.write_text(
            json.dumps(self._registry, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def save_factor(
        self,
        name: str,
        expression: str,
        factor_values: pd.DataFrame,
        metrics: dict,
    ) -> None:
        """保存挖掘出的因子。

        Args:
            name: 因子名称。
            expression: 因子表达式描述。
            factor_values: 因子值 DataFrame, index=date, columns=symbol。
            metrics: 评估指标 dict。
        """
        # 保存 parquet
        parquet_name = f"{name}.parquet"
        path = self._mined_dir / parquet_name
        factor_values.to_parquet(path, engine="pyarrow")

        # 更新 registry
        self._registry["factors"][name] = {
            "name": name,
            "expression": expression,
            "category": metrics.get("category", "unknown"),
            "created_at": date.today().isoformat(),
            "metrics": {
                "ic_mean": metrics.get("ic_mean", 0.0),
                "ir": metrics.get("ir", 0.0),
                "sharpe_top_group": metrics.get("sharpe_top_group", 0.0),
                "monotonicity": metrics.get("monotonicity", 0.0),
            },
            "status": "active",
            "inverted": metrics.get("ic_mean", 0) < 0,
            "parquet_path": f"mined/{parquet_name}",
        }
        self._save_registry()

    def load_factor_values(self, name: str) -> pd.DataFrame:
        """加载因子值 parquet。"""
        info = self._registry["factors"].get(name)
        if info is None:
            raise KeyError(f"Factor not found in registry: {name}")
        path = self._dir / info["parquet_path"]
        if not path.exists():
            raise FileNotFoundError(f"Factor parquet not found: {path}")
        return pd.read_parquet(path, engine="pyarrow")

    def list_factors(
        self,
        status: str = "active",
        min_ir: float = 0.0,
    ) -> list[dict]:
        """列出符合条件的因子。"""
        results: list[dict] = []
        for info in self._registry["factors"].values():
            if info.get("status") != status:
                continue
            ir = abs(info.get("metrics", {}).get("ir", 0.0))
            if ir < min_ir:
                continue
            results.append(info)
        return results

    def deactivate_factor(self, name: str, reason: str) -> None:
        """停用因子。"""
        if name not in self._registry["factors"]:
            raise KeyError(f"Factor not found: {name}")
        self._registry["factors"][name]["status"] = "inactive"
        self._registry["factors"][name]["deactivation_reason"] = reason
        self._registry["factors"][name]["deactivated_at"] = date.today().isoformat()
        self._save_registry()

    def to_domain_factor(self, name: str) -> object:
        """将存储的因子转换为 domain MinedFactor 实例。"""
        from src.domain.strategy.factors.mined_factor import MinedFactor

        df = self.load_factor_values(name)
        info = self._registry["factors"][name]

        # 转换为 {date_str: {symbol: value}} 格式
        values_by_date: dict[str, dict[str, float]] = {}
        for dt_idx in df.index:
            dt_str = str(dt_idx)[:10]  # YYYY-MM-DD
            row = df.loc[dt_idx]
            day_vals: dict[str, float] = {}
            for col in df.columns:
                val = row[col]
                if pd.notna(val):
                    day_vals[str(col)] = float(val)
            if day_vals:
                values_by_date[dt_str] = day_vals

        return MinedFactor(
            name=name,
            values_by_date=values_by_date,
            inverted=info.get("inverted", False),
        )
