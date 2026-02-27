from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = Field(default="auth-service", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8080, alias="APP_PORT")
    app_log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")
    app_json_logs: bool = Field(default=True, alias="APP_JSON_LOGS")

    db_host: str = Field(default="postgres", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="auth", alias="DB_NAME")
    db_user: str = Field(default="auth", alias="DB_USER")
    db_password: str = Field(default="auth", alias="DB_PASSWORD")
    db_min_pool_size: int = Field(default=5, alias="DB_MIN_POOL_SIZE")
    db_max_pool_size: int = Field(default=20, alias="DB_MAX_POOL_SIZE")

    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    nats_url: str = Field(default="nats://nats:4222", alias="NATS_URL")
    nats_connect_timeout: int = Field(default=5, alias="NATS_CONNECT_TIMEOUT")

    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_issuer: str = Field(default="auth-service", alias="JWT_ISSUER")
    jwt_audience: str = Field(default="substy", alias="JWT_AUDIENCE")
    jwt_access_token_ttl_minutes: int = Field(default=15, alias="JWT_ACCESS_TOKEN_TTL_MINUTES")
    jwt_refresh_token_ttl_seconds: int | None = Field(default=None, alias="JWT_REFRESH_TOKEN_TTL_SECONDS")
    jwt_refresh_token_ttl_days: int = Field(default=30, alias="JWT_REFRESH_TOKEN_TTL_DAYS")
    jwt_secret: str = Field(default="change-me-super-secret", alias="JWT_SECRET")
    jwt_private_key: str = Field(default="", alias="JWT_PRIVATE_KEY")
    jwt_public_key: str = Field(default="", alias="JWT_PUBLIC_KEY")
    refresh_token_pepper: str = Field(default="change-me-token-pepper", alias="REFRESH_TOKEN_PEPPER")

    rate_limit_login: int = Field(default=10, alias="RATE_LIMIT_LOGIN")
    rate_limit_register: int = Field(default=5, alias="RATE_LIMIT_REGISTER")
    rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")

    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_service_name: str = Field(default="auth-service", alias="OTEL_SERVICE_NAME")
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
    def effective_refresh_token_ttl_seconds(self) -> int:
        if self.jwt_refresh_token_ttl_seconds is not None:
            return max(1, self.jwt_refresh_token_ttl_seconds)
        return max(1, self.jwt_refresh_token_ttl_days * 24 * 60 * 60)


@lru_cache
def get_settings() -> Settings:
    return Settings()
