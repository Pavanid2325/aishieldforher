-- Bound re-publication while a worker is busy; lost broker messages recover after this lease.
ALTER TABLE alert_outbox ADD COLUMN IF NOT EXISTS dispatch_after TIMESTAMPTZ NOT NULL DEFAULT now();
