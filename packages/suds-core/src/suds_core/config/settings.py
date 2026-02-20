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

    citylab_base_url: str = "https://citylab.gate-ai.eu/citylab/api"
    citylab_api_key: str | None = None
    citylab_timeout_s: int = 30

    geoapify_api_key: str | None = None
    geoapify_base_url: str = "https://api.geoapify.com/v1/geocode"

    geocode_rate_limit_per_min: int = 60
    geocode_batch_max_size: int = 100

    geoapify_use_batch_api: bool = False
    geoapify_batch_min_size: int = 25
    geoapify_batch_timeout_s: int = 60
    geoapify_batch_poll_s: float = 1.0

    wikidata_api_url: str = "https://www.wikidata.org/w/api.php"
    wikidata_cache_ttl_days: int = 30
    wikidata_user_agent: str = "SUDS/0.1 (contact: you@example.com)"

    overpass_url: str = "https://overpass-api.de/api/interpreter"
    overpass_timeout_s: int = 60
    overpass_rate_limit_delay_s: float = 2.0

    openmeteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    http_timeout_s: int = 30

    weather_cache_ttl_days: int = 90
    osm_cache_ttl_days: int = 30

    openmeteo_forecast_url: str = Field(
        default="https://api.open-meteo.com/v1/forecast",
    )

    weather_forecast_cache_ttl_hours: int = Field(
        default=6,
        description="Forecast cache TTL in hours. Forecast can change; archive is stable.",
    )

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