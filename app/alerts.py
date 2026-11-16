"""PostgreSQL owns retry state. Redis is a disposable delivery accelerator."""
import logging
import os
import time
from celery import Celery, Task
from app.db import transaction, connect

log = logging.getLogger('shield')
log.setLevel(logging.INFO)
MAX_ATTEMPTS = 5

class RedactTaskErrors(logging.Filter):
    def filter(self, record):
        if record.levelno >= logging.ERROR:
            # Database exceptions can contain row values; do not emit their tracebacks.
            record.msg = '{"event":"task_failed_redacted"}'
            record.args = ()
            record.exc_info = None
            record.exc_text = None
        return True

logging.getLogger('celery.app.trace').addFilter(RedactTaskErrors())

class FlaskTask(Task):
    def __call__(self, *args, **kwargs):
        # Worker imports only lightweight Flask initialization, never audio models.
        from app.operations import create_operations_app
        if not hasattr(self, '_flask_app'):
            self._flask_app = create_operations_app()
        with self._flask_app.app_context():
            return self.run(*args, **kwargs)

celery = Celery('shield', task_cls=FlaskTask, broker=os.getenv('REDIS_URL', 'redis://redis:6379/0'))
celery.conf.update(task_serializer='json', accept_content=['json'], result_serializer='json',
    task_ignore_result=True, task_acks_late=True, task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, task_soft_time_limit=25, task_time_limit=30,
    broker_connection_retry_on_startup=True, broker_connection_timeout=2,
    broker_transport_options={'visibility_timeout': 120, 'socket_connect_timeout': 2, 'socket_timeout': 2},
    task_publish_retry=False, worker_hijack_root_logger=False,
    worker_log_format='%(message)s', worker_task_log_format='%(message)s')

def provider_send(recipient, key):
    """No real provider was present. Fake must be explicit; unsupported providers fail closed."""
    provider = os.getenv('ALERT_PROVIDER', 'fake')
    if provider == 'fake' and os.getenv('APP_ENV') != 'production':
        if os.getenv('FAKE_ALERT_FAIL', 'false') == 'true':
            raise RuntimeError('fake provider failure')
        return
    raise RuntimeError('No production alert provider configured')

def event(name, **fields):
    import json
    log.info(json.dumps({'event':name, 'release':os.getenv('RELEASE_ID','development'), **fields}))

@celery.task(name='shield.deliver')
def deliver(alert_id):
    conn = connect()
    locked = False
    try:
        with conn.cursor() as cur:
            # Session lock spans committed attempt history and provider I/O.
            cur.execute('SELECT pg_try_advisory_lock(720001, %s)', (alert_id,))
            locked = cur.fetchone()[0]
            if not locked:
                return
            cur.execute('''SELECT recipient,idempotency_key,status,attempts,correlation_id,
                available_at <= now() FROM alert_outbox WHERE id=%s''', (alert_id,))
            row = cur.fetchone()
            if not row or row[2] in ('delivered','failed') or not row[5]:
                return
            recipient, key, status, attempts, correlation, _ = row
            if attempts >= MAX_ATTEMPTS:
                cur.execute("UPDATE alert_outbox SET status='failed' WHERE id=%s", (alert_id,))
                cur.execute("UPDATE alert_attempts SET outcome='interrupted',finished_at=now() WHERE alert_id=%s AND outcome='started'", (alert_id,))
                conn.commit()
                event('alert_terminal', alert_id=alert_id, correlation_id=correlation)
                return
            cur.execute("UPDATE alert_attempts SET outcome='interrupted',finished_at=now() WHERE alert_id=%s AND outcome='started'", (alert_id,))
            attempt = attempts + 1
            cur.execute("UPDATE alert_outbox SET status='processing',attempts=%s,available_at=now()+interval '90 seconds' WHERE id=%s", (attempt,alert_id))
            cur.execute("INSERT INTO alert_attempts(alert_id,attempt,outcome) VALUES (%s,%s,'started')", (alert_id,attempt))
            conn.commit()
            try:
                provider_send(recipient, key)
            except Exception:
                terminal = attempt >= MAX_ATTEMPTS
                cur.execute("UPDATE alert_outbox SET status=%s,available_at=now()+(%s * interval '1 second'),dispatch_after=now() WHERE id=%s",
                            ('failed' if terminal else 'retry',min(300,2 ** attempt),alert_id))
                outcome = 'failed'
                event('alert_failed' if terminal else 'alert_retry', alert_id=alert_id, attempt=attempt, correlation_id=correlation)
            else:
                cur.execute("UPDATE alert_outbox SET status='delivered',delivered_at=now() WHERE id=%s", (alert_id,))
                outcome = 'delivered'
                event('alert_delivered', alert_id=alert_id, attempt=attempt, correlation_id=correlation)
            cur.execute('UPDATE alert_attempts SET outcome=%s,finished_at=now() WHERE alert_id=%s AND attempt=%s', (outcome,alert_id,attempt))
            conn.commit()
    finally:
        conn.rollback()
        if locked:
            with conn.cursor() as cur:
                cur.execute('SELECT pg_advisory_unlock(720001, %s)', (alert_id,))
            conn.commit()
        conn.close()

@celery.task(name='shield.probe')
def probe(name):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO operational_checks(name) VALUES (%s)
                ON CONFLICT(name) DO UPDATE SET checked_at=now()''', (name,))

def dispatch_once():
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,attempts FROM alert_outbox WHERE status IN ('pending','retry','processing') AND available_at<=now() AND dispatch_after<=now() ORDER BY dispatch_after,id LIMIT 100")
            rows = cur.fetchall()
    # Never mark published as delivered; repeated dispatch recovers lost broker messages.
    for alert_id, attempts in rows:
        deliver.apply_async(args=[alert_id])
        with transaction() as conn:
            with conn.cursor() as cur:
                # Do not postpone a retry whose worker already started a new attempt.
                cur.execute("UPDATE alert_outbox SET dispatch_after=now()+interval '30 seconds' WHERE id=%s AND attempts=%s", (alert_id,attempts))
    probe('dispatcher')
    event('dispatch_completed', pending=len(rows))

def run_dispatcher():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    while True:
        try:
            dispatch_once()
        except Exception:
            event('dispatch_unavailable')
        time.sleep(5)

if __name__ == '__main__':
    run_dispatcher()
