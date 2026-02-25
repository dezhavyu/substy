CREATE SCHEMA IF NOT EXISTS notifications;

CREATE TABLE IF NOT EXISTS notifications.notifications (
    id UUID PRIMARY KEY,
    topic_id UUID NOT NULL,
    payload JSONB NOT NULL,
    scheduled_at TIMESTAMPTZ NULL,
    status TEXT NOT NULL,
    created_by UUID NOT NULL,
    idempotency_key TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT notifications_status_check CHECK (status IN ('created', 'processing', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_notifications_created_by_created_at
    ON notifications.notifications (created_by, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_topic_created_at
    ON notifications.notifications (topic_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_status_scheduled_at
    ON notifications.notifications (status, scheduled_at);

CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_idempotency
    ON notifications.notifications (created_by, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS notifications.outbox_events (
    id UUID PRIMARY KEY,
    aggregate_type TEXT NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    headers JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ NULL,
    publish_attempts INT NOT NULL DEFAULT 0,
    last_error TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_outbox_published_at
    ON notifications.outbox_events (published_at);

CREATE INDEX IF NOT EXISTS idx_outbox_created_at
    ON notifications.outbox_events (created_at);

CREATE INDEX IF NOT EXISTS idx_outbox_event_type
    ON notifications.outbox_events (event_type);
