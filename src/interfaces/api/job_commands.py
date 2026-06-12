"""Web 任务请求 → CLI argv 翻译层（白名单, 无 shell）。

每种任务类型 = 一个 Pydantic 请求模型 + 一个纯函数构建器。
校验借 domain 注册表/因子目录把关, 解析失败 → 422。
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
CONFIG_WHITELIST = (
    "resources/backtest.yaml",
    "resources/backtest_multi_factor.yaml",
)
_QUANT = [sys.executable, "-m", "src.interfaces.cli.quant"]

_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
_SYMBOL_RE = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")
_PARAM_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PARAM_STR_VALUE_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _check_date_range(start: str, end: str) -> None:
    """两端日历有效性 + start <= end；违例抛 ValueError。"""
    fmt = "%Y-%m-%d"
    try:
        s = datetime.strptime(start, fmt)
    except ValueError:
        raise ValueError(f"无效日期: {start}") from None
    try:
        e = datetime.strptime(end, fmt)
    except ValueError:
        raise ValueError(f"无效日期: {end}") from None
    if s > e:
        raise ValueError(f"start_date ({start}) 不得晚于 end_date ({end})")


class BacktestJobRequest(BaseModel):
    strategies: list[str] = Field(min_length=1)
    start_date: str = Field(pattern=DATE_PATTERN)
    end_date: str = Field(pattern=DATE_PATTERN)
    symbols: list[str] | None = None
    params: dict[str, dict[str, float | int | str]] | None = None
    config: str | None = None
    initial_capital: float | None = Field(default=None, gt=0)

    @field_validator("strategies")
    @classmethod
    def _known_strategies(cls, v: list[str]) -> list[str]:
        from src.domain.strategy.registry import get_strategy

        for name in v:
            try:
                get_strategy(name)
            except KeyError:
                raise ValueError(f"未知策略: {name}") from None
        return v

    @field_validator("config")
    @classmethod
    def _config_in_whitelist(cls, v: str | None) -> str | None:
        if v is not None and v not in CONFIG_WHITELIST:
            raise ValueError(f"config 仅允许: {CONFIG_WHITELIST}")
        return v

    @model_validator(mode="after")
    def _validate_symbols_and_params_and_dates(self) -> BacktestJobRequest:
        # 日期语义
        _check_date_range(self.start_date, self.end_date)

        # symbols 逐项正则
        if self.symbols is not None:
            for sym in self.symbols:
                if not _SYMBOL_RE.match(sym):
                    raise ValueError(
                        f"symbols 格式错误: {sym!r}，须匹配 NNNNNN.(SH|SZ|BJ)"
                    )

        # params 注入收口
        if self.params is not None:
            strategy_set = set(self.strategies)
            for strat_key, kv in self.params.items():
                if strat_key not in strategy_set:
                    raise ValueError(f"params 引用未选策略: {strat_key}")
                for param_name, param_val in kv.items():
                    if not _PARAM_NAME_RE.match(param_name):
                        raise ValueError(
                            f"参数名格式错误: {param_name!r}，须匹配 ^[A-Za-z_][A-Za-z0-9_]*$"
                        )
                    if isinstance(param_val, str):
                        if not _PARAM_STR_VALUE_RE.match(param_val):
                            raise ValueError(
                                f"参数值含非法字符: {param_val!r}（禁 ,/=/空串）"
                            )
        return self


class FactorTestJobRequest(BaseModel):
    factors: str = Field(min_length=1)
    start_date: str = Field(default="2021-01-01", pattern=DATE_PATTERN)
    end_date: str = Field(default="2025-12-31", pattern=DATE_PATTERN)
    split_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    objective: Literal["long_short", "long_only"] = "long_short"
    num_layers: int = Field(default=5, ge=2, le=10)
    rebalance_days: int = Field(default=1, ge=1, le=60)
    cost_rate: float = Field(default=0.003, ge=0, le=0.05)

    @field_validator("factors")
    @classmethod
    def _resolvable(cls, v: str) -> str:
        from src.domain.strategy.factor_test.factor_catalog import resolve_factors

        resolve_factors(v)  # ValueError 自然冒泡 → 422
        return v

    @model_validator(mode="after")
    def _validate_dates(self) -> FactorTestJobRequest:
        _check_date_range(self.start_date, self.end_date)
        if self.split_date is not None:
            # 校验 split_date 为合法日历日
            try:
                datetime.strptime(self.split_date, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"split_date 非合法日历日: {self.split_date}") from None
        return self


class DataRefreshJobRequest(BaseModel):
    start_date: str = Field(pattern=DATE_PATTERN)
    end_date: str = Field(pattern=DATE_PATTERN)

    @model_validator(mode="after")
    def _validate_dates(self) -> DataRefreshJobRequest:
        _check_date_range(self.start_date, self.end_date)
        return self


class MlTrainJobRequest(BaseModel):
    start_date: str = Field(pattern=DATE_PATTERN)
    end_date: str = Field(pattern=DATE_PATTERN)
    symbols: str = "000300.SH"
    model_name: str = Field(default="lgbm_return_5d", pattern=r"^[A-Za-z0-9_\-]{1,64}$")
    label_horizon: int = Field(default=5, ge=1, le=20)
    n_trials: int = Field(default=50, ge=1, le=200)

    @field_validator("symbols")
    @classmethod
    def _validate_symbols(cls, v: str) -> str:
        for seg in v.split(","):
            seg = seg.strip()
            if not _SYMBOL_RE.match(seg):
                raise ValueError(
                    f"symbols 格式错误: {seg!r}，须匹配 NNNNNN.(SH|SZ|BJ)"
                )
        return v

    @model_validator(mode="after")
    def _validate_dates(self) -> MlTrainJobRequest:
        _check_date_range(self.start_date, self.end_date)
        return self


class MlEvaluateJobRequest(BaseModel):
    model_name: str = Field(pattern=r"^[A-Za-z0-9_\-]{1,64}$")
    eval_start: str = Field(pattern=DATE_PATTERN)
    eval_end: str = Field(pattern=DATE_PATTERN)

    @model_validator(mode="after")
    def _validate_dates(self) -> MlEvaluateJobRequest:
        _check_date_range(self.eval_start, self.eval_end)
        return self


def build_backtest_argv(req: BacktestJobRequest) -> list[str]:
    argv = [sys.executable, "-m", "src.interfaces.cli.compare_strategies",
            "--strategies", ",".join(req.strategies),
            "--start-date", req.start_date, "--end-date", req.end_date]
    if req.symbols:
        argv += ["--symbols", ",".join(req.symbols)]
    if req.params:
        pairs = [f"{strat}.{key}={value}"
                 for strat, kv in req.params.items() for key, value in kv.items()]
        argv += ["--params", ",".join(pairs)]
    if req.config:
        argv += ["--config", req.config]
    if req.initial_capital:
        argv += ["--initial-capital", str(float(req.initial_capital))]
    return argv


def build_factor_test_argv(req: FactorTestJobRequest) -> list[str]:
    argv = [*_QUANT, "factor-test",
            "--factors", req.factors,
            "--start-date", req.start_date, "--end-date", req.end_date,
            "--objective", req.objective,
            "--num-layers", str(req.num_layers),
            "--rebalance-days", str(req.rebalance_days),
            "--cost-rate", str(req.cost_rate)]
    if req.split_date:
        argv += ["--split-date", req.split_date]
    return argv


def build_data_refresh_argv(req: DataRefreshJobRequest) -> list[str]:
    return [*_QUANT, "data", "refresh",
            "--start-date", req.start_date, "--end-date", req.end_date]


def build_ml_train_argv(req: MlTrainJobRequest) -> list[str]:
    return [*_QUANT, "ml-train",
            "--symbols", req.symbols,
            "--start-date", req.start_date, "--end-date", req.end_date,
            "--label-horizon", str(req.label_horizon),
            "--model-name", req.model_name,
            "--n-trials", str(req.n_trials)]


def build_ml_evaluate_argv(req: MlEvaluateJobRequest) -> list[str]:
    return [*_QUANT, "ml-evaluate",
            "--model-name", req.model_name,
            "--eval-start", req.eval_start, "--eval-end", req.eval_end]
