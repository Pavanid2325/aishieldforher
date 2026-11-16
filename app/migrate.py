"""Explicit, serialized forward-only SQL migrations: python -m app.migrate."""
import hashlib
from pathlib import Path
from app.db import transaction

def main():
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(710002)')
            cur.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, checksum TEXT NOT NULL)')
            for path in sorted(Path(__file__).with_name('migrations').glob('*.sql')):
                sql = path.read_text(encoding='utf-8')
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                cur.execute('SELECT checksum FROM schema_migrations WHERE name=%s', (path.name,))
                row = cur.fetchone()
                if row:
                    if row[0] != checksum:
                        raise RuntimeError('Applied migration changed: ' + path.name)
                    continue
                cur.execute(sql)
                cur.execute('INSERT INTO schema_migrations VALUES (%s,%s)', (path.name,checksum))
                print('Applied ' + path.name)

if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Migration failed; database details redacted') from None
