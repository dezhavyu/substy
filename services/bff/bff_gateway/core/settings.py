from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = Field(default="bff-gateway", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8070, alias="APP_PORT")
    app_log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")
    app_json_logs: bool = Field(default=True, alias="APP_JSON_LOGS")

    auth_service_url: str = Field(default="http://auth-service:8080", alias="AUTH_SERVICE_URL")
    subscriptions_service_url: str = Field(
        default="http://subscriptions-service:8090",
        alias="SUBSCRIPTIONS_SERVICE_URL",
    )
    notifications_service_url: str = Field(
        default="http://notifications-service:8091",
        alias="NOTIFICATIONS_SERVICE_URL",
    )

    http_connect_timeout_seconds: float = Field(default=1.0, alias="HTTP_CONNECT_TIMEOUT_SECONDS")
    http_read_timeout_seconds: float = Field(default=5.0, alias="HTTP_READ_TIMEOUT_SECONDS")
    http_retries_get: int = Field(default=2, alias="HTTP_RETRIES_GET")

    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    jwt_mode: str = Field(default="local", alias="JWT_MODE")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_audience: str = Field(default="substy", alias="JWT_AUDIENCE")
    jwt_issuer: str = Field(default="auth-service", alias="JWT_ISSUER")
    jwt_secret: str = Field(default="change-me-super-secret-at-least-32-bytes", alias="JWT_SECRET")
    jwt_public_key: str = Field(default="", alias="JWT_PUBLIC_KEY")

    rate_limit_auth_per_minute: int = Field(default=5, alias="RATE_LIMIT_AUTH_PER_MINUTE")
    rate_limit_user_per_minute: int = Field(default=60, alias="RATE_LIMIT_USER_PER_MINUTE")

    cors_allow_origins: str = Field(default="http://localhost:3000,http://localhost:5173", alias="CORS_ALLOW_ORIGINS")
    max_body_bytes: int = Field(default=1024 * 1024, alias="MAX_BODY_BYTES")

    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_service_name: str = Field(default="bff-gateway", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://otel-collector:4317",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )

    @property
    def parsed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
