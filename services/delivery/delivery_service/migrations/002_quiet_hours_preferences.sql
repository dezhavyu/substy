ALTER TABLE delivery.delivery_attempts
    ADD COLUMN IF NOT EXISTS quiet_hours_start TIME NULL,
    ADD COLUMN IF NOT EXISTS quiet_hours_end TIME NULL,
    ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'UTC';
