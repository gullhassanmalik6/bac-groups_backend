from decimal import Decimal

from app.payouts.eligibility import evaluate_payout_eligibility
from app.protocols.execution import decide_protocol_execution


def test_payout_not_eligible_without_settlement():
    result = evaluate_payout_eligibility(
        settlement_confirmed=False,
        provider_configured=True,
        destination_address="TGQbDuBTUw75Uhh5qTuK1NFyQXyTTjDai7",
        amount=Decimal("100.00"),
        currency="USDT",
    )
    assert result.status == "PAYOUT_NOT_ELIGIBLE"
    assert result.destination_masked.startswith("TGQbD")
    assert "••••" in result.destination_masked


def test_payout_not_eligible_without_provider():
    result = evaluate_payout_eligibility(
        settlement_confirmed=True,
        provider_configured=False,
        destination_address="TGQbDuBTUw75Uhh5qTuK1NFyQXyTTjDai7",
    )
    assert result.status == "PAYOUT_NOT_ELIGIBLE"
    assert result.provider_configured is False


def test_payout_pending_when_configured_and_settled():
    result = evaluate_payout_eligibility(
        settlement_confirmed=True,
        provider_configured=True,
        destination_address="TGQbDuBTUw75Uhh5qTuK1NFyQXyTTjDai7",
    )
    assert result.status == "PAYOUT_PENDING"
    assert "Not confirmed on-chain" in result.reason


def test_production_undocumented_protocol_blocked():
    decision = decide_protocol_execution("201.3", environment="production")
    assert decision.allowed is False
    assert decision.status == "PROVIDER_CONFIGURATION_REQUIRED"


def test_sandbox_protocol_may_simulate():
    decision = decide_protocol_execution("201.3", environment="sandbox")
    assert decision.allowed is True
    assert decision.status == "SANDBOX_SIMULATION"
