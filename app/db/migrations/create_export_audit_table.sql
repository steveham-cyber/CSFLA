CREATE TABLE IF NOT EXISTS export_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exported_by TEXT NOT NULL,
    exported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    format TEXT NOT NULL CHECK (format IN ('csv', 'json', 'ndjson')),
    row_count INTEGER NOT NULL,
    suppressed_count INTEGER NOT NULL DEFAULT 0,
    client_ip TEXT,
    outcome TEXT NOT NULL CHECK (outcome IN ('success', 'failure')),
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_export_audit_exported_by ON export_audit (exported_by);
