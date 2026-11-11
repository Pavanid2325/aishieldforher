from contextlib import contextmanager
import pytest

def test_existing_home_iot_and_audio(client):
    assert client.get('/').data == b'Server Running'
    assert client.post('/iot_data',json={'accel':12}).json == {'accel':12.0,'iot_score':0.7,'level':'LEVEL_3'}
    assert client.post('/stream_audio',data=b'').status_code == 400
    result = client.post('/stream_audio?latitude=1&longitude=2&accel=10',data=b'\0\0'*160).json
    assert result['threat_score'] == 0.083875
    assert result['level'] == 'LEVEL_3'
    assert result['text'] == 'test transcript'
    assert result['alert_status'] == 'not_requested'

@pytest.mark.parametrize('score,level', [(0,'IDLE'),(.005,'LEVEL_1'),(.02,'LEVEL_2'),(.05,'LEVEL_3')])
def test_unchanged_thresholds(score,level):
    from server import get_threat_level
    assert get_threat_level(score) == level

def test_auth_and_diagnostics(client,monkeypatch):
    monkeypatch.setenv('API_TOKEN','test-api')
    monkeypatch.setenv('DIAGNOSTIC_TOKEN','test-ops')
    assert client.get('/get_contacts').status_code == 401
    assert client.get('/health/live').status_code == 200
    assert client.get('/ops/instance').status_code == 401
    assert client.get('/ops/instance',headers={'Authorization':'Bearer test-api'}).status_code == 401
    assert client.get('/ops/instance',headers={'Authorization':'Bearer test-ops'}).status_code == 200
    assert client.get('/',headers={'Authorization':'Bearer test-api'}).status_code == 200

def test_ready_failure_is_redacted(client,monkeypatch):
    import operations
    @contextmanager
    def unavailable():
        raise RuntimeError('secret password')
        yield
    monkeypatch.setattr(operations,'transaction',unavailable)
    assert client.get('/health/live').status_code == 200
    response=client.get('/health/ready')
    assert response.status_code == 503
    assert response.json == {'status':'unready'}

def test_correlation_and_upload_limit(client):
    assert client.get('/',headers={'X-Request-ID':'safe-id'}).headers['X-Request-ID'] == 'safe-id'
    assert client.post('/stream_audio',data=b'x'*(10*1024*1024+1)).status_code == 413

def test_production_configuration_fails_closed(monkeypatch):
    from operations import create_operations_app
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.delenv('API_TOKEN',raising=False)
    with pytest.raises(RuntimeError):
        create_operations_app()

def test_contacts_incidents_and_pending_contract(client,database,monkeypatch):
    from db import insert_incident
    assert client.post('/add_contact',json={'name':'Test','phone':'fake-number','level':1}).json == {'message':'added'}
    contacts=client.get('/get_contacts').json
    contact_id=contacts[0]['id']
    assert client.get('/get_contacts_by_level/2').json == ['fake-number']
    assert client.put(f'/update_contact/{contact_id}',json={'name':'Updated','phone':'fake-number','level':2}).json == {'message':'updated'}
    monkeypatch.setattr('server.process_audio_file',lambda *args:(.3,'distress'))
    result=client.post('/stream_audio',data=b'\0\0'*16).json
    assert result['incident_id']
    assert result['alert_status'] == 'pending'
    assert client.get('/alerts/'+str(result['incident_id'])).json == {'pending':1}
    incidents=client.get('/get_incidents').json
    assert incidents[0]['threat_score'] == .3
    assert incidents[0]['threat_level'] == 'LEVEL_3'
    assert client.delete(f'/delete_contact/{contact_id}').json == {'message':'deleted'}
    assert client.delete('/delete_incident/'+str(result['incident_id'])).status_code == 200

def test_ready_ignores_redis_with_durable_outbox(client,database,monkeypatch):
    monkeypatch.setenv('REDIS_URL','redis://127.0.0.1:1/0')
    assert client.get('/health/ready').json == {'status':'ready'}
