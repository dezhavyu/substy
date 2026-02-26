from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = Field(default="delivery-service", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8092, alias="APP_PORT")
    app_log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")
    app_json_logs: bool = Field(default=True, alias="APP_JSON_LOGS")

    db_host: str = Field(default="postgres", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="delivery", alias="DB_NAME")
    db_user: str = Field(default="delivery", alias="DB_USER")
    db_password: str = Field(default="delivery", alias="DB_PASSWORD")
    db_min_pool_size: int = Field(default=3, alias="DB_MIN_POOL_SIZE")
    db_max_pool_size: int = Field(default=20, alias="DB_MAX_POOL_SIZE")

    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    nats_url: str = Field(default="nats://nats:4222", alias="NATS_URL")
    nats_connect_timeout: int = Field(default=5, alias="NATS_CONNECT_TIMEOUT")
    nats_stream_name: str = Field(default="NOTIFICATIONS", alias="NATS_STREAM_NAME")
    nats_subject_notification_created: str = Field(
        default="notification.created.v1",
        alias="NATS_SUBJECT_NOTIFICATION_CREATED",
    )
    nats_subject_delivery_succeeded: str = Field(
        default="delivery.succeeded.v1",
        alias="NATS_SUBJECT_DELIVERY_SUCCEEDED",
    )
    nats_subject_delivery_failed: str = Field(
        default="delivery.failed.v1",
        alias="NATS_SUBJECT_DELIVERY_FAILED",
    )
    nats_consumer_name: str = Field(default="delivery-service", alias="NATS_CONSUMER_NAME")
    nats_durable_name: str = Field(default="delivery-service", alias="NATS_DURABLE_NAME")

    subscriptions_internal_url: str = Field(
        default="http://subscriptions-service:8090",
        alias="SUBSCRIPTIONS_INTERNAL_URL",
    )
    subscriptions_page_limit: int = Field(default=100, alias="SUBSCRIPTIONS_PAGE_LIMIT")
    subscriptions_fetch_concurrency: int = Field(default=3, alias="SUBSCRIPTIONS_FETCH_CONCURRENCY")

    delivery_max_attempts: int = Field(default=5, alias="DELIVERY_MAX_ATTEMPTS")
    delivery_base_delay_seconds: int = Field(default=5, alias="DELIVERY_BASE_DELAY_SECONDS")
    delivery_max_delay_seconds: int = Field(default=3600, alias="DELIVERY_MAX_DELAY_SECONDS")
    delivery_retry_jitter_seconds: int = Field(default=5, alias="DELIVERY_RETRY_JITTER_SECONDS")
    delivery_channels: str = Field(default="push,email,web", alias="DELIVERY_CHANNELS")

    provider_stub_fail_rate: float = Field(default=0.0, alias="PROVIDER_STUB_FAIL_RATE")

    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_service_name: str = Field(default="delivery-service", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://otel-collector:4317",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )

    @property
    def database_dsn(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def channels(self) -> tuple[str, ...]:
        return tuple(ch.strip().lower() for ch in self.delivery_channels.split(",") if ch.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
