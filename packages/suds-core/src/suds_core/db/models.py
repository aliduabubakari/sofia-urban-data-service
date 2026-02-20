# packages/suds-core/src/suds_core/db/models.py
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from geoalchemy2 import Geometry, WKBElement

class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# -------------------------
# Static geospatial layers
# -------------------------

class Buildings(Base, TimestampMixin):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    props: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False)

    __table_args__ = (
        Index("ix_buildings_geom_gist", "geom", postgresql_using="gist"),
    )


class GreenAreas(Base, TimestampMixin):
    __tablename__ = "green_areas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    props: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False)

    __table_args__ = (
        Index("ix_green_areas_geom_gist", "geom", postgresql_using="gist"),
    )


class Neighbourhoods(Base, TimestampMixin):
    __tablename__ = "neighbourhoods"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    props: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False)

    __table_args__ = (
        Index("ix_neighbourhoods_geom_gist", "geom", postgresql_using="gist"),
    )


class Streets(Base, TimestampMixin):
    __tablename__ = "streets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    props: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="MULTILINESTRING", srid=4326), nullable=False)

    __table_args__ = (
        Index("ix_streets_geom_gist", "geom", postgresql_using="gist"),
    )


class PedestrianNetwork(Base, TimestampMixin):
    __tablename__ = "pedestrian_network"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    props: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="MULTILINESTRING", srid=4326), nullable=False)

    __table_args__ = (
        Index("ix_pedestrian_network_geom_gist", "geom", postgresql_using="gist"),
    )


class Trees(Base, TimestampMixin):
    __tablename__ = "trees"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    props: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # Keep point (4326). Z can be stored in props if needed.
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    __table_args__ = (
        Index("ix_trees_geom_gist", "geom", postgresql_using="gist"),
    )


class POIs(Base, TimestampMixin):
    __tablename__ = "pois"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    props: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    __table_args__ = (
        Index("ix_pois_geom_gist", "geom", postgresql_using="gist"),
    )


# -------------------------
# Stations & time-series
# -------------------------

class Stations(Base, TimestampMixin):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    station_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    props: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    measurements: Mapped[list["AirQualityMeasurements"]] = relationship(back_populates="station")

    __table_args__ = (
        Index("ix_stations_geom_gist", "geom", postgresql_using="gist"),
    )


class AirQualityMeasurements(Base, TimestampMixin):
    __tablename__ = "air_quality_measurements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"), nullable=False)

    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)
    parameter: Mapped[str] = mapped_column(String(32), nullable=False, index=True)      # canonical (PM10, PM2.5, NO2, O3)
    parameter_raw: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)    # API name
    value: Mapped[float] = mapped_column(Float, nullable=False)

    unit: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="gate")
    data_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, default="valid")

    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    station: Mapped["Stations"] = relationship(back_populates="measurements")

    __table_args__ = (
        Index("ix_aq_station_param_time", "station_id", "parameter", "timestamp"),
        UniqueConstraint("station_id", "parameter", "timestamp", name="uq_aq_station_param_time"),
    )


class WeatherDaily(Base, TimestampMixin):
    __tablename__ = "weather_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"), nullable=False)

    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)

    # Store weather variables as JSONB (flexible)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_weather_station_date", "station_id", "date"),
        UniqueConstraint("station_id", "date", name="uq_weather_station_date"),
    )


class OsmMetrics(Base, TimestampMixin):
    __tablename__ = "osm_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"), nullable=False)

    buffer_m: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    extracted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_osm_station_buffer_extracted", "station_id", "buffer_m", "extracted_at"),
    )

class WeatherDailyPoint(Base, TimestampMixin):
    __tablename__ = "weather_daily_point"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    lat_round: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    lon_round: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)

    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="openmeteo")
    values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_weather_point_latlon_date", "lat_round", "lon_round", "date"),
        UniqueConstraint("lat_round", "lon_round", "date", "provider", name="uq_weather_point_day_provider"),
    )

class WeatherHourlyPoint(Base, TimestampMixin):
    __tablename__ = "weather_hourly_point"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    lat_round: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    lon_round: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    # store as timezone-aware; we will request UTC from OpenMeteo for hourly
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="openmeteo_archive")
    values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_weather_hourly_point_latlon_ts", "lat_round", "lon_round", "timestamp"),
        UniqueConstraint(
            "lat_round", "lon_round", "timestamp", "provider",
            name="uq_weather_hourly_point_latlon_ts_provider",
        ),
    )

class OsmMetricsPoint(Base, TimestampMixin):
    __tablename__ = "osm_metrics_point"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    lat_round: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    lon_round: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    buffer_m: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    extracted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_osm_point_latlon_buffer_extracted", "lat_round", "lon_round", "buffer_m", "extracted_at"),
    )

class OsmMetricsBbox(Base, TimestampMixin):
    __tablename__ = "osm_metrics_bbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    minx_round: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    miny_round: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    maxx_round: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    maxy_round: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    extracted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_osm_bbox_round_extracted", "minx_round", "miny_round", "maxx_round", "maxy_round", "extracted_at"),
    )

class CityLabStation(Base, TimestampMixin):
    __tablename__ = "citylab_stations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    external_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # e.g. A1
    station_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # airquality/noise/pedestrian

    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(256), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # store the full raw payload for traceability
    props: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    __table_args__ = (
        Index("ix_citylab_stations_geom", "geom", postgresql_using="gist"),
    )


class CityLabAggregate(Base, TimestampMixin):
    """
    Aggregated measurements from CityLab (hour/day/week/month endpoints).
    For Phase 1 we will fill: granularity='month', calculation_type='Mean'
    """
    __tablename__ = "citylab_aggregates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    station_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    station_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # "hour" | "day" | "week" | "month"
    granularity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # For month granularity: use period_start = YYYY-MM-01 00:00:00+00
    period_start: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # e.g. "PM2.5", "PM10", "NO2"
    param: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # "Mean" | "Median" | "First Quartile (25%)" | "Third Quartile (75%)"
    calculation_type: Mapped[str] = mapped_column(String(64), nullable=False, default="Mean")

    value: Mapped[float] = mapped_column(Float, nullable=False)

    # optional – can be added later if CityLab provides it
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)

    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint(
            "station_name", "station_type", "granularity", "period_start", "param", "calculation_type",
            name="uq_citylab_agg_key",
        ),
    )

class GeocodeCache(Base, TimestampMixin):
    __tablename__ = "geocode_cache"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="geoapify")
    # "search" | "reverse"
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # sha256 of normalized query
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query_text: Mapped[str] = mapped_column(String, nullable=False)

    best_lat: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    best_lon: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    best_formatted: Mapped[str | None] = mapped_column(String(512), nullable=True)
    best_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("provider", "kind", "query_hash", name="uq_geocode_cache_provider_kind_hash"),
    )

class WikidataSearchCache(Base, TimestampMixin):
    __tablename__ = "wikidata_search_cache"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query: Mapped[str] = mapped_column(String, nullable=False)
    lang: Mapped[str] = mapped_column(String(8), nullable=False, default="bg")
    limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("query_hash", "lang", "limit", name="uq_wikidata_search_hash_lang_limit"),
    )


class WikidataEntityCache(Base, TimestampMixin):
    __tablename__ = "wikidata_entity_cache"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    qid: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # "Q..."
    lang: Mapped[str] = mapped_column(String(8), nullable=False, default="bg")

    # store raw entity response (claims + labels + descriptions + sitelinks)
    entity: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("qid", "lang", name="uq_wikidata_entity_qid_lang"),
    )

 