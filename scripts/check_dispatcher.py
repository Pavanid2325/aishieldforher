from db import transaction
with transaction() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT checked_at > now()-interval '30 seconds' FROM operational_checks WHERE name='dispatcher'")
        row = cur.fetchone()
        if not row or not row[0]:
            raise SystemExit(1)
