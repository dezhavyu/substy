CREATE SCHEMA IF NOT EXISTS subscriptions;

CREATE TABLE IF NOT EXISTS subscriptions.topics (
    id UUID PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_topics_key ON subscriptions.topics (key);
CREATE INDEX IF NOT EXISTS idx_topics_created_at ON subscriptions.topics (created_at);

CREATE TABLE IF NOT EXISTS subscriptions.subscriptions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    topic_id UUID NOT NULL REFERENCES subscriptions.topics(id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_created_at
    ON subscriptions.subscriptions (user_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_subscriptions_topic_user
    ON subscriptions.subscriptions (topic_id, user_id, id);
