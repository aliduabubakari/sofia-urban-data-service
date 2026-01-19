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

