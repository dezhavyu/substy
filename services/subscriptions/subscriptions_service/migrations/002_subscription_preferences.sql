CREATE TABLE IF NOT EXISTS subscriptions.subscription_preferences (
    subscription_id UUID PRIMARY KEY REFERENCES subscriptions.subscriptions(id) ON DELETE CASCADE,
    channels TEXT[] NOT NULL,
    quiet_hours_start TIME NULL,
    quiet_hours_end TIME NULL,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT subscription_preferences_channels_non_empty CHECK (cardinality(channels) > 0),
    CONSTRAINT subscription_preferences_channels_allowed CHECK (
        channels <@ ARRAY['push', 'email', 'web']::text[]
    )
);

INSERT INTO subscriptions.subscription_preferences (
    subscription_id,
    channels,
    quiet_hours_start,
    quiet_hours_end,
    timezone
)
SELECT
    s.id,
    ARRAY['push']::text[],
    NULL,
    NULL,
    'UTC'
FROM subscriptions.subscriptions s
ON CONFLICT (subscription_id) DO NOTHING;
