import logging
import pytest

def test_task_error_logs_redact_sensitive_row_details(caplog):
    from app.alerts import RedactTaskErrors
    record=logging.LogRecord('celery.app.trace',logging.ERROR,'',0,'private row %s',('phone/GPS',),None)
    assert RedactTaskErrors().filter(record)
    assert record.getMessage()=='{"event":"task_failed_redacted"}'
    assert record.exc_info is None

def test_production_rejects_fake_and_missing_provider(monkeypatch):
    from app.operations import create_operations_app
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('API_TOKEN','test-api')
    monkeypatch.setenv('DIAGNOSTIC_TOKEN','test-ops')
    monkeypatch.setenv('ALERTS_ENABLED','true')
    with pytest.raises(RuntimeError,match='provider adapter'):
        create_operations_app()
    from app.inference import initialize
    monkeypatch.setenv('ALERTS_ENABLED','false')
    monkeypatch.setenv('FAKE_INFERENCE','true')
    with pytest.raises(RuntimeError,match='Fake inference'):
        initialize(create_operations_app())
