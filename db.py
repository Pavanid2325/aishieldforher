"""Bounded per-process PostgreSQL pool. No connections during import."""
import os
from contextlib import contextmanager
from threading import Lock
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extensions import make_dsn

_pool = None
_pid = None
_lock = Lock()

def pool():
    global _pool, _pid
    with _lock:
        if _pool is None or _pid != os.getpid():
            kwargs = dict(connect_timeout=3, options='-c statement_timeout=5000 -c lock_timeout=2000')
            if os.getenv('APP_ENV') == 'production':
                kwargs.update(sslmode='verify-full', sslrootcert=os.environ['RDS_CA_PATH'])
            dsn = os.getenv('DATABASE_URL')
            if not dsn:
                # Preserve the existing developer DB_* configuration without hard-coded credentials.
                legacy = {key:os.environ[env] for key,env in (
                    ('dbname','DB_NAME'),('user','DB_USER'),('password','DB_PASSWORD'),
                    ('host','DB_HOST'),('port','DB_PORT')) if env in os.environ}
                if not legacy:
                    raise RuntimeError('DATABASE_URL is required')
                dsn = make_dsn(**legacy)
            _pool = ThreadedConnectionPool(1, int(os.getenv('DB_POOL_SIZE', '2')), dsn, **kwargs)
            _pid = os.getpid()
        return _pool

class Connection:
    def __init__(self):
        self.pool = pool()
        for attempt in range(2):
            self.raw = self.pool.getconn()
            try:
                with self.raw.cursor() as cur:
                    cur.execute('SELECT 1')
                self.raw.rollback()
                break
            except Exception:
                self.pool.putconn(self.raw, close=True)
                if attempt == 1:
                    raise
    def cursor(self, *args, **kwargs):
        return self.raw.cursor(*args, **kwargs)
    def commit(self):
        self.raw.commit()
    def rollback(self):
        self.raw.rollback()
    def close(self):
        if self.raw is not None:
            try:
                self.raw.rollback()
            finally:
                self.pool.putconn(self.raw, close=self.raw.closed != 0)
                self.raw = None

def connect(**ignored):
    conn = Connection()
    from flask import has_request_context, g
    if has_request_context():
        if 'db_connections' not in g:
            g.db_connections = []
        g.db_connections.append(conn)
    return conn

@contextmanager
def transaction():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def insert_incident(user_id, threat_score, level, text, emotion, audio_path, lat, lon, hash,
                    correlation_id='system'):
    """Commit incident, alert intent and shared cooldown in one transaction."""
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(710001)')
            cur.execute("SELECT last_saved < now() - interval '15 seconds' FROM incident_gate WHERE id=1")
            if not cur.fetchone()[0]:
                return None
            cur.execute('''INSERT INTO incidents
                (user_id,threat_score,threat_level,speech_text,emotion,audio_path,latitude,longitude,status,hash)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE',%s) RETURNING id''',
                (user_id,threat_score,level,text,emotion,audio_path,lat,lon,hash))
            incident_id = cur.fetchone()[0]
            if os.getenv('ALERTS_ENABLED', 'false').lower() == 'true':
                numeric_level = int(level[-1]) if level != 'IDLE' else 0
                cur.execute('SELECT id, phone FROM contacts WHERE level <= %s', (numeric_level,))
                for contact_id, phone in cur.fetchall():
                    cur.execute('''INSERT INTO alert_outbox
                        (incident_id,recipient,idempotency_key,correlation_id)
                        VALUES (%s,%s,%s,%s)''',
                        (incident_id,phone,f'incident-{incident_id}-contact-{contact_id}',correlation_id))
            cur.execute('UPDATE incident_gate SET last_saved=now() WHERE id=1')
    return incident_id
