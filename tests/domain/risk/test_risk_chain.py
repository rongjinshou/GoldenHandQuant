from unittest.mock import MagicMock
from src.domain.risk.services.risk_chain import RiskChain
from src.domain.risk.value_objects.risk_check_result import RiskCheckResult


def test_risk_chain_passes_when_all_policies_pass():
    p1 = MagicMock()
    p1.check.return_value = RiskCheckResult.pass_check()
    p2 = MagicMock()
    p2.check.return_value = RiskCheckResult.pass_check()

    chain = RiskChain([p1, p2])
    result = chain.check(MagicMock())
    assert result.passed is True


def test_risk_chain_stops_at_first_rejection():
    p1 = MagicMock()
    p1.check.return_value = RiskCheckResult.reject("blocked by p1")
    p2 = MagicMock()
    p2.check.return_value = RiskCheckResult.pass_check()

    chain = RiskChain([p1, p2])
    result = chain.check(MagicMock())
    assert result.passed is False
    assert "blocked by p1" in result.reason
    p2.check.assert_not_called()


def test_risk_chain_empty_passes():
    chain = RiskChain()
    result = chain.check(MagicMock())
    assert result.passed is True


def test_risk_chain_add_policy():
    chain = RiskChain()
    p1 = MagicMock()
    p1.check.return_value = RiskCheckResult.pass_check()
    chain.add_policy(p1)
    result = chain.check(MagicMock())
    assert result.passed is True
    p1.check.assert_called_once()
