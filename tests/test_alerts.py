import threading
from concurrent.futures import ThreadPoolExecutor
import pytest

def create_alert(database):
    from db import insert_incident
    with database() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO contacts(name,phone,level) VALUES ('Test','fake-only',1)")
    return insert_incident(1,.3,'LEVEL_3','test','unknown','test.wav',0,0,'test','correlation-test')

def status(database):
    with database() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT status,attempts FROM alert_outbox ORDER BY id LIMIT 1')
            return cur.fetchone()

def due(database):
    with database() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE alert_outbox SET available_at=now()-interval '1 second'")

def test_atomic_rollback(database,monkeypatch):
    from db import insert_incident
    # Deliberately break the outbox insert: incident and cooldown must roll back too.
    with database() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO contacts(name,phone,level) VALUES ('Test',NULL,1)")
    with pytest.raises(Exception):
        insert_incident(1,.3,'LEVEL_3','test','unknown','test.wav',0,0,'test')
    with database() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM incidents')
            assert cur.fetchone()[0] == 0

def test_broker_failure_recovery_and_duplicate_execution(database,monkeypatch):
    import alerts
    incident=create_alert(database)
    def fail(*args,**kwargs):
        raise ConnectionError('broker offline')
    monkeypatch.setattr(alerts.deliver,'apply_async',fail)
    with pytest.raises(ConnectionError):
        alerts.dispatch_once()
    assert status(database) == ('pending',0)
    sent=[]
    monkeypatch.setattr(alerts.deliver,'apply_async',lambda args:sent.append(args[0]))
    alerts.dispatch_once()
    alerts.deliver(sent[0])
    alerts.deliver(sent[0])
    assert status(database) == ('delivered',1)

def test_bounded_retry_and_terminal_failure(database,monkeypatch):
    import alerts
    create_alert(database)
    monkeypatch.setenv('FAKE_ALERT_FAIL','true')
    for attempt in range(1,6):
        due(database)
        alerts.deliver(1)
        assert status(database) == ('failed' if attempt==5 else 'retry',attempt)
    alerts.deliver(1)
    assert status(database) == ('failed',5)
    with database() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM alert_attempts')
            assert cur.fetchone()[0] == 5

def test_bounded_publication_and_lost_queue_recovery(database,monkeypatch):
    import alerts
    create_alert(database)
    sent=[]
    monkeypatch.setattr(alerts.deliver,'apply_async',lambda args:sent.append(args[0]))
    alerts.dispatch_once()
    alerts.dispatch_once()
    assert sent==[1]
    with database() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE alert_outbox SET dispatch_after=now()-interval '1 second'")
    alerts.dispatch_once()
    assert sent==[1,1]

def test_concurrent_tasks_only_one_provider_call(database,monkeypatch):
    import alerts
    create_alert(database)
    entered,release=threading.Event(),threading.Event()
    calls=[]
    def send(recipient,key):
        calls.append(key)
        entered.set()
        assert release.wait(5)
    monkeypatch.setattr(alerts,'provider_send',send)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first=executor.submit(alerts.deliver.run,1)
        assert entered.wait(5)
        second=executor.submit(alerts.deliver.run,1)
        second.result(timeout=5)
        release.set()
        first.result(timeout=5)
    assert len(calls)==1
    assert status(database)==('delivered',1)

def test_worker_crash_recovery_and_retry_budget(database):
    import alerts
    create_alert(database)
    with database() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE alert_outbox SET status='processing',attempts=1,available_at=now()-interval '1 second'")
            cur.execute("INSERT INTO alert_attempts(alert_id,attempt,outcome) VALUES(1,1,'started')")
    alerts.deliver(1)
    assert status(database)==('delivered',2)
    with database() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT outcome FROM alert_attempts ORDER BY attempt')
            assert cur.fetchall()==[('interrupted',),('delivered',)]

def test_shared_cooldown(database):
    from db import insert_incident
    first=create_alert(database)
    assert first
    assert insert_incident(1,.3,'LEVEL_3','test','unknown','test.wav',0,0,'test') is None

def test_no_delivery_before_backoff_expires(database,monkeypatch):
    import alerts
    create_alert(database)
    monkeypatch.setenv('FAKE_ALERT_FAIL','true')
    alerts.deliver(1)
    alerts.deliver(1)
    assert status(database)==('retry',1)

def test_last_interrupted_attempt_becomes_terminal(database):
    import alerts
    create_alert(database)
    with database() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE alert_outbox SET status='processing',attempts=5,available_at=now()-interval '1 second'")
            cur.execute("INSERT INTO alert_attempts(alert_id,attempt,outcome) VALUES(1,5,'started')")
    alerts.deliver(1)
    assert status(database)==('failed',5)

def test_real_broker_probe(database):
    import os
    if os.getenv('RUN_REDIS') != 'true':
        pytest.skip('Set RUN_REDIS=true to exercise a live Redis broker')
    from celery.contrib.testing.worker import start_worker
    from alerts import celery,probe,dispatch_once
    import time
    create_alert(database)
    with start_worker(celery,perform_ping_check=False,pool='solo'):
        dispatch_once()
        probe.apply_async(args=['integration-probe'])
        for _ in range(30):
            with database() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM operational_checks WHERE name='integration-probe'")
                    if cur.fetchone():
                        assert status(database)==('delivered',1)
                        return
            time.sleep(.2)
        pytest.fail('Redis worker did not execute probe')
