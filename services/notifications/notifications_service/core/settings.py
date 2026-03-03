from functools import lru_cache
from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = Field(default="notifications-service", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8091, alias="APP_PORT")
    app_log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")
    app_json_logs: bool = Field(default=True, alias="APP_JSON_LOGS")

    db_host: str = Field(default="postgres", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="notifications", alias="DB_NAME")
    db_user: str = Field(default="notifications", alias="DB_USER")
    db_password: str = Field(default="notifications", alias="DB_PASSWORD")
    db_min_pool_size: int = Field(default=3, alias="DB_MIN_POOL_SIZE")
    db_max_pool_size: int = Field(default=20, alias="DB_MAX_POOL_SIZE")

    nats_url: str = Field(default="nats://nats:4222", alias="NATS_URL")
    nats_connect_timeout: int = Field(default=5, alias="NATS_CONNECT_TIMEOUT")
    nats_stream_name: str = Field(default="NOTIFICATIONS", alias="NATS_STREAM_NAME")
    nats_subject_notification_created: str = Field(
        default="notification.created.v1",
        alias="NATS_SUBJECT_NOTIFICATION_CREATED",
    )

    outbox_batch_size: int = Field(default=100, alias="OUTBOX_BATCH_SIZE")
    outbox_publish_interval_seconds: float = Field(default=2.0, alias="OUTBOX_PUBLISH_INTERVAL_SECONDS")
    outbox_worker_enabled: bool = Field(default=False, alias="OUTBOX_WORKER_ENABLED")
    scheduler_batch_size: int = Field(default=200, alias="SCHEDULER_BATCH_SIZE")
    scheduler_tick_interval_seconds: float = Field(default=2.0, alias="SCHEDULER_TICK_INTERVAL_SECONDS")

    payload_max_bytes: int = Field(default=65536, alias="PAYLOAD_MAX_BYTES")
    payload_max_depth: int = Field(default=8, alias="PAYLOAD_MAX_DEPTH")

    page_limit_default: int = 50
    page_limit_max: int = 200

    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_service_name: str = Field(default="notifications-service", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://otel-collector:4317",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )

    @property
    def database_dsn(self) -> str:
        db_user = quote(self.db_user, safe="")
        db_password = quote(self.db_password, safe="")
        db_name = quote(self.db_name, safe="")
        return (
            f"postgresql://{db_user}:{db_password}@{self.db_host}:{self.db_port}/{db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
