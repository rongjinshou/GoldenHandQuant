"""FactorRepository 单元测试。"""


import numpy as np
import pandas as pd
import pytest

from src.infrastructure.ml_engine.factor_repository import FactorRepository


@pytest.fixture
def tmp_repo(tmp_path):
    return FactorRepository(data_dir=str(tmp_path / "factors"))


@pytest.fixture
def sample_factor_values():
    dates = pd.date_range("2023-01-01", periods=10, freq="B")
    symbols = ["000001", "000002", "000003"]
    data = np.random.default_rng(42).standard_normal((10, 3))
    return pd.DataFrame(data, index=dates, columns=symbols)


class TestFactorRepository:
    def test_save_and_load_roundtrip(self, tmp_repo, sample_factor_values):
        metrics = {"ic_mean": 0.05, "ir": 1.2, "sharpe_top_group": 1.5, "monotonicity": 0.85}
        tmp_repo.save_factor("test_factor", "return_5d / pe_ratio", sample_factor_values, metrics)

        loaded = tmp_repo.load_factor_values("test_factor")
        assert loaded.shape == sample_factor_values.shape
        pd.testing.assert_frame_equal(loaded, sample_factor_values, check_freq=False)

    def test_registry_updated_on_save(self, tmp_repo, sample_factor_values):
        metrics = {"ic_mean": 0.05, "ir": 1.2}
        tmp_repo.save_factor("f1", "expr1", sample_factor_values, metrics)

        factors = tmp_repo.list_factors()
        assert len(factors) == 1
        assert factors[0]["name"] == "f1"
        assert factors[0]["expression"] == "expr1"
        assert factors[0]["status"] == "active"
        assert factors[0]["inverted"] is False

    def test_list_factors_filters_by_status(self, tmp_repo, sample_factor_values):
        tmp_repo.save_factor("f1", "expr1", sample_factor_values, {"ic_mean": 0.05, "ir": 1.0})
        tmp_repo.save_factor("f2", "expr2", sample_factor_values, {"ic_mean": -0.05, "ir": 0.8})

        active = tmp_repo.list_factors(status="active")
        assert len(active) == 2

        tmp_repo.deactivate_factor("f1", "decay")
        active = tmp_repo.list_factors(status="active")
        assert len(active) == 1
        assert active[0]["name"] == "f2"

    def test_list_factors_filters_by_ir(self, tmp_repo, sample_factor_values):
        tmp_repo.save_factor("f1", "expr1", sample_factor_values, {"ic_mean": 0.05, "ir": 1.2})
        tmp_repo.save_factor("f2", "expr2", sample_factor_values, {"ic_mean": 0.03, "ir": 0.3})

        high_ir = tmp_repo.list_factors(min_ir=0.5)
        assert len(high_ir) == 1
        assert high_ir[0]["name"] == "f1"

    def test_deactivate_factor(self, tmp_repo, sample_factor_values):
        tmp_repo.save_factor("f1", "expr1", sample_factor_values, {"ic_mean": 0.05})
        tmp_repo.deactivate_factor("f1", "IC decayed")

        factors = tmp_repo.list_factors(status="inactive")
        assert len(factors) == 1
        assert factors[0]["deactivation_reason"] == "IC decayed"

    def test_deactivate_nonexistent_raises(self, tmp_repo):
        with pytest.raises(KeyError):
            tmp_repo.deactivate_factor("nonexistent", "reason")

    def test_load_nonexistent_raises(self, tmp_repo):
        with pytest.raises(KeyError):
            tmp_repo.load_factor_values("nonexistent")

    def test_inverted_flag_for_negative_ic(self, tmp_repo, sample_factor_values):
        tmp_repo.save_factor("neg_ic", "expr", sample_factor_values, {"ic_mean": -0.05})
        factors = tmp_repo.list_factors()
        assert factors[0]["inverted"] is True

    def test_to_domain_factor(self, tmp_repo, sample_factor_values):
        tmp_repo.save_factor("f1", "expr1", sample_factor_values, {"ic_mean": 0.05})
        factor = tmp_repo.to_domain_factor("f1")
        assert factor.name == "f1"
        # 应该满足 Factor Protocol
        assert hasattr(factor, "compute")
