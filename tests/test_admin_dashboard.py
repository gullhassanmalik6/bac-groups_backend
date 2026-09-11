"""Unit tests for admin dashboard status bucketing helpers."""

from app.services.admin_dashboard_service import _bucket, _minor_to_major


def test_bucket_terminal_and_legacy_statuses():
    assert _bucket("COMPLETED") == "approved"
    assert _bucket("APPROVED") == "approved"
    assert _bucket("success") == "approved"
    assert _bucket("DECLINED") == "declined"
    assert _bucket("failed") == "declined"
    assert _bucket("REFUNDED") == "refunded"
    assert _bucket("VOIDED") == "voided"
    assert _bucket("CANCELLED") == "voided"
    assert _bucket("pending") == "pending"
    assert _bucket("AUTHORIZING") == "pending"


def test_minor_to_major():
    assert _minor_to_major(4850, "CAD") == 48.5
    assert _minor_to_major(1000) == 10.0
