-- Additive bootstrap based on the existing queries. Never drop existing tables.
CREATE TABLE IF NOT EXISTS contacts (
 id BIGSERIAL PRIMARY KEY, name TEXT, phone TEXT, level INTEGER
);
CREATE TABLE IF NOT EXISTS incidents (
 id BIGSERIAL PRIMARY KEY, user_id INTEGER, timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
 threat_score DOUBLE PRECISION, threat_level TEXT, speech_text TEXT, emotion TEXT,
 audio_path TEXT, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, status TEXT, hash TEXT
);
CREATE TABLE IF NOT EXISTS incident_gate (
 id INTEGER PRIMARY KEY CHECK(id=1), last_saved TIMESTAMPTZ NOT NULL DEFAULT '-infinity'
);
INSERT INTO incident_gate(id) VALUES (1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS alert_outbox (
 id BIGSERIAL PRIMARY KEY, incident_id BIGINT REFERENCES incidents(id) ON DELETE CASCADE,
 recipient TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE, correlation_id TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','retry','delivered','failed')),
 attempts INTEGER NOT NULL DEFAULT 0, available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS outbox_due ON alert_outbox(available_at) WHERE status IN ('pending','processing','retry');
CREATE TABLE IF NOT EXISTS alert_attempts (
 id BIGSERIAL PRIMARY KEY, alert_id BIGINT REFERENCES alert_outbox(id) ON DELETE CASCADE,
 attempt INTEGER NOT NULL, outcome TEXT NOT NULL, started_at TIMESTAMPTZ DEFAULT now(),
 finished_at TIMESTAMPTZ, UNIQUE(alert_id,attempt)
);
CREATE TABLE IF NOT EXISTS operational_checks (
 name TEXT PRIMARY KEY, checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
