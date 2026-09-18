"""Fee engine unit tests — screenshot example 0.5% of 1,000,000.00."""

from decimal import Decimal

from app.fees.engine import calculate_fee


def test_half_percent_of_one_million():
    result = calculate_fee(
        Decimal("1000000.00"),
        "USD",
        Decimal("0.5"),
        policy_version="screenshot-example-v1",
    )
    assert result.fee_amount == Decimal("5000.00")
    assert result.net_amount == Decimal("995000.00")
    assert result.currency == "USD"
    assert result.policy_version == "screenshot-example-v1"


def test_rounding_half_up():
    result = calculate_fee(Decimal("10.01"), "USD", Decimal("0.5"))
    assert result.fee_amount == Decimal("0.05")
    assert result.net_amount == Decimal("9.96")


def test_rejects_negative_gross():
    try:
        calculate_fee(Decimal("-1"), "USD", Decimal("0.5"))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
