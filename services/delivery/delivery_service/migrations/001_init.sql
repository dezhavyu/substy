CREATE SCHEMA IF NOT EXISTS delivery;

CREATE TABLE IF NOT EXISTS delivery.delivery_attempts (
    id UUID PRIMARY KEY,
    notification_id UUID NOT NULL,
    user_id UUID NOT NULL,
    channel TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL,
    attempt_no INT NOT NULL DEFAULT 0,
    last_error_code TEXT NULL,
    last_error_message TEXT NULL,
    next_retry_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT delivery_status_check CHECK (status IN ('pending', 'sent', 'failed', 'dead')),
    CONSTRAINT delivery_channel_check CHECK (channel IN ('push', 'email', 'web')),
    UNIQUE (notification_id, user_id, channel)
);

CREATE INDEX IF NOT EXISTS idx_delivery_status_next_retry_at
    ON delivery.delivery_attempts (status, next_retry_at);

CREATE INDEX IF NOT EXISTS idx_delivery_notification_id
    ON delivery.delivery_attempts (notification_id);

CREATE INDEX IF NOT EXISTS idx_delivery_user_id
    ON delivery.delivery_attempts (user_id);

CREATE TABLE IF NOT EXISTS delivery.processed_events (
    event_id UUID PRIMARY KEY,
    subject TEXT NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
