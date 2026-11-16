import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['APP_ENV'] = 'test'
os.environ['FAKE_INFERENCE'] = 'true'
# Do not load the developer's .env during tests.
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ.setdefault('ALERT_PROVIDER','fake')
import pytest

@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv('API_TOKEN', raising=False)
    monkeypatch.setenv('UPLOAD_FOLDER',str(tmp_path))
    from app import server
    server.UPLOAD_FOLDER = str(tmp_path)
    server.app.config['TESTING'] = True
    return server.app.test_client()

@pytest.fixture
def database(monkeypatch):
    if os.getenv('RUN_INTEGRATION') != 'true':
        pytest.skip('Set RUN_INTEGRATION=true with an isolated DATABASE_URL')
    from app import migrate
    from app.db import transaction
    migrate.main()
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute('TRUNCATE contacts, incidents, alert_outbox, alert_attempts, operational_checks RESTART IDENTITY CASCADE')
            cur.execute("UPDATE incident_gate SET last_saved='-infinity'")
    monkeypatch.setenv('ALERTS_ENABLED','true')
    monkeypatch.setenv('ALERT_PROVIDER','fake')
    monkeypatch.delenv('FAKE_ALERT_FAIL',raising=False)
    return transaction
