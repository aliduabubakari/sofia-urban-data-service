--
-- PostgreSQL database dump
--

-- Dumped from database version 16.4 (Debian 16.4-1.pgdg110+2)
-- Dumped by pg_dump version 16.4 (Debian 16.4-1.pgdg110+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: postgis_topology; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_topology WITH SCHEMA topology;


--
-- Name: EXTENSION postgis_topology; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis_topology IS 'PostGIS topology spatial types and functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: air_quality_measurements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.air_quality_measurements (
    id bigint NOT NULL,
    station_id bigint NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    parameter character varying(32) NOT NULL,
    parameter_raw character varying(64),
    value double precision NOT NULL,
    unit character varying(16),
    source character varying(32) NOT NULL,
    data_status character varying(16),
    extra jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: air_quality_measurements_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.air_quality_measurements_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: air_quality_measurements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.air_quality_measurements_id_seq OWNED BY public.air_quality_measurements.id;


--
-- Name: buildings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.buildings (
    id bigint NOT NULL,
    source_id character varying,
    props jsonb NOT NULL,
    geom public.geometry(MultiPolygon,4326) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: buildings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.buildings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: buildings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.buildings_id_seq OWNED BY public.buildings.id;


--
-- Name: citylab_aggregates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.citylab_aggregates (
    id bigint NOT NULL,
    station_name character varying(64) NOT NULL,
    station_type character varying(32) NOT NULL,
    granularity character varying(16) NOT NULL,
    period_start timestamp with time zone NOT NULL,
    param character varying(32) NOT NULL,
    calculation_type character varying(64) NOT NULL,
    value double precision NOT NULL,
    unit character varying(32),
    raw jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: citylab_aggregates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.citylab_aggregates_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: citylab_aggregates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.citylab_aggregates_id_seq OWNED BY public.citylab_aggregates.id;


--
-- Name: citylab_stations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.citylab_stations (
    id bigint NOT NULL,
    external_id integer NOT NULL,
    name character varying(64) NOT NULL,
    station_type character varying(32) NOT NULL,
    address character varying(512),
    operator character varying(256),
    model character varying(128),
    serial_number character varying(128),
    props jsonb NOT NULL,
    geom public.geometry(Point,4326) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: citylab_stations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.citylab_stations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: citylab_stations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.citylab_stations_id_seq OWNED BY public.citylab_stations.id;


--
-- Name: geocode_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.geocode_cache (
    id bigint NOT NULL,
    provider character varying(32) NOT NULL,
    kind character varying(16) NOT NULL,
    query_hash character varying(64) NOT NULL,
    query_text character varying NOT NULL,
    best_lat double precision,
    best_lon double precision,
    best_formatted character varying(512),
    best_confidence double precision,
    result jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: geocode_cache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.geocode_cache_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: geocode_cache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.geocode_cache_id_seq OWNED BY public.geocode_cache.id;


--
-- Name: green_areas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.green_areas (
    id bigint NOT NULL,
    source_id character varying,
    props jsonb NOT NULL,
    geom public.geometry(MultiPolygon,4326) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: green_areas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.green_areas_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: green_areas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.green_areas_id_seq OWNED BY public.green_areas.id;


--
-- Name: neighbourhoods; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.neighbourhoods (
    id bigint NOT NULL,
    source_id character varying,
    props jsonb NOT NULL,
    geom public.geometry(MultiPolygon,4326) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: neighbourhoods_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.neighbourhoods_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: neighbourhoods_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.neighbourhoods_id_seq OWNED BY public.neighbourhoods.id;


--
-- Name: osm_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.osm_metrics (
    id bigint NOT NULL,
    station_id bigint NOT NULL,
    buffer_m integer NOT NULL,
    extracted_at timestamp with time zone DEFAULT now() NOT NULL,
    metrics jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: osm_metrics_bbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.osm_metrics_bbox (
    id bigint NOT NULL,
    minx_round double precision NOT NULL,
    miny_round double precision NOT NULL,
    maxx_round double precision NOT NULL,
    maxy_round double precision NOT NULL,
    extracted_at timestamp with time zone DEFAULT now() NOT NULL,
    metrics jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: osm_metrics_bbox_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.osm_metrics_bbox_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: osm_metrics_bbox_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.osm_metrics_bbox_id_seq OWNED BY public.osm_metrics_bbox.id;


--
-- Name: osm_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.osm_metrics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: osm_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.osm_metrics_id_seq OWNED BY public.osm_metrics.id;


--
-- Name: osm_metrics_point; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.osm_metrics_point (
    id bigint NOT NULL,
    lat_round double precision NOT NULL,
    lon_round double precision NOT NULL,
    buffer_m integer NOT NULL,
    extracted_at timestamp with time zone DEFAULT now() NOT NULL,
    metrics jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: osm_metrics_point_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.osm_metrics_point_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: osm_metrics_point_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.osm_metrics_point_id_seq OWNED BY public.osm_metrics_point.id;


--
-- Name: pedestrian_network; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pedestrian_network (
    id bigint NOT NULL,
    source_id character varying,
    props jsonb NOT NULL,
    geom public.geometry(MultiLineString,4326) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: pedestrian_network_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pedestrian_network_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pedestrian_network_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pedestrian_network_id_seq OWNED BY public.pedestrian_network.id;


--
-- Name: pois; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pois (
    id bigint NOT NULL,
    source_id character varying,
    props jsonb NOT NULL,
    geom public.geometry(Point,4326) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: pois_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pois_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pois_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pois_id_seq OWNED BY public.pois.id;


--
-- Name: stations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stations (
    id bigint NOT NULL,
    station_name character varying(64) NOT NULL,
    props jsonb NOT NULL,
    geom public.geometry(Point,4326) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: stations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stations_id_seq OWNED BY public.stations.id;


--
-- Name: streets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.streets (
    id bigint NOT NULL,
    source_id character varying,
    props jsonb NOT NULL,
    geom public.geometry(MultiLineString,4326) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: streets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.streets_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: streets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.streets_id_seq OWNED BY public.streets.id;


--
-- Name: trees; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trees (
    id bigint NOT NULL,
    source_id character varying,
    props jsonb NOT NULL,
    geom public.geometry(Point,4326) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: trees_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trees_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trees_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trees_id_seq OWNED BY public.trees.id;


--
-- Name: weather_daily; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weather_daily (
    id bigint NOT NULL,
    station_id bigint NOT NULL,
    date date NOT NULL,
    "values" jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: weather_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.weather_daily_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: weather_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.weather_daily_id_seq OWNED BY public.weather_daily.id;


--
-- Name: weather_daily_point; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weather_daily_point (
    id bigint NOT NULL,
    lat_round double precision NOT NULL,
    lon_round double precision NOT NULL,
    date date NOT NULL,
    provider character varying(32) NOT NULL,
    "values" jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: weather_daily_point_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.weather_daily_point_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: weather_daily_point_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.weather_daily_point_id_seq OWNED BY public.weather_daily_point.id;


--
-- Name: weather_hourly_point; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weather_hourly_point (
    id bigint NOT NULL,
    lat_round double precision NOT NULL,
    lon_round double precision NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    provider character varying(32) NOT NULL,
    "values" jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: weather_hourly_point_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.weather_hourly_point_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: weather_hourly_point_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.weather_hourly_point_id_seq OWNED BY public.weather_hourly_point.id;


--
-- Name: wikidata_entity_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wikidata_entity_cache (
    id bigint NOT NULL,
    qid character varying(16) NOT NULL,
    lang character varying(8) NOT NULL,
    entity jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: wikidata_entity_cache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wikidata_entity_cache_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wikidata_entity_cache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wikidata_entity_cache_id_seq OWNED BY public.wikidata_entity_cache.id;


--
-- Name: wikidata_search_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wikidata_search_cache (
    id bigint NOT NULL,
    query_hash character varying(64) NOT NULL,
    query character varying NOT NULL,
    lang character varying(8) NOT NULL,
    "limit" integer NOT NULL,
    result jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: wikidata_search_cache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wikidata_search_cache_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wikidata_search_cache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wikidata_search_cache_id_seq OWNED BY public.wikidata_search_cache.id;


--
-- Name: air_quality_measurements id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.air_quality_measurements ALTER COLUMN id SET DEFAULT nextval('public.air_quality_measurements_id_seq'::regclass);


--
-- Name: buildings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buildings ALTER COLUMN id SET DEFAULT nextval('public.buildings_id_seq'::regclass);


--
-- Name: citylab_aggregates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citylab_aggregates ALTER COLUMN id SET DEFAULT nextval('public.citylab_aggregates_id_seq'::regclass);


--
-- Name: citylab_stations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citylab_stations ALTER COLUMN id SET DEFAULT nextval('public.citylab_stations_id_seq'::regclass);


--
-- Name: geocode_cache id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.geocode_cache ALTER COLUMN id SET DEFAULT nextval('public.geocode_cache_id_seq'::regclass);


--
-- Name: green_areas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.green_areas ALTER COLUMN id SET DEFAULT nextval('public.green_areas_id_seq'::regclass);


--
-- Name: neighbourhoods id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.neighbourhoods ALTER COLUMN id SET DEFAULT nextval('public.neighbourhoods_id_seq'::regclass);


--
-- Name: osm_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.osm_metrics ALTER COLUMN id SET DEFAULT nextval('public.osm_metrics_id_seq'::regclass);


--
-- Name: osm_metrics_bbox id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.osm_metrics_bbox ALTER COLUMN id SET DEFAULT nextval('public.osm_metrics_bbox_id_seq'::regclass);


--
-- Name: osm_metrics_point id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.osm_metrics_point ALTER COLUMN id SET DEFAULT nextval('public.osm_metrics_point_id_seq'::regclass);


--
-- Name: pedestrian_network id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedestrian_network ALTER COLUMN id SET DEFAULT nextval('public.pedestrian_network_id_seq'::regclass);


--
-- Name: pois id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pois ALTER COLUMN id SET DEFAULT nextval('public.pois_id_seq'::regclass);


--
-- Name: stations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stations ALTER COLUMN id SET DEFAULT nextval('public.stations_id_seq'::regclass);


--
-- Name: streets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.streets ALTER COLUMN id SET DEFAULT nextval('public.streets_id_seq'::regclass);


--
-- Name: trees id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trees ALTER COLUMN id SET DEFAULT nextval('public.trees_id_seq'::regclass);


--
-- Name: weather_daily id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_daily ALTER COLUMN id SET DEFAULT nextval('public.weather_daily_id_seq'::regclass);


--
-- Name: weather_daily_point id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_daily_point ALTER COLUMN id SET DEFAULT nextval('public.weather_daily_point_id_seq'::regclass);


--
-- Name: weather_hourly_point id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_hourly_point ALTER COLUMN id SET DEFAULT nextval('public.weather_hourly_point_id_seq'::regclass);


--
-- Name: wikidata_entity_cache id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wikidata_entity_cache ALTER COLUMN id SET DEFAULT nextval('public.wikidata_entity_cache_id_seq'::regclass);


--
-- Name: wikidata_search_cache id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wikidata_search_cache ALTER COLUMN id SET DEFAULT nextval('public.wikidata_search_cache_id_seq'::regclass);


--
-- Name: air_quality_measurements air_quality_measurements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.air_quality_measurements
    ADD CONSTRAINT air_quality_measurements_pkey PRIMARY KEY (id);


--
-- Name: buildings buildings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buildings
    ADD CONSTRAINT buildings_pkey PRIMARY KEY (id);


--
-- Name: citylab_aggregates citylab_aggregates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citylab_aggregates
    ADD CONSTRAINT citylab_aggregates_pkey PRIMARY KEY (id);


--
-- Name: citylab_stations citylab_stations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citylab_stations
    ADD CONSTRAINT citylab_stations_pkey PRIMARY KEY (id);


--
-- Name: geocode_cache geocode_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.geocode_cache
    ADD CONSTRAINT geocode_cache_pkey PRIMARY KEY (id);


--
-- Name: green_areas green_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.green_areas
    ADD CONSTRAINT green_areas_pkey PRIMARY KEY (id);


--
-- Name: neighbourhoods neighbourhoods_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.neighbourhoods
    ADD CONSTRAINT neighbourhoods_pkey PRIMARY KEY (id);


--
-- Name: osm_metrics_bbox osm_metrics_bbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.osm_metrics_bbox
    ADD CONSTRAINT osm_metrics_bbox_pkey PRIMARY KEY (id);


--
-- Name: osm_metrics osm_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.osm_metrics
    ADD CONSTRAINT osm_metrics_pkey PRIMARY KEY (id);


--
-- Name: osm_metrics_point osm_metrics_point_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.osm_metrics_point
    ADD CONSTRAINT osm_metrics_point_pkey PRIMARY KEY (id);


--
-- Name: pedestrian_network pedestrian_network_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedestrian_network
    ADD CONSTRAINT pedestrian_network_pkey PRIMARY KEY (id);


--
-- Name: pois pois_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pois
    ADD CONSTRAINT pois_pkey PRIMARY KEY (id);


--
-- Name: stations stations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stations
    ADD CONSTRAINT stations_pkey PRIMARY KEY (id);


--
-- Name: stations stations_station_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stations
    ADD CONSTRAINT stations_station_name_key UNIQUE (station_name);


--
-- Name: streets streets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.streets
    ADD CONSTRAINT streets_pkey PRIMARY KEY (id);


--
-- Name: trees trees_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trees
    ADD CONSTRAINT trees_pkey PRIMARY KEY (id);


--
-- Name: air_quality_measurements uq_aq_station_param_time; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.air_quality_measurements
    ADD CONSTRAINT uq_aq_station_param_time UNIQUE (station_id, parameter, "timestamp");


--
-- Name: citylab_aggregates uq_citylab_agg_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citylab_aggregates
    ADD CONSTRAINT uq_citylab_agg_key UNIQUE (station_name, station_type, granularity, period_start, param, calculation_type);


--
-- Name: geocode_cache uq_geocode_cache_provider_kind_hash; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.geocode_cache
    ADD CONSTRAINT uq_geocode_cache_provider_kind_hash UNIQUE (provider, kind, query_hash);


--
-- Name: weather_hourly_point uq_weather_hourly_point_latlon_ts_provider; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_hourly_point
    ADD CONSTRAINT uq_weather_hourly_point_latlon_ts_provider UNIQUE (lat_round, lon_round, "timestamp", provider);


--
-- Name: weather_daily_point uq_weather_point_day_provider; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_daily_point
    ADD CONSTRAINT uq_weather_point_day_provider UNIQUE (lat_round, lon_round, date, provider);


--
-- Name: weather_daily uq_weather_station_date; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_daily
    ADD CONSTRAINT uq_weather_station_date UNIQUE (station_id, date);


--
-- Name: wikidata_entity_cache uq_wikidata_entity_qid_lang; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wikidata_entity_cache
    ADD CONSTRAINT uq_wikidata_entity_qid_lang UNIQUE (qid, lang);


--
-- Name: wikidata_search_cache uq_wikidata_search_hash_lang_limit; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wikidata_search_cache
    ADD CONSTRAINT uq_wikidata_search_hash_lang_limit UNIQUE (query_hash, lang, "limit");


--
-- Name: weather_daily weather_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_daily
    ADD CONSTRAINT weather_daily_pkey PRIMARY KEY (id);


--
-- Name: weather_daily_point weather_daily_point_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_daily_point
    ADD CONSTRAINT weather_daily_point_pkey PRIMARY KEY (id);


--
-- Name: weather_hourly_point weather_hourly_point_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_hourly_point
    ADD CONSTRAINT weather_hourly_point_pkey PRIMARY KEY (id);


--
-- Name: wikidata_entity_cache wikidata_entity_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wikidata_entity_cache
    ADD CONSTRAINT wikidata_entity_cache_pkey PRIMARY KEY (id);


--
-- Name: wikidata_search_cache wikidata_search_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wikidata_search_cache
    ADD CONSTRAINT wikidata_search_cache_pkey PRIMARY KEY (id);


--
-- Name: idx_buildings_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_buildings_geom ON public.buildings USING gist (geom);


--
-- Name: idx_citylab_stations_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_citylab_stations_geom ON public.citylab_stations USING gist (geom);


--
-- Name: idx_green_areas_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_green_areas_geom ON public.green_areas USING gist (geom);


--
-- Name: idx_neighbourhoods_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_neighbourhoods_geom ON public.neighbourhoods USING gist (geom);


--
-- Name: idx_pedestrian_network_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pedestrian_network_geom ON public.pedestrian_network USING gist (geom);


--
-- Name: idx_pois_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pois_geom ON public.pois USING gist (geom);


--
-- Name: idx_stations_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stations_geom ON public.stations USING gist (geom);


--
-- Name: idx_streets_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_streets_geom ON public.streets USING gist (geom);


--
-- Name: idx_trees_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trees_geom ON public.trees USING gist (geom);


--
-- Name: ix_air_quality_measurements_parameter; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_air_quality_measurements_parameter ON public.air_quality_measurements USING btree (parameter);


--
-- Name: ix_air_quality_measurements_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_air_quality_measurements_timestamp ON public.air_quality_measurements USING btree ("timestamp");


--
-- Name: ix_aq_station_param_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aq_station_param_time ON public.air_quality_measurements USING btree (station_id, parameter, "timestamp");


--
-- Name: ix_buildings_geom_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_buildings_geom_gist ON public.buildings USING gist (geom);


--
-- Name: ix_citylab_aggregates_granularity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citylab_aggregates_granularity ON public.citylab_aggregates USING btree (granularity);


--
-- Name: ix_citylab_aggregates_param; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citylab_aggregates_param ON public.citylab_aggregates USING btree (param);


--
-- Name: ix_citylab_aggregates_period_start; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citylab_aggregates_period_start ON public.citylab_aggregates USING btree (period_start);


--
-- Name: ix_citylab_aggregates_station_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citylab_aggregates_station_name ON public.citylab_aggregates USING btree (station_name);


--
-- Name: ix_citylab_aggregates_station_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citylab_aggregates_station_type ON public.citylab_aggregates USING btree (station_type);


--
-- Name: ix_citylab_stations_external_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_citylab_stations_external_id ON public.citylab_stations USING btree (external_id);


--
-- Name: ix_citylab_stations_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citylab_stations_geom ON public.citylab_stations USING gist (geom);


--
-- Name: ix_citylab_stations_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citylab_stations_name ON public.citylab_stations USING btree (name);


--
-- Name: ix_citylab_stations_station_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citylab_stations_station_type ON public.citylab_stations USING btree (station_type);


--
-- Name: ix_geocode_cache_best_lat; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_geocode_cache_best_lat ON public.geocode_cache USING btree (best_lat);


--
-- Name: ix_geocode_cache_best_lon; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_geocode_cache_best_lon ON public.geocode_cache USING btree (best_lon);


--
-- Name: ix_geocode_cache_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_geocode_cache_kind ON public.geocode_cache USING btree (kind);


--
-- Name: ix_geocode_cache_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_geocode_cache_provider ON public.geocode_cache USING btree (provider);


--
-- Name: ix_geocode_cache_query_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_geocode_cache_query_hash ON public.geocode_cache USING btree (query_hash);


--
-- Name: ix_green_areas_geom_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_green_areas_geom_gist ON public.green_areas USING gist (geom);


--
-- Name: ix_neighbourhoods_geom_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_neighbourhoods_geom_gist ON public.neighbourhoods USING gist (geom);


--
-- Name: ix_osm_bbox_round_extracted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_osm_bbox_round_extracted ON public.osm_metrics_bbox USING btree (minx_round, miny_round, maxx_round, maxy_round, extracted_at);


--
-- Name: ix_osm_metrics_bbox_maxx_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_osm_metrics_bbox_maxx_round ON public.osm_metrics_bbox USING btree (maxx_round);


--
-- Name: ix_osm_metrics_bbox_maxy_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_osm_metrics_bbox_maxy_round ON public.osm_metrics_bbox USING btree (maxy_round);


--
-- Name: ix_osm_metrics_bbox_minx_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_osm_metrics_bbox_minx_round ON public.osm_metrics_bbox USING btree (minx_round);


--
-- Name: ix_osm_metrics_bbox_miny_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_osm_metrics_bbox_miny_round ON public.osm_metrics_bbox USING btree (miny_round);


--
-- Name: ix_osm_metrics_point_lat_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_osm_metrics_point_lat_round ON public.osm_metrics_point USING btree (lat_round);


--
-- Name: ix_osm_metrics_point_lon_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_osm_metrics_point_lon_round ON public.osm_metrics_point USING btree (lon_round);


--
-- Name: ix_osm_point_latlon_buffer_extracted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_osm_point_latlon_buffer_extracted ON public.osm_metrics_point USING btree (lat_round, lon_round, buffer_m, extracted_at);


--
-- Name: ix_osm_station_buffer_extracted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_osm_station_buffer_extracted ON public.osm_metrics USING btree (station_id, buffer_m, extracted_at);


--
-- Name: ix_pedestrian_network_geom_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pedestrian_network_geom_gist ON public.pedestrian_network USING gist (geom);


--
-- Name: ix_pois_geom_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pois_geom_gist ON public.pois USING gist (geom);


--
-- Name: ix_stations_geom_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_stations_geom_gist ON public.stations USING gist (geom);


--
-- Name: ix_streets_geom_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_streets_geom_gist ON public.streets USING gist (geom);


--
-- Name: ix_trees_geom_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trees_geom_gist ON public.trees USING gist (geom);


--
-- Name: ix_weather_daily_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_daily_date ON public.weather_daily USING btree (date);


--
-- Name: ix_weather_daily_point_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_daily_point_date ON public.weather_daily_point USING btree (date);


--
-- Name: ix_weather_daily_point_lat_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_daily_point_lat_round ON public.weather_daily_point USING btree (lat_round);


--
-- Name: ix_weather_daily_point_lon_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_daily_point_lon_round ON public.weather_daily_point USING btree (lon_round);


--
-- Name: ix_weather_hourly_point_lat_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_hourly_point_lat_round ON public.weather_hourly_point USING btree (lat_round);


--
-- Name: ix_weather_hourly_point_latlon_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_hourly_point_latlon_ts ON public.weather_hourly_point USING btree (lat_round, lon_round, "timestamp");


--
-- Name: ix_weather_hourly_point_lon_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_hourly_point_lon_round ON public.weather_hourly_point USING btree (lon_round);


--
-- Name: ix_weather_hourly_point_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_hourly_point_timestamp ON public.weather_hourly_point USING btree ("timestamp");


--
-- Name: ix_weather_point_latlon_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_point_latlon_date ON public.weather_daily_point USING btree (lat_round, lon_round, date);


--
-- Name: ix_weather_station_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_station_date ON public.weather_daily USING btree (station_id, date);


--
-- Name: ix_wikidata_entity_cache_qid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_wikidata_entity_cache_qid ON public.wikidata_entity_cache USING btree (qid);


--
-- Name: ix_wikidata_search_cache_query_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_wikidata_search_cache_query_hash ON public.wikidata_search_cache USING btree (query_hash);


--
-- Name: air_quality_measurements air_quality_measurements_station_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.air_quality_measurements
    ADD CONSTRAINT air_quality_measurements_station_id_fkey FOREIGN KEY (station_id) REFERENCES public.stations(id) ON DELETE CASCADE;


--
-- Name: osm_metrics osm_metrics_station_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.osm_metrics
    ADD CONSTRAINT osm_metrics_station_id_fkey FOREIGN KEY (station_id) REFERENCES public.stations(id) ON DELETE CASCADE;


--
-- Name: weather_daily weather_daily_station_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_daily
    ADD CONSTRAINT weather_daily_station_id_fkey FOREIGN KEY (station_id) REFERENCES public.stations(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

