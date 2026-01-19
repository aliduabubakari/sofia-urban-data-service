from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for suds-core.

    Reads env vars with prefix SUDS_ and also loads from .env automatically.
    """

    model_config = SettingsConfigDict(
        env_prefix="SUDS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -------------------------
    # Database
    # -------------------------
    database_url: Optional[str] = Field(
        default=None,
        description="SQLAlchemy DB URL. If set, overrides host/port/user/password/dbname fields.",
        examples=["postgresql+psycopg://user:pass@localhost:5432/suds"],
    )
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "suds"

    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # -------------------------
    # API / service behavior
    # -------------------------
    default_srid: int = 4326
    max_page_size: int = 50000
    default_page_size: int = 5000

    # API auth keys (comma-separated)
    api_keys: Optional[str] = Field(
        default=None,
        description="Comma-separated API keys for internal access (e.g. 'key1,key2').",
    )

    # -------------------------
    # External services
    # -------------------------
    # -------------------------
    # GATE API credentials (external env vars, no SUDS_ prefix)
    # -------------------------
    gate_api_username: Optional[str] = Field(default=None, validation_alias="GATE_API_USERNAME")
    gate_api_password: Optional[str] = Field(default=None, validation_alias="GATE_API_PASSWORD")

    # Optional: if GATE uses API keys instead of Basic
    gate_api_key: Optional[str] = Field(default=None, validation_alias="GATE_API_KEY")
    gate_api_key_header: str = Field(default="X-API-Key", validation_alias="GATE_API_KEY_HEADER")

    overpass_url: str = "https://overpass-api.de/api/interpreter"
    overpass_timeout_s: int = 60
    overpass_rate_limit_delay_s: float = 2.0

    openmeteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    http_timeout_s: int = 30

    weather_cache_ttl_days: int = 90
    osm_cache_ttl_days: int = 30

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()