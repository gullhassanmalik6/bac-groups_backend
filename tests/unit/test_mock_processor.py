from app.processors.mock_processor import MockPaymentProcessor, simulate_terminal_authorize_flow


def test_mock_processor_test_auth_prefix():
    proc = MockPaymentProcessor()
    result = proc.authorize(session_id="s1", amount_minor=1000, currency="CAD")
    assert result.status == "APPROVED"
    assert result.authorization_code.startswith("TEST-")
    assert result.processor_reference.startswith("sbx_")
    assert result.sandbox is True


def test_mock_processor_decline_amount_13():
    proc = MockPaymentProcessor()
    result = proc.authorize(session_id="s1", amount_minor=1013, currency="CAD")
    assert result.status == "DECLINED"


def test_simulate_capture_flow_completes():
    state, result = simulate_terminal_authorize_flow(sandbox_outcome="capture")
    assert state == "COMPLETED"
    assert result.status == "APPROVED"


def test_simulate_pre_auth_stays_approved():
    state, result = simulate_terminal_authorize_flow(sandbox_outcome="pre_auth")
    assert state == "APPROVED"
    assert result.authorization_code.startswith("TEST-")


def test_simulate_declined():
    state, result = simulate_terminal_authorize_flow(scenario="declined")
    assert state == "DECLINED"
