from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = Field(default="subscriptions-service", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8090, alias="APP_PORT")
    app_log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")
    app_json_logs: bool = Field(default=True, alias="APP_JSON_LOGS")

    db_host: str = Field(default="postgres", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="subscriptions", alias="DB_NAME")
    db_user: str = Field(default="subscriptions", alias="DB_USER")
    db_password: str = Field(default="subscriptions", alias="DB_PASSWORD")
    db_min_pool_size: int = Field(default=3, alias="DB_MIN_POOL_SIZE")
    db_max_pool_size: int = Field(default=20, alias="DB_MAX_POOL_SIZE")

    page_limit_default: int = 50
    page_limit_max: int = 500
    internal_subscribers_limit_default: int = 100
    internal_subscribers_limit_max: int = 500

    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_service_name: str = Field(default="subscriptions-service", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://otel-collector:4317",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )

    @property
    def database_dsn(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
